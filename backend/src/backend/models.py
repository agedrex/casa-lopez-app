"""DER v3 from the `Diccionario` sheet of Plantilla Costos Casa Lopez v4.1.

Only columns marked `carga` / `clave` are persisted; columns marked
`calculada (la app recalcula)` are computed by the app, except in `cotizacion`,
which stores a calculated snapshot. Schema creation belongs to Alembic.
"""

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger, Boolean, CHAR, CheckConstraint, Date, DateTime, ForeignKey,
    Identity, Index, Integer, MetaData, Numeric, SmallInteger, Text,
    UniqueConstraint, func, text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    metadata = MetaData(schema="costos", naming_convention={
        "pk": "pk_%(table_name)s",
        "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
        "uq": "uq_%(table_name)s_%(column_0_name)s",
        "ck": "ck_%(table_name)s_%(constraint_name)s",
        "ix": "ix_%(table_name)s_%(column_0_name)s",
    })


def money() -> Numeric:
    return Numeric(14, 4, asdecimal=True)


def quantity() -> Numeric:
    return Numeric(12, 6, asdecimal=True)


def exchange_rate() -> Numeric:
    return Numeric(12, 4, asdecimal=True)


def pct() -> Numeric:
    return Numeric(6, 3, asdecimal=True)


def one_of(column: str, values: tuple[str, ...], name: str) -> CheckConstraint:
    """CHECK built from a dropdown list of the sheet."""
    listed = ",".join(f"'{value}'" for value in values)
    return CheckConstraint(f"{column} IN ({listed})", name=name)


ARS_USD = ("ARS", "USD")
# SUPUESTO: validar. The sheet describes the unit as "m2, juego, unidad, USD (solo herrajes migrados), cm..."
# (open list); these are the values in use, extend it with a migration when Casa López adds one.
UNITS = ("m2", "cm", "juego", "unidad", "USD")
LOT_STATES = ("PLANIFICADA", "EN_CORTE", "CORTADA", "EN_CONFECCION", "LISTA", "CERRADA")
WHERE_MADE = ("EXTERNA", "INTERNA")


class IdentityAndCreatedAt:
    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class BusinessKey(IdentityAndCreatedAt):
    """The `codigo` of the sheet is the business key: unique and never changes."""
    codigo: Mapped[str] = mapped_column(Text, unique=True)


# --- Reference tables -------------------------------------------------------

class Etapa(BusinessKey, Base):
    __tablename__ = "etapa"
    __table_args__ = (one_of("tipo", ("MATERIAL", "TAREA_INTERNA", "CONFECCION"), "tipo"),)
    orden: Mapped[int] = mapped_column(SmallInteger, unique=True)
    que_es_y_de_donde_viene: Mapped[str | None] = mapped_column(Text)
    tipo: Mapped[str] = mapped_column(Text)
    va_siempre: Mapped[bool] = mapped_column(Boolean)
    tratamiento: Mapped[str | None] = mapped_column(Text)
    nota: Mapped[str | None] = mapped_column(Text)


class Categoria(BusinessKey, Base):
    __tablename__ = "categoria"
    nombre: Mapped[str] = mapped_column(Text, unique=True)
    nota: Mapped[str | None] = mapped_column(Text)


class Color(BusinessKey, Base):
    __tablename__ = "color"
    nombre: Mapped[str] = mapped_column(Text, unique=True)
    nota: Mapped[str | None] = mapped_column(Text)


class Persona(BusinessKey, Base):
    __tablename__ = "persona"
    __table_args__ = (
        one_of("rol", ("CONSUMO_MOLDES", "CORTE", "CONFECCION", "VENTAS", "ENCARGADO", "ADMINISTRACION", "OTRO"), "rol"),
        one_of("vinculo", ("SUELDO_FIJO", "OTRO"), "vinculo"),
    )
    nombre: Mapped[str] = mapped_column(Text)
    rol: Mapped[str] = mapped_column(Text)
    vinculo: Mapped[str] = mapped_column(Text)
    activo: Mapped[bool] = mapped_column(Boolean, server_default=text("true"))
    nota: Mapped[str | None] = mapped_column(Text)


class Taller(BusinessKey, Base):
    __tablename__ = "taller"
    nombre: Mapped[str] = mapped_column(Text, unique=True)
    cuit: Mapped[str | None] = mapped_column(Text, unique=True)
    telefono: Mapped[str | None] = mapped_column(Text)
    direccion: Mapped[str | None] = mapped_column(Text)
    contacto: Mapped[str | None] = mapped_column(Text)
    activo: Mapped[bool] = mapped_column(Boolean, server_default=text("true"))
    nota: Mapped[str | None] = mapped_column(Text)


