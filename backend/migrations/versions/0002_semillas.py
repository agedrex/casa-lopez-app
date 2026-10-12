"""Load the exact Excel catalog seeds using natural keys (WO 2)."""

from alembic import op

revision = "0002_semillas"
down_revision = "0001_esquema_costos"
branch_labels = None
depends_on = None

SEED_STATEMENTS = (
    """INSERT INTO costos.etapa (codigo,nombre,grupo,orden,requiere_material) VALUES
 ('CUERO','Cuero (capa externa)','material exterior',1,true),
 ('FORRO','Forro (capa interna)','material interior',2,true),
 ('HERRAJES','Herrajes, hilo y cemento','accesorios y detalles',3,false),
 ('REFUERZO','Refuerzos (flex, goma EVA)','accesorios y detalles',4,true),
 ('CORTE','Corte','refinamiento',5,false),
 ('REB','Reb (supuesto: rebajado)','refinamiento',6,false),
 ('PREP','Prep (supuesto: preparación)','refinamiento',7,false),
 ('MANO_OBRA','Mano de obra (estimación)','mano de obra',8,false)""",
    """INSERT INTO costos.material (nombre,tipo,unidad_consumo,codigo_excel,cotizable,notas) VALUES
 ('Estándar (Anilina Fina Lisa - C Arena)','cuero','m2','cuero:1',true,NULL),
 ('Carpincho','cuero','m2','cuero:2',true,NULL),
 ('Lagarto','cuero','m2','cuero:3',false,'Precio en USD por cm (texto en G9). Bloqueado hasta definir unidad.'),
 ('Yacaré overo','cuero','m2','cuero:4',false,'Precio en USD por cm (texto en G10). Bloqueado hasta definir unidad.'),
 ('Grano largo','cuero','m2','cuero:5',true,'H11 tipeado 34040 (= 23 x 1480).'),
 ('Camuflado / vaca con pelo','cuero','m2','cuero:6',true,NULL),
 ('Potro / Popurri / Cuero','forro','m2','forro:1',true,NULL),
 ('Tela forrería (Gross textil 1 x 1,50)','forro','m2','forro:2',true,'G14 dice U$S pero es precio en pesos.'),
 ('Flex 1 x 1,40 m x 0,8 mm','refuerzo','m2','insumo:W5',true,NULL),
 ('Goma EVA 1 x 1,40 x 2 mm','refuerzo','m2','insumo:W6',true,NULL),
 ('Cartón 1,5 mm','refuerzo','m2','insumo:W10',true,'No lo usa ninguna fórmula.')""",
    """INSERT INTO costos.proveedor (nombre,categorias) VALUES ('Rouez','refuerzos'),('Acropol','refuerzos')""",
    """INSERT INTO costos.precio_material (material_id,proveedor_id,precio,moneda,unidad_precio,presentacion,precio_presentacion,contenido_presentacion,vigente_desde,fuente,fuente_detalle)
SELECT m.id, p.id, v.precio, v.moneda, v.unidad, v.pres, v.ppres, v.cont, v.desde::date, 'excel_migracion', v.celda
FROM (VALUES
 ('cuero:1',NULL,24,'USD','m2',NULL,NULL,NULL,'2026-09-01','Marroquineria1!G7'),
 ('cuero:2',NULL,80,'USD','m2',NULL,NULL,NULL,'2026-09-01','Marroquineria1!G8'),
 ('cuero:3',NULL,26,'USD','cm',NULL,NULL,NULL,'2026-09-01','Marroquineria1!G9 (texto)'),
 ('cuero:4',NULL,3,'USD','cm',NULL,NULL,NULL,'2026-09-01','Marroquineria1!G10 (texto)'),
 ('cuero:5',NULL,34040,'ARS','m2',NULL,NULL,NULL,'2026-09-01','Marroquineria1!H11 (tipeado)'),
 ('cuero:6',NULL,35,'USD','m2',NULL,NULL,NULL,'2026-09-01','Marroquineria1!G12'),
 ('forro:1',NULL,19,'USD','m2',NULL,NULL,NULL,'2026-09-01','Marroquineria1!G13'),
 ('forro:2',NULL,4053,'ARS','m2','rollo/plancha 1 x 1,50 m',6080,1.50,'2026-09-01','Marroquineria1!W7 (V7 = 6080)'),
 ('insumo:W5','Rouez',10000,'ARS','m2','rollo/plancha 1 x 1,40 m',14000,1.40,'2026-09-03','Marroquineria1!W5 (V5 = 14000)'),
 ('insumo:W6','Acropol',5857,'ARS','m2','rollo/plancha 1 x 1,40 m x 2 mm',8200,1.40,'2026-09-03','Marroquineria1!W6 (V6 = 8200)'),
 ('insumo:W10',NULL,12250,'ARS','m2',NULL,NULL,NULL,'2026-09-01','Marroquineria1!W10')
) AS v(cod,prov,precio,moneda,unidad,pres,ppres,cont,desde,celda)
JOIN costos.material m ON m.codigo_excel = v.cod
LEFT JOIN costos.proveedor p ON p.nombre = v.prov""",
    """INSERT INTO costos.tipo_cambio (fecha,valor,fuente,fuente_detalle) VALUES ('2026-09-01',1545,'manual Excel','Marroquineria1!G15')""",
    """INSERT INTO costos.parametro (clave,valor,vigente_desde,fuente,fuente_detalle) VALUES
 ('GG_PCT',11,'2026-09-01','excel_migracion','Marroquineria1!G16'),
 ('GANANCIA_PCT',0,'2026-09-01','excel_migracion','Marroquineria1!G17 (no la usa ninguna fórmula)')""",
    """INSERT INTO costos.categoria (nombre) VALUES ('Portafolio'),('Cartera'),('Billetera')""",
)


