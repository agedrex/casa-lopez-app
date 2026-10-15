"""The provisional DER v1, phase one only; schema creation belongs to Alembic."""

from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    BigInteger, Boolean, CHAR, CheckConstraint, Date, DateTime, ForeignKey,
    Identity, Index, Integer, MetaData, Numeric, SmallInteger, Text,
    UniqueConstraint, func, text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    metadata = MetaData(schema="costos", naming_convention={
        "pk": "pk_%(table_name)s",
        "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
        "uq": "uq_%(table_name)s_%(column_0_name)s",
        "ck": "ck_%(table_name)s_%(constraint_name)s",
        "ix": "ix_%(table_name)s_%(column_0_name)s",
    })


class IdentityAndCreatedAt:
    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Categoria(IdentityAndCreatedAt, Base):
    __tablename__ = "categoria"
    nombre: Mapped[str] = mapped_column(Text, unique=True)
    activo: Mapped[bool] = mapped_column(Boolean, server_default=text("true"))


class Producto(IdentityAndCreatedAt, Base):
    __tablename__ = "producto"
    __table_args__ = (
        CheckConstraint("tamano IN ('chico','mediano','grande')", name="tamano"),
        CheckConstraint("producto_base_id IS NULL OR producto_base_id <> id", name="base_distinta"),
        CheckConstraint("estado IN ('activo','archivado')", name="estado"),
    )
    codigo_modelo: Mapped[str | None] = mapped_column(Text, index=True)
    nombre: Mapped[str] = mapped_column(Text)
    nombre_original: Mapped[str | None] = mapped_column(Text)
    categoria_id: Mapped[int | None] = mapped_column(ForeignKey("costos.categoria.id"))
    tamano: Mapped[str | None] = mapped_column(Text)
    producto_base_id: Mapped[int | None] = mapped_column(ForeignKey("costos.producto.id"))
    estado: Mapped[str] = mapped_column(Text, server_default=text("'activo'"))
    codigo_erp: Mapped[str | None] = mapped_column(Text, unique=True)
    fila_excel: Mapped[int | None] = mapped_column(Integer, unique=True)
    notas: Mapped[str | None] = mapped_column(Text)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class Etapa(IdentityAndCreatedAt, Base):
    __tablename__ = "etapa"
    codigo: Mapped[str] = mapped_column(Text, unique=True)
    nombre: Mapped[str] = mapped_column(Text)
    grupo: Mapped[str] = mapped_column(Text)
    orden: Mapped[int] = mapped_column(SmallInteger, unique=True)
    requiere_material: Mapped[bool] = mapped_column(Boolean)


class Material(IdentityAndCreatedAt, Base):
    __tablename__ = "material"
    __table_args__ = (
        CheckConstraint("tipo IN ('cuero','forro','refuerzo','insumo')", name="tipo"),
        CheckConstraint("unidad_consumo IN ('m2','cm','unidad')", name="unidad_consumo"),
    )
    nombre: Mapped[str] = mapped_column(Text)
    tipo: Mapped[str] = mapped_column(Text)
    unidad_consumo: Mapped[str] = mapped_column(Text)
    codigo_excel: Mapped[str | None] = mapped_column(Text, unique=True)
    cotizable: Mapped[bool] = mapped_column(Boolean, server_default=text("true"))
    activo: Mapped[bool] = mapped_column(Boolean, server_default=text("true"))
    notas: Mapped[str | None] = mapped_column(Text)


class Proveedor(IdentityAndCreatedAt, Base):
    __tablename__ = "proveedor"
    nombre: Mapped[str] = mapped_column(Text)
    cuit: Mapped[str | None] = mapped_column(Text, unique=True)
    direccion: Mapped[str | None] = mapped_column(Text)
    telefono: Mapped[str | None] = mapped_column(Text)
    contacto: Mapped[str | None] = mapped_column(Text)
    categorias: Mapped[str | None] = mapped_column(Text)
    notas: Mapped[str | None] = mapped_column(Text)
    activo: Mapped[bool] = mapped_column(Boolean, server_default=text("true"))