class Impuesto(BusinessKey, Base):
    __tablename__ = "impuesto"
    __table_args__ = (CheckConstraint("alicuota >= 0", name="alicuota_no_negativa"),)
    nombre: Mapped[str] = mapped_column(Text)
    alicuota: Mapped[Decimal | None] = mapped_column(pct())
    # SUPUESTO: validar. `base` has no dropdown in the sheet (data: COMPRA, VENTA, RESULTADO).
    base: Mapped[str | None] = mapped_column(Text)
    es_costo_del_producto: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
    nota: Mapped[str | None] = mapped_column(Text)


class Parametro(BusinessKey, Base):
    """`codigo` is the sheet's "Código en la base" (technical name used by the app and n8n)."""
    __tablename__ = "parametro"
    __table_args__ = (CheckConstraint("valor IS NULL OR valor_texto IS NULL", name="un_solo_valor"),)
    constante: Mapped[str] = mapped_column(Text)
    # SUPUESTO: validar. The sheet mixes numbers (1545, 0.11) and text (2026-10) in one column.
    valor: Mapped[Decimal | None] = mapped_column(money())
    valor_texto: Mapped[str | None] = mapped_column(Text)
    unidad: Mapped[str | None] = mapped_column(Text)
    que_es: Mapped[str | None] = mapped_column(Text)
    fuente_estado: Mapped[str | None] = mapped_column(Text)


class Material(BusinessKey, Base):
    __tablename__ = "material"
    __table_args__ = (
        one_of("unidad_de_consumo", UNITS, "unidad_de_consumo"),
        CheckConstraint("desperdicio_manual IS NULL OR desperdicio_manual >= 0", name="desperdicio_no_negativo"),
    )
    nombre: Mapped[str] = mapped_column(Text)
    nombre_corto: Mapped[str | None] = mapped_column(Text)
    etapa_id: Mapped[int] = mapped_column(ForeignKey("costos.etapa.id"), index=True)
    unidad_de_consumo: Mapped[str] = mapped_column(Text)
    cotizable: Mapped[bool] = mapped_column(Boolean, server_default=text("true"))
    controla_inventario: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
    desperdicio_manual: Mapped[Decimal | None] = mapped_column(pct())
    ref_excel_viejo: Mapped[str | None] = mapped_column(Text)
    nota: Mapped[str | None] = mapped_column(Text)


class Molde(BusinessKey, Base):
    __tablename__ = "molde"
    __table_args__ = (
        CheckConstraint("ancho_cm >= 0 AND alto_cm >= 0", name="medidas_no_negativas"),
        CheckConstraint("area_medida_m2 IS NULL OR area_medida_m2 >= 0", name="area_no_negativa"),
    )
    figura: Mapped[str | None] = mapped_column(Text)
    ancho_cm: Mapped[Decimal | None] = mapped_column(quantity())
    alto_cm: Mapped[Decimal | None] = mapped_column(quantity())
    area_medida_m2: Mapped[Decimal | None] = mapped_column(quantity())
    version: Mapped[str | None] = mapped_column(Text)
    medido_por_id: Mapped[int | None] = mapped_column(ForeignKey("costos.persona.id"))
    nota: Mapped[str | None] = mapped_column(Text)


# --- Catalog: models, products, recipe ---------------------------------------