def upgrade():
    for statement in SEED_STATEMENTS:
        op.execute(statement)


def downgrade():
    op.execute("""
    DO $wo2$
    DECLARE
        seed record;
        candidate_supplier_ids bigint[];
        candidate_price_ids bigint[];
        captured_supplier_ids bigint[] := ARRAY[]::bigint[];
        captured_price_ids bigint[] := ARRAY[]::bigint[];
    BEGIN
        -- Preserve the price relationships until supplier identity is established.
        LOCK TABLE costos.proveedor, costos.precio_material IN SHARE ROW EXCLUSIVE MODE;
        FOR seed IN SELECT * FROM (VALUES
            ('insumo:W5', 'Rouez', 10000, 'rollo/plancha 1 x 1,40 m', 14000,
             1.40, 'Marroquineria1!W5 (V5 = 14000)'),
            ('insumo:W6', 'Acropol', 5857, 'rollo/plancha 1 x 1,40 m x 2 mm', 8200,
             1.40, 'Marroquineria1!W6 (V6 = 8200)')
        ) AS expected(code, supplier, price, presentation, presentation_price, content, detail)
        LOOP
            SELECT array_agg(p.id), array_agg(pm.id)
            INTO candidate_supplier_ids, candidate_price_ids
            FROM costos.precio_material pm
            JOIN costos.material m ON m.id = pm.material_id
            JOIN costos.proveedor p ON p.id = pm.proveedor_id
            WHERE m.codigo_excel = seed.code AND p.nombre = seed.supplier
              AND p.categorias = 'refuerzos' AND p.activo IS TRUE
              AND p.cuit IS NULL AND p.direccion IS NULL AND p.telefono IS NULL
              AND p.contacto IS NULL AND p.notas IS NULL
              AND pm.precio = seed.price AND pm.moneda = 'ARS' AND pm.unidad_precio = 'm2'
              AND pm.presentacion = seed.presentation
              AND pm.precio_presentacion = seed.presentation_price
              AND pm.contenido_presentacion = seed.content
              AND pm.vigente_desde = DATE '2026-09-03'
              AND pm.fuente = 'excel_migracion' AND pm.fuente_detalle = seed.detail;
            IF cardinality(candidate_supplier_ids) IS DISTINCT FROM 1 THEN
                RAISE EXCEPTION 'Seed supplier identity is missing or ambiguous; downgrade refused.';
            END IF;
            captured_supplier_ids := captured_supplier_ids || candidate_supplier_ids;
            captured_price_ids := captured_price_ids || candidate_price_ids;
        END LOOP;

        DELETE FROM costos.categoria WHERE nombre IN ('Portafolio','Cartera','Billetera');
        DELETE FROM costos.parametro
          WHERE clave IN ('GG_PCT','GANANCIA_PCT') AND vigente_desde = DATE '2026-09-01'
            AND fuente = 'excel_migracion';
        DELETE FROM costos.tipo_cambio WHERE fecha = DATE '2026-09-01' AND fuente = 'manual Excel';
        DELETE FROM costos.precio_material pm USING costos.material m
        WHERE pm.material_id = m.id AND pm.fuente = 'excel_migracion' AND (
            (m.codigo_excel IN ('cuero:1','cuero:2','cuero:3','cuero:4','cuero:5','cuero:6','forro:1','forro:2','insumo:W10')
                AND pm.proveedor_id IS NULL AND pm.vigente_desde = DATE '2026-09-01')
            OR pm.id = ANY(captured_price_ids)
        );
        DELETE FROM costos.proveedor p
          WHERE p.id = ANY(captured_supplier_ids) AND p.categorias = 'refuerzos'
            AND p.activo IS TRUE AND p.cuit IS NULL AND p.direccion IS NULL
            AND p.telefono IS NULL AND p.contacto IS NULL AND p.notas IS NULL;
        DELETE FROM costos.material WHERE codigo_excel IN
          ('cuero:1','cuero:2','cuero:3','cuero:4','cuero:5','cuero:6','forro:1','forro:2','insumo:W5','insumo:W6','insumo:W10');
        DELETE FROM costos.etapa WHERE codigo IN
          ('CUERO','FORRO','HERRAJES','REFUERZO','CORTE','REB','PREP','MANO_OBRA');
    END;
    $wo2$;
    """)
