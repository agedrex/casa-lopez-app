-- Casa López · DER v1 · BORRADOR DE VALIDACIÓN (WO 1)
-- No es la migración. Sirve para probar que el DER compila en Postgres 16 y que
-- reproduce la fila 22 del Excel. La migración real la hace la WO 2 con Alembic.
-- Solo las 11 tablas de la primera migración. Las de fase 2 están descriptas en der.md.

BEGIN;
CREATE SCHEMA IF NOT EXISTS costos;
SET search_path TO costos;

-- ---------- Catálogo ----------
CREATE TABLE categoria (
  id          bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  nombre      text NOT NULL UNIQUE,
  activo      boolean NOT NULL DEFAULT true,
  created_at  timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE producto (
  id                bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  codigo_modelo     text,                       -- texto tal cual el Excel: '6', '514/1'. NO único.
  nombre            text NOT NULL,              -- nombre limpio
  nombre_original   text,                       -- columna F sin tocar
  categoria_id      bigint REFERENCES categoria(id),
  tamano            text CHECK (tamano IN ('chico','mediano','grande')),
  producto_base_id  bigint REFERENCES producto(id),   -- solo si la base es inequívoca
  estado            text NOT NULL DEFAULT 'activo' CHECK (estado IN ('activo','archivado')),
  codigo_erp        text UNIQUE,                -- vacío hasta que Alejandro/Gerardo confirmen
  fila_excel        integer UNIQUE,             -- trazabilidad: fila de Marroquineria1
  notas             text,
  created_at        timestamptz NOT NULL DEFAULT now(),
  updated_at        timestamptz NOT NULL DEFAULT now(),
  CHECK (producto_base_id IS NULL OR producto_base_id <> id)
);
CREATE INDEX producto_codigo_modelo_idx ON producto (codigo_modelo);

CREATE TABLE etapa (
  id                 bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  codigo             text NOT NULL UNIQUE,
  nombre             text NOT NULL,
  grupo              text NOT NULL,
  orden              smallint NOT NULL UNIQUE,
  requiere_material  boolean NOT NULL
);

CREATE TABLE material (
  id              bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  nombre          text NOT NULL,
  tipo            text NOT NULL CHECK (tipo IN ('cuero','forro','refuerzo','insumo')),
  unidad_consumo  text NOT NULL CHECK (unidad_consumo IN ('m2','cm','unidad')),
  codigo_excel    text UNIQUE,                  -- 'cuero:1', 'forro:2', 'insumo:W5'
  cotizable       boolean NOT NULL DEFAULT true, -- lagarto y yacaré = false
  activo          boolean NOT NULL DEFAULT true,
  notas           text,
  created_at      timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE proveedor (
  id          bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  nombre      text NOT NULL,
  cuit        text UNIQUE,
  direccion   text,
  telefono    text,
  contacto    text,
  categorias  text,
  activo      boolean NOT NULL DEFAULT true,
  notas       text,
  created_at  timestamptz NOT NULL DEFAULT now()
);

-- ---------- Precios y parámetros (solo se agregan filas) ----------
CREATE TABLE precio_material (
  id                      bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  material_id             bigint NOT NULL REFERENCES material(id),
  proveedor_id            bigint REFERENCES proveedor(id),   -- null = proveedor desconocido
  precio                  numeric(14,4) NOT NULL CHECK (precio >= 0),
  moneda                  char(3) NOT NULL CHECK (moneda IN ('ARS','USD')),
  unidad_precio           text NOT NULL CHECK (unidad_precio IN ('m2','cm','unidad')),
  presentacion            text,                 -- 'plancha 1 x 1,40 m'
  precio_presentacion     numeric(14,4),        -- 14000
  contenido_presentacion  numeric(10,4),        -- 1.40 (en unidad_precio)
  vigente_desde           date NOT NULL,
  fuente                  text NOT NULL CHECK (fuente IN ('excel_migracion','manual','proveedor')),
  fuente_detalle          text,                 -- 'Marroquineria1!W5'
  created_at              timestamptz NOT NULL DEFAULT now(),
  CHECK ((presentacion IS NULL) = (precio_presentacion IS NULL))
);
CREATE UNIQUE INDEX precio_material_uq
  ON precio_material (material_id, COALESCE(proveedor_id, 0), vigente_desde);

CREATE TABLE tipo_cambio (
  id              bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  fecha           date NOT NULL,
  valor           numeric(12,4) NOT NULL CHECK (valor > 0),   -- ARS por 1 USD
  fuente          text NOT NULL,                -- 'manual Excel', luego 'BNA vendedor'...
  fuente_detalle  text,
  created_at      timestamptz NOT NULL DEFAULT now(),
  UNIQUE (fecha, fuente)
);

CREATE TABLE parametro (
  id                 bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  clave              text NOT NULL CHECK (clave IN ('GG_PCT','GANANCIA_PCT')),
  valor              numeric(6,3) NOT NULL,
  vigente_desde      date NOT NULL,
  estado_validacion  text NOT NULL DEFAULT 'supuesto' CHECK (estado_validacion IN ('supuesto','confirmado')),
  fuente             text NOT NULL,
  fuente_detalle     text,
  created_at         timestamptz NOT NULL DEFAULT now(),
  UNIQUE (clave, vigente_desde)
);

-- ---------- Lo que pasó: cotizaciones ----------
CREATE TABLE cotizacion (
  id                      bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  producto_id             bigint NOT NULL REFERENCES producto(id),
  version                 integer NOT NULL CHECK (version >= 1),
  estado                  text NOT NULL CHECK (estado IN ('borrador','vigente','historica')),
  fecha                   date NOT NULL,         -- fecha de los precios usados
  tipo_cambio_id          bigint REFERENCES tipo_cambio(id),
  tc_valor                numeric(12,4) NOT NULL, -- copiado (foto)
  gg_pct                  numeric(6,3) NOT NULL,  -- copiado (foto)
  subtotal_ars            numeric(14,4),          -- calculados por el backend
  gg_ars                  numeric(14,4),
  costo_ars               numeric(14,4),
  costo_usd               numeric(14,4),
  origen                  text NOT NULL CHECK (origen IN ('migracion','manual','recotizacion')),
  basada_en_cotizacion_id bigint REFERENCES cotizacion(id),  -- de qué producto/versión se copió
  creado_por              text,                   -- id de usuario de Better Auth
  motivo                  text,
  dato_origen             jsonb,                  -- B, D, E, AI viejo, AJ/AK, comentarios
  created_at              timestamptz NOT NULL DEFAULT now(),
  UNIQUE (producto_id, version)
);
CREATE UNIQUE INDEX cotizacion_una_vigente ON cotizacion (producto_id) WHERE estado = 'vigente';

CREATE TABLE cotizacion_linea (
  id                   bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  cotizacion_id        bigint NOT NULL REFERENCES cotizacion(id),
  etapa_id             bigint NOT NULL REFERENCES etapa(id),
  orden                smallint NOT NULL DEFAULT 1,
  material_id          bigint REFERENCES material(id),
  precio_material_id   bigint REFERENCES precio_material(id),
  concepto             text NOT NULL,
  cantidad             numeric(10,4) CHECK (cantidad >= 0),  -- NULL = dato faltante
  unidad               text NOT NULL,
  precio_unitario      numeric(14,4) NOT NULL,   -- en su moneda original (foto)
  moneda               char(3) NOT NULL CHECK (moneda IN ('ARS','USD')),
  precio_unitario_ars  numeric(14,4) NOT NULL,   -- convertido con tc de la cotización
  total_ars            numeric(14,4) NOT NULL,
  incluye_desperdicio  boolean,                  -- null = no se sabe
  origen_valor         text NOT NULL CHECK (origen_valor IN ('migrado','sugerido','manual','copiado')),
  fuente_detalle       text,                     -- 'Marroquineria1!J22'
  nota                 text,
  CHECK (precio_material_id IS NULL OR material_id IS NOT NULL)
);
CREATE INDEX cotizacion_linea_cot_idx ON cotizacion_linea (cotizacion_id);

CREATE TABLE marca_calidad (
  id             bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  producto_id    bigint REFERENCES producto(id),
  cotizacion_id  bigint REFERENCES cotizacion(id),
  material_id    bigint REFERENCES material(id),
  tipo           text NOT NULL,
  detalle        text,
  celda_excel    text,
  resuelta       boolean NOT NULL DEFAULT false,
  resuelta_por   text,
  resuelta_at    timestamptz,
  created_at     timestamptz NOT NULL DEFAULT now(),
  CHECK (num_nonnulls(producto_id, cotizacion_id, material_id) >= 1)
);

-- ---------- Datos semilla (los del Excel) ----------
INSERT INTO etapa (codigo,nombre,grupo,orden,requiere_material) VALUES
 ('CUERO','Cuero (capa externa)','material exterior',1,true),
 ('FORRO','Forro (capa interna)','material interior',2,true),
 ('HERRAJES','Herrajes, hilo y cemento','accesorios y detalles',3,false),
 ('REFUERZO','Refuerzos (flex, goma EVA)','accesorios y detalles',4,true),
 ('CORTE','Corte','refinamiento',5,false),
 ('REB','Reb (supuesto: rebajado)','refinamiento',6,false),
 ('PREP','Prep (supuesto: preparación)','refinamiento',7,false),
 ('MANO_OBRA','Mano de obra (estimación)','mano de obra',8,false);

INSERT INTO material (nombre,tipo,unidad_consumo,codigo_excel,cotizable,notas) VALUES
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
 ('Cartón 1,5 mm','refuerzo','m2','insumo:W10',true,'No lo usa ninguna fórmula.');

INSERT INTO proveedor (nombre,categorias) VALUES ('Rouez','refuerzos'),('Acropol','refuerzos');

INSERT INTO precio_material (material_id,proveedor_id,precio,moneda,unidad_precio,presentacion,precio_presentacion,contenido_presentacion,vigente_desde,fuente,fuente_detalle)
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
JOIN material m ON m.codigo_excel = v.cod
LEFT JOIN proveedor p ON p.nombre = v.prov;

INSERT INTO tipo_cambio (fecha,valor,fuente,fuente_detalle) VALUES ('2026-09-01',1545,'manual Excel','Marroquineria1!G15');
INSERT INTO parametro (clave,valor,vigente_desde,fuente,fuente_detalle) VALUES
 ('GG_PCT',11,'2026-09-01','excel_migracion','Marroquineria1!G16'),
 ('GANANCIA_PCT',0,'2026-09-01','excel_migracion','Marroquineria1!G17 (no la usa ninguna fórmula)');
INSERT INTO categoria (nombre) VALUES ('Portafolio'),('Cartera'),('Billetera');
COMMIT;