class Modelo(BusinessKey, Base):
    __tablename__ = "modelo"
    __table_args__ = (
        one_of("tamano", ("CHICO", "MEDIANO", "GRANDE"), "tamano"),
        one_of("origen_de_los_consumos", ("EXCEL", "MOLDE", "ESTIMADO", "MEDIDO"), "origen_de_los_consumos"),
        CheckConstraint(
            "coalesce(cuero_m2_por_unidad, 0) >= 0 AND coalesce(forro_m2_por_unidad, 0) >= 0 "
            "AND coalesce(flex_m2_por_unidad, 0) >= 0 AND coalesce(goma_eva_m2_por_unidad, 0) >= 0 "
            "AND coalesce(herrajes_usd_por_unidad, 0) >= 0 AND coalesce(hilo_y_cemento, 0) >= 0",
            name="consumos_no_negativos",
        ),
    )
    # Two models must not share a name: the sheet asks to "agregar algo que los distinga".
    nombre_del_modelo: Mapped[str] = mapped_column(Text, unique=True)
    categoria_id: Mapped[int | None] = mapped_column(ForeignKey("costos.categoria.id"), index=True)
    modelo_excel_viejo: Mapped[str | None] = mapped_column(Text)
    fila_excel_viejo: Mapped[int | None] = mapped_column(Integer)
    # NULL = missing data (e.g. lagarto/yacaré rows of the old Excel), 0 = "no lleva".
    cuero_m2_por_unidad: Mapped[Decimal | None] = mapped_column(quantity())
    forro_id: Mapped[int | None] = mapped_column(ForeignKey("costos.material.id"))
    forro_m2_por_unidad: Mapped[Decimal | None] = mapped_column(quantity())
    flex_m2_por_unidad: Mapped[Decimal | None] = mapped_column(quantity())
    goma_eva_m2_por_unidad: Mapped[Decimal | None] = mapped_column(quantity())
    herrajes_usd_por_unidad: Mapped[Decimal | None] = mapped_column(money())
    hilo_y_cemento: Mapped[Decimal | None] = mapped_column(quantity())
    confeccion_estimada_ars: Mapped[Decimal | None] = mapped_column(money())
    horas_de_confeccion: Mapped[Decimal | None] = mapped_column(quantity())
    origen_de_los_consumos: Mapped[str | None] = mapped_column(Text)
    validado: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
    nota: Mapped[str | None] = mapped_column(Text)
    excel_viejo_subtotal_af: Mapped[Decimal | None] = mapped_column(money())
    excel_viejo_corte_reb_prep: Mapped[Decimal | None] = mapped_column(money())
    tamano: Mapped[str | None] = mapped_column(Text)


class Producto(BusinessKey, Base):
    __tablename__ = "producto"
    __table_args__ = (
        one_of("quien_lo_confecciona", WHERE_MADE, "quien_lo_confecciona"),
        one_of("estado_del_ciclo", ("EN_DEFINICION", "COTIZADO", "EN_PRODUCCION", "PRODUCIDO"), "estado_del_ciclo"),
    )
    # SUPUESTO: validar. modelo_id is nullable because "un kit sin modelo" carries its name in nombre_propio.
    modelo_id: Mapped[int | None] = mapped_column(ForeignKey("costos.modelo.id"), index=True)
    cuero_id: Mapped[int | None] = mapped_column(ForeignKey("costos.material.id"))
    color_id: Mapped[int | None] = mapped_column(ForeignKey("costos.color.id"))
    quien_lo_confecciona: Mapped[str | None] = mapped_column(Text)
    # SUPUESTO: validar. EN_DEFINICION as the default is the first state of the cycle.
    estado_del_ciclo: Mapped[str] = mapped_column(Text, server_default=text("'EN_DEFINICION'"))
    fecha_de_alta: Mapped[date | None] = mapped_column(Date)
    fecha_de_recotizacion: Mapped[date | None] = mapped_column(Date)
    fecha_de_cierre: Mapped[date | None] = mapped_column(Date)
    nombre_propio: Mapped[str | None] = mapped_column(Text)
    es_kit: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
    nota: Mapped[str | None] = mapped_column(Text)


class RecetaLinea(BusinessKey, Base):
    """Only the EXTRA lines are persisted; the MODELO lines are calculated from `modelo`."""
    __tablename__ = "receta_linea"
    __table_args__ = (
        one_of("origen", ("EXTRA",), "origen"),
        CheckConstraint("consumo_neto_por_unidad >= 0", name="consumo_no_negativo"),
    )
    origen: Mapped[str] = mapped_column(Text, server_default=text("'EXTRA'"))
    producto_id: Mapped[int] = mapped_column(ForeignKey("costos.producto.id"), index=True)
    material_id: Mapped[int] = mapped_column(ForeignKey("costos.material.id"))
    color_id: Mapped[int | None] = mapped_column(ForeignKey("costos.color.id"))
    consumo_neto_por_unidad: Mapped[Decimal] = mapped_column(quantity())
    nota: Mapped[str | None] = mapped_column(Text)


class KitComponente(IdentityAndCreatedAt, Base):
    __tablename__ = "kit_componente"
    __table_args__ = (
        CheckConstraint("cantidad >= 0", name="cantidad_no_negativa"),
        CheckConstraint("kit_id <> componente_id", name="kit_distinto_del_componente"),
    )
    kit_id: Mapped[int] = mapped_column(ForeignKey("costos.producto.id"), index=True)
    componente_id: Mapped[int] = mapped_column(ForeignKey("costos.producto.id"))
    cantidad: Mapped[Decimal] = mapped_column(quantity())