class PrecioMaterial(IdentityAndCreatedAt, Base):
    __tablename__ = "precio_material"
    __table_args__ = (
        CheckConstraint("precio >= 0", name="precio_no_negativo"),
        CheckConstraint("moneda IN ('ARS','USD')", name="moneda"),
        CheckConstraint("unidad_precio IN ('m2','cm','unidad')", name="unidad_precio"),
        CheckConstraint("fuente IN ('excel_migracion','manual','proveedor')", name="fuente"),
        CheckConstraint("(presentacion IS NULL) = (precio_presentacion IS NULL)", name="presentacion_completa"),
    )
    material_id: Mapped[int] = mapped_column(ForeignKey("costos.material.id"))
    proveedor_id: Mapped[int | None] = mapped_column(ForeignKey("costos.proveedor.id"))
    precio: Mapped[Decimal] = mapped_column(Numeric(14, 4, asdecimal=True))
    moneda: Mapped[str] = mapped_column(CHAR(3))
    unidad_precio: Mapped[str] = mapped_column(Text)
    presentacion: Mapped[str | None] = mapped_column(Text)
    precio_presentacion: Mapped[Decimal | None] = mapped_column(Numeric(14, 4, asdecimal=True))
    contenido_presentacion: Mapped[Decimal | None] = mapped_column(Numeric(10, 4, asdecimal=True))
    vigente_desde: Mapped[date] = mapped_column(Date)
    fuente: Mapped[str] = mapped_column(Text)
    fuente_detalle: Mapped[str | None] = mapped_column(Text)


Index("precio_material_uq", PrecioMaterial.material_id,
      func.coalesce(PrecioMaterial.proveedor_id, text("0")), PrecioMaterial.vigente_desde, unique=True)


class TipoCambio(IdentityAndCreatedAt, Base):
    __tablename__ = "tipo_cambio"
    __table_args__ = (
        CheckConstraint("valor > 0", name="valor_positivo"),
        UniqueConstraint("fecha", "fuente"),
    )
    fecha: Mapped[date] = mapped_column(Date)
    valor: Mapped[Decimal] = mapped_column(Numeric(12, 4, asdecimal=True))
    fuente: Mapped[str] = mapped_column(Text)
    fuente_detalle: Mapped[str | None] = mapped_column(Text)


class Parametro(IdentityAndCreatedAt, Base):
    __tablename__ = "parametro"
    __table_args__ = (
        CheckConstraint("clave IN ('GG_PCT','GANANCIA_PCT')", name="clave"),
        CheckConstraint("estado_validacion IN ('supuesto','confirmado')", name="estado_validacion"),
        UniqueConstraint("clave", "vigente_desde"),
    )
    clave: Mapped[str] = mapped_column(Text)
    valor: Mapped[Decimal] = mapped_column(Numeric(6, 3, asdecimal=True))
    vigente_desde: Mapped[date] = mapped_column(Date)
    estado_validacion: Mapped[str] = mapped_column(Text, server_default=text("'supuesto'"))
    fuente: Mapped[str] = mapped_column(Text)
    fuente_detalle: Mapped[str | None] = mapped_column(Text)