class ModeloMolde(IdentityAndCreatedAt, Base):
    __tablename__ = "modelo_molde"
    __table_args__ = (
        one_of("capa", ("EXTERIOR", "INTERIOR", "FLEX", "GOMA_EVA"), "capa"),
        CheckConstraint("cantidad >= 0", name="cantidad_no_negativa"),
    )
    modelo_id: Mapped[int] = mapped_column(ForeignKey("costos.modelo.id"), index=True)
    molde_id: Mapped[int] = mapped_column(ForeignKey("costos.molde.id"))
    capa: Mapped[str] = mapped_column(Text)
    cantidad: Mapped[Decimal] = mapped_column(quantity())
    nota: Mapped[str | None] = mapped_column(Text)


# --- Prices and exchange rate (append-only: a new price is a new row) ---------

class PrecioMaterial(BusinessKey, Base):
    __tablename__ = "precio_material"
    __table_args__ = (
        CheckConstraint("precio >= 0", name="precio_no_negativo"),
        one_of("moneda", ARS_USD, "moneda"),
        one_of("unidad_del_precio", UNITS, "unidad_del_precio"),
    )
    material_id: Mapped[int] = mapped_column(ForeignKey("costos.material.id"))
    color_id: Mapped[int | None] = mapped_column(ForeignKey("costos.color.id"))
    # The supplier lives in an external file (PRV-0001...), so it is kept as its code.
    proveedor: Mapped[str | None] = mapped_column(Text)
    precio: Mapped[Decimal] = mapped_column(money())
    moneda: Mapped[str] = mapped_column(CHAR(3))
    unidad_del_precio: Mapped[str] = mapped_column(Text)
    iva_incluido: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
    vigente_desde: Mapped[date] = mapped_column(Date)
    nota_fuente: Mapped[str | None] = mapped_column(Text)


# A NULL color means "all colors": it must not allow two prices on the same date.
Index("precio_material_uq", PrecioMaterial.material_id,
      func.coalesce(PrecioMaterial.color_id, text("0")), PrecioMaterial.vigente_desde, unique=True)


class TipoCambio(IdentityAndCreatedAt, Base):
    __tablename__ = "tipo_cambio"
    __table_args__ = (
        CheckConstraint("ars_por_usd > 0", name="valor_positivo"),
        one_of("tipo", ("VENDEDOR", "COMPRADOR"), "tipo"),
        one_of("fuente", ("BNA", "EXCEL_VIEJO", "MANUAL"), "fuente"),
    )
    fecha: Mapped[date] = mapped_column(Date)
    ars_por_usd: Mapped[Decimal] = mapped_column(exchange_rate())
    fuente: Mapped[str] = mapped_column(Text)
    # SUPUESTO: validar con Gerardo. The Excel row has no tipo yet, so it is nullable.
    tipo: Mapped[str | None] = mapped_column(Text)
    nota: Mapped[str | None] = mapped_column(Text)


Index("tipo_cambio_uq", TipoCambio.fecha, func.coalesce(TipoCambio.tipo, text("''")), TipoCambio.fuente, unique=True)


# --- Production orders ---------------------------------------------------------

class OrdenFabricacion(BusinessKey, Base):
    """A "lote": one batch sent to a workshop or made in house."""
    __tablename__ = "orden_fabricacion"
    __table_args__ = (
        one_of("donde_se_hace", WHERE_MADE, "donde_se_hace"),
        one_of("estado", LOT_STATES, "estado"),
    )
    donde_se_hace: Mapped[str] = mapped_column(Text)
    taller_id: Mapped[int | None] = mapped_column(ForeignKey("costos.taller.id"))
    persona_id: Mapped[int | None] = mapped_column(ForeignKey("costos.persona.id"))
    fecha_de_envio: Mapped[date | None] = mapped_column(Date)
    fecha_de_entrega: Mapped[date | None] = mapped_column(Date)
    estado: Mapped[str] = mapped_column(Text)
    nota: Mapped[str | None] = mapped_column(Text)


class OrdenItem(BusinessKey, Base):
    """One product inside a lot. Asked and paid workshop prices are kept apart."""
    __tablename__ = "orden_item"
    __table_args__ = (
        CheckConstraint("cantidad >= 0", name="cantidad_no_negativa"),
        CheckConstraint("coalesce(taller_precio_cotizado_por_unidad_ars, 0) >= 0 "
                        "AND coalesce(taller_precio_pagado_por_unidad_ars, 0) >= 0", name="precios_no_negativos"),
    )
    orden_fabricacion_id: Mapped[int] = mapped_column(ForeignKey("costos.orden_fabricacion.id"), index=True)
    producto_id: Mapped[int] = mapped_column(ForeignKey("costos.producto.id"), index=True)
    cantidad: Mapped[Decimal] = mapped_column(quantity())
    taller_precio_cotizado_por_unidad_ars: Mapped[Decimal | None] = mapped_column(money())
    taller_precio_pagado_por_unidad_ars: Mapped[Decimal | None] = mapped_column(money())
    nota: Mapped[str | None] = mapped_column(Text)


class OrdenEstado(IdentityAndCreatedAt, Base):
    __tablename__ = "orden_estado"
    __table_args__ = (one_of("estado", LOT_STATES, "estado"),)
    orden_fabricacion_id: Mapped[int] = mapped_column(ForeignKey("costos.orden_fabricacion.id"), index=True)
    estado: Mapped[str] = mapped_column(Text)
    fecha: Mapped[date] = mapped_column(Date)
    quien_id: Mapped[int | None] = mapped_column(ForeignKey("costos.persona.id"))


class RegistroTarea(IdentityAndCreatedAt, Base):
    __tablename__ = "registro_tarea"
    __table_args__ = (
        one_of("tarea", ("CORTE", "CONFECCION"), "tarea"),
        CheckConstraint("unidades >= 0 AND coalesce(horas, 0) >= 0", name="no_negativos"),
    )
    orden_fabricacion_id: Mapped[int] = mapped_column(ForeignKey("costos.orden_fabricacion.id"), index=True)
    persona_id: Mapped[int] = mapped_column(ForeignKey("costos.persona.id"))
    tarea: Mapped[str] = mapped_column(Text)
    unidades: Mapped[Decimal] = mapped_column(quantity())
    horas: Mapped[Decimal | None] = mapped_column(quantity())
    fecha: Mapped[date] = mapped_column(Date)


class GastoPeriodo(BusinessKey, Base):
    """Monthly fixed cost. A new month is a new block of rows."""
    __tablename__ = "gasto_periodo"
    __table_args__ = (
        CheckConstraint("periodo ~ '^[0-9]{4}-(0[1-9]|1[0-2])$'", name="periodo_aaaa_mm"),
        one_of("fabrica_o_tienda", ("FABRICA", "TIENDA"), "fabrica_o_tienda"),
        one_of("categoria", ("SUELDOS", "CARGAS_SOCIALES", "ALQUILER", "SERVICIOS", "IMPUESTOS_FIJOS", "OTROS"), "categoria"),
        CheckConstraint("monto_ars_del_mes IS NULL OR monto_ars_del_mes >= 0", name="monto_no_negativo"),
    )
    periodo: Mapped[str] = mapped_column(Text, index=True)
    concepto: Mapped[str] = mapped_column(Text)
    fabrica_o_tienda: Mapped[str] = mapped_column(Text)
    categoria: Mapped[str] = mapped_column(Text)
    persona_id: Mapped[int | None] = mapped_column(ForeignKey("costos.persona.id"))
    # NULL = amount still pending (the sheet lists concepts without a figure).
    monto_ars_del_mes: Mapped[Decimal | None] = mapped_column(money())
    ficticio: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
    nota_fuente: Mapped[str | None] = mapped_column(Text)


# --- Leather inventory ------------------------------------------------------------

class PiezaCuero(BusinessKey, Base):
    __tablename__ = "pieza_cuero"
    __table_args__ = (
        one_of("moneda", ARS_USD, "moneda"),
        one_of("estado", ("ENTERA", "EN_USO", "RETAZO", "CERRADA"), "estado"),
        CheckConstraint("m2_iniciales >= 0 AND coalesce(precio_pagado_por_m2, 0) >= 0", name="no_negativos"),
    )
    material_id: Mapped[int] = mapped_column(ForeignKey("costos.material.id"), index=True)
    color_id: Mapped[int | None] = mapped_column(ForeignKey("costos.color.id"))
    fecha_de_compra: Mapped[date | None] = mapped_column(Date)
    # The supplier lives in an external file (PRV-0001...), so it is kept as its code.
    proveedor: Mapped[str | None] = mapped_column(Text)
    m2_iniciales: Mapped[Decimal] = mapped_column(quantity())
    precio_pagado_por_m2: Mapped[Decimal | None] = mapped_column(money())
    moneda: Mapped[str | None] = mapped_column(CHAR(3))
    estado: Mapped[str] = mapped_column(Text)