class Cotizacion(IdentityAndCreatedAt, Base):
    __tablename__ = "cotizacion"
    __table_args__ = (
        CheckConstraint("version >= 1", name="version_positiva"),
        CheckConstraint("estado IN ('borrador','vigente','historica')", name="estado"),
        CheckConstraint("origen IN ('migracion','manual','recotizacion')", name="origen"),
        CheckConstraint("estado = 'borrador' OR (subtotal_ars IS NOT NULL AND gg_ars IS NOT NULL AND costo_ars IS NOT NULL AND costo_usd IS NOT NULL)", name="costos_calculados"),
        UniqueConstraint("producto_id", "version"),
        Index("cotizacion_una_vigente", "producto_id", unique=True, postgresql_where=text("estado = 'vigente'")),
    )
    producto_id: Mapped[int] = mapped_column(ForeignKey("costos.producto.id"))
    version: Mapped[int] = mapped_column(Integer)
    estado: Mapped[str] = mapped_column(Text)
    fecha: Mapped[date] = mapped_column(Date)
    tipo_cambio_id: Mapped[int | None] = mapped_column(ForeignKey("costos.tipo_cambio.id"))
    tc_valor: Mapped[Decimal] = mapped_column(Numeric(12, 4, asdecimal=True))
    gg_pct: Mapped[Decimal] = mapped_column(Numeric(6, 3, asdecimal=True))
    subtotal_ars: Mapped[Decimal | None] = mapped_column(Numeric(14, 4, asdecimal=True))
    gg_ars: Mapped[Decimal | None] = mapped_column(Numeric(14, 4, asdecimal=True))
    costo_ars: Mapped[Decimal | None] = mapped_column(Numeric(14, 4, asdecimal=True))
    costo_usd: Mapped[Decimal | None] = mapped_column(Numeric(14, 4, asdecimal=True))
    origen: Mapped[str] = mapped_column(Text)
    basada_en_cotizacion_id: Mapped[int | None] = mapped_column(ForeignKey("costos.cotizacion.id"))
    creado_por: Mapped[str | None] = mapped_column(Text)
    motivo: Mapped[str | None] = mapped_column(Text)
    dato_origen: Mapped[dict[str, Any] | None] = mapped_column(JSONB)


class CotizacionLinea(IdentityAndCreatedAt, Base):
    __tablename__ = "cotizacion_linea"
    __table_args__ = (
        CheckConstraint("precio_material_id IS NULL OR material_id IS NOT NULL", name="precio_requiere_material"),
        CheckConstraint("cantidad >= 0", name="cantidad_no_negativa"),
        CheckConstraint("moneda IN ('ARS','USD')", name="moneda"),
        CheckConstraint("origen_valor IN ('migrado','sugerido','manual','copiado')", name="origen_valor"),
    )
    cotizacion_id: Mapped[int] = mapped_column(ForeignKey("costos.cotizacion.id"), index=True)
    etapa_id: Mapped[int] = mapped_column(ForeignKey("costos.etapa.id"))
    orden: Mapped[int] = mapped_column(SmallInteger, server_default=text("1"))
    material_id: Mapped[int | None] = mapped_column(ForeignKey("costos.material.id"))
    precio_material_id: Mapped[int | None] = mapped_column(ForeignKey("costos.precio_material.id"))
    concepto: Mapped[str] = mapped_column(Text)
    cantidad: Mapped[Decimal | None] = mapped_column(Numeric(10, 4, asdecimal=True))
    unidad: Mapped[str] = mapped_column(Text)
    precio_unitario: Mapped[Decimal] = mapped_column(Numeric(14, 4, asdecimal=True))
    moneda: Mapped[str] = mapped_column(CHAR(3))
    precio_unitario_ars: Mapped[Decimal] = mapped_column(Numeric(14, 4, asdecimal=True))
    total_ars: Mapped[Decimal] = mapped_column(Numeric(14, 4, asdecimal=True))
    incluye_desperdicio: Mapped[bool | None] = mapped_column(Boolean)
    origen_valor: Mapped[str] = mapped_column(Text)
    fuente_detalle: Mapped[str | None] = mapped_column(Text)
    nota: Mapped[str | None] = mapped_column(Text)


class MarcaCalidad(IdentityAndCreatedAt, Base):
    __tablename__ = "marca_calidad"
    __table_args__ = (
        CheckConstraint("num_nonnulls(producto_id, cotizacion_id, material_id) >= 1", name="alguna_entidad"),
    )
    producto_id: Mapped[int | None] = mapped_column(ForeignKey("costos.producto.id"))
    cotizacion_id: Mapped[int | None] = mapped_column(ForeignKey("costos.cotizacion.id"))
    material_id: Mapped[int | None] = mapped_column(ForeignKey("costos.material.id"))
    tipo: Mapped[str] = mapped_column(Text)
    detalle: Mapped[str | None] = mapped_column(Text)
    celda_excel: Mapped[str | None] = mapped_column(Text)
    resuelta: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
    resuelta_por: Mapped[str | None] = mapped_column(Text)
    resuelta_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