class MovimientoCuero(IdentityAndCreatedAt, Base):
    __tablename__ = "movimiento_cuero"
    __table_args__ = (
        one_of("tipo", ("CORTE", "DESPERDICIO", "AJUSTE", "ENTRADA"), "tipo"),
        # The sheet marks the lot/product line as mandatory for CORTE rows.
        CheckConstraint("tipo <> 'CORTE' OR orden_item_id IS NOT NULL", name="corte_requiere_orden_item"),
    )
    fecha: Mapped[date] = mapped_column(Date)
    pieza_cuero_id: Mapped[int] = mapped_column(ForeignKey("costos.pieza_cuero.id"), index=True)
    tipo: Mapped[str] = mapped_column(Text)
    # Negative when leather leaves the hide: -0.25 if 0.25 m2 were cut.
    m2: Mapped[Decimal] = mapped_column(quantity())
    orden_item_id: Mapped[int | None] = mapped_column(ForeignKey("costos.orden_item.id"))
    unidades: Mapped[Decimal | None] = mapped_column(quantity())
    registro_id: Mapped[int | None] = mapped_column(ForeignKey("costos.persona.id"))


class ConteoInventario(IdentityAndCreatedAt, Base):
    __tablename__ = "conteo_inventario"
    __table_args__ = (
        CheckConstraint("periodo ~ '^[0-9]{4}-(0[1-9]|1[0-2])$'", name="periodo_aaaa_mm"),
        one_of("momento", ("INICIO", "CIERRE"), "momento"),
        CheckConstraint("m2_contados >= 0", name="m2_no_negativo"),
    )
    periodo: Mapped[str] = mapped_column(Text)
    momento: Mapped[str] = mapped_column(Text)
    material_id: Mapped[int] = mapped_column(ForeignKey("costos.material.id"))
    color_id: Mapped[int | None] = mapped_column(ForeignKey("costos.color.id"))
    m2_contados: Mapped[Decimal] = mapped_column(quantity())


# --- Calculated snapshot ----------------------------------------------------------

class Cotizacion(IdentityAndCreatedAt, Base):
    """Snapshot of a calculated quote; the cost engine writes it, nobody edits it."""
    __tablename__ = "cotizacion"
    __table_args__ = (
        one_of("tipo", ("INICIAL", "RECOTIZACION", "FINAL"), "tipo"),
        UniqueConstraint("producto_id", "fecha", "tipo", name="uq_cotizacion_producto_fecha_tipo"),
        CheckConstraint("dolar > 0", name="dolar_positivo"),
    )
    producto_id: Mapped[int] = mapped_column(ForeignKey("costos.producto.id"), index=True)
    tipo: Mapped[str] = mapped_column(Text)
    fecha: Mapped[date] = mapped_column(Date)
    dolar: Mapped[Decimal] = mapped_column(exchange_rate())
    cuero: Mapped[Decimal] = mapped_column(money(), server_default=text("0"))
    forro: Mapped[Decimal] = mapped_column(money(), server_default=text("0"))
    flex: Mapped[Decimal] = mapped_column(money(), server_default=text("0"))
    goma_eva: Mapped[Decimal] = mapped_column(money(), server_default=text("0"))
    herrajes: Mapped[Decimal] = mapped_column(money(), server_default=text("0"))
    hilo_cemento: Mapped[Decimal] = mapped_column(money(), server_default=text("0"))
    corte: Mapped[Decimal] = mapped_column(money(), server_default=text("0"))
    confeccion: Mapped[Decimal] = mapped_column(money(), server_default=text("0"))
    subtotal_etapas: Mapped[Decimal] = mapped_column(money())
    componentes_kit: Mapped[Decimal] = mapped_column(money(), server_default=text("0"))
    iva_compras: Mapped[Decimal] = mapped_column(money(), server_default=text("0"))
    arreglos: Mapped[Decimal] = mapped_column(money(), server_default=text("0"))
    total_ars: Mapped[Decimal] = mapped_column(money())
    total_usd: Mapped[Decimal] = mapped_column(money())
    # SUPUESTO: validar. The sheet gives no list of values for the quote "Estado".
    estado: Mapped[str | None] = mapped_column(Text)
