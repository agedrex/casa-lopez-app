"""Costing API: read and load endpoints. Routers only validate input and call `servicios`.

Every route requires a signed-in user (see auth.py; fail-closed without a verifier). Reads are open to
any signed-in role; every POST also needs the role `admin` or `cotizador` (`consulta` gets 403), except the
admin area (parameters, people, catalogs, model consumptions), which needs `admin`.
Calculated values (names, categories, totals, costs) are never accepted from the client:
request models forbid unknown fields. Money leaves as strings because the response models
keep Decimal and pydantic serializes it as text in JSON.
"""

import importlib.metadata
import logging
import threading
import time
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from functools import lru_cache
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, FastAPI, HTTPException, Query, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy.orm import Session

from backend import servicios, sheets_client
from backend.auth import Usuario, require_role, require_user
from backend.database import get_session
from backend.models import ARS_USD, LOT_STATES, UNITS, WHERE_MADE
from backend.sheets_client import ErrorDeSheets, SheetsClient
from backend.sheets_export import NOMBRES_DE_PESTANAS, Fuente, FuenteSQL, construir_tab, construir_tabs

logger = logging.getLogger("uvicorn.error")

router = APIRouter(dependencies=[Depends(require_user)])
# Roles that may write. `require_role` builds on `require_user`, so no session still answers 401, not 403.
ESCRITURA = [Depends(require_role("admin", "cotizador"))]
# The admin area: only `admin` (the front also hides it, and re-checks the role in every server action).
ADMINISTRACION = [Depends(require_role("admin"))]
SoloAdmin = Annotated[Usuario, Depends(require_role("admin"))]
Sesion = Annotated[Session, Depends(get_session)]

PERIODO = r"^[0-9]{4}-(0[1-9]|1[0-2])$"
Dinero = Annotated[Decimal, Field(max_digits=14, decimal_places=4)]
Cantidad = Annotated[Decimal, Field(max_digits=12, decimal_places=6)]


class Entrada(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class Salida(BaseModel):
    pass


# --- Request bodies --------------------------------------------------------------------------------

class ProductoIn(Entrada):
    modelo: str | None = None
    cuero: str | None = None
    color: str | None = None
    quien_lo_confecciona: Literal[*WHERE_MADE] | None = None
    fecha_de_alta: date | None = None
    nombre_propio: str | None = None
    es_kit: bool = False
    nota: str | None = None


class ExtraIn(Entrada):
    material: str
    color: str | None = None
    consumo_neto_por_unidad: Annotated[Decimal, Field(gt=0, max_digits=12, decimal_places=6)]
    nota: str | None = None


class ComponenteIn(Entrada):
    componente: str
    cantidad: Annotated[Decimal, Field(gt=0, max_digits=12, decimal_places=6)]


class CotizacionIn(Entrada):
    tipo: Literal[*servicios.QUOTE_TYPES]
    fecha: date | None = None


class PrecioIn(Entrada):
    material: str
    color: str | None = None
    proveedor: str | None = None
    precio: Annotated[Decimal, Field(ge=0, max_digits=14, decimal_places=4)]
    moneda: Literal[*ARS_USD]
    unidad_del_precio: Literal[*UNITS]
    iva_incluido: bool = False
    vigente_desde: date
    nota_fuente: str | None = None


class DolarIn(Entrada):
    fecha: date
    ars_por_usd: Annotated[Decimal, Field(gt=0, max_digits=12, decimal_places=4)]
    fuente: Literal["BNA", "EXCEL_VIEJO", "MANUAL"] = "MANUAL"
    tipo: Literal["VENDEDOR", "COMPRADOR"] | None = None
    nota: str | None = None


class GastoIn(Entrada):
    periodo: Annotated[str, Field(pattern=PERIODO)]
    concepto: str
    fabrica_o_tienda: Literal["FABRICA", "TIENDA"]
    categoria: Literal["SUELDOS", "CARGAS_SOCIALES", "ALQUILER", "SERVICIOS", "IMPUESTOS_FIJOS", "OTROS"]
    persona: str | None = None
    monto_ars_del_mes: Annotated[Decimal, Field(ge=0, max_digits=14, decimal_places=4)] | None = None
    ficticio: bool = False
    nota_fuente: str | None = None


class ItemIn(Entrada):
    producto: str
    cantidad: Annotated[Decimal, Field(ge=0, max_digits=12, decimal_places=6)]
    taller_precio_cotizado_por_unidad_ars: Annotated[Decimal, Field(ge=0, max_digits=14, decimal_places=4)] | None = None
    taller_precio_pagado_por_unidad_ars: Annotated[Decimal, Field(ge=0, max_digits=14, decimal_places=4)] | None = None
    nota: str | None = None


class OrdenIn(Entrada):
    donde_se_hace: Literal[*WHERE_MADE]
    taller: str | None = None
    persona: str | None = None
    fecha_de_envio: date | None = None
    fecha_de_entrega: date | None = None
    estado: Literal[*LOT_STATES] = "PLANIFICADA"
    nota: str | None = None
    items: Annotated[list[ItemIn], Field(min_length=1)]


class TallerIn(Entrada):
    nombre: Annotated[str, Field(min_length=1)]
    cuit: str | None = None
    telefono: str | None = None
    direccion: str | None = None
    contacto: str | None = None
    nota: str | None = None


class ActivoIn(Entrada):
    activo: bool


class EstadoIn(Entrada):
    estado: Literal[*LOT_STATES]
    fecha: date
    quien: str | None = None
    fecha_de_entrega: date | None = None


class PreciosItemIn(Entrada):
    """What the workshop quoted and/or charged per unit; at least one of the two."""

    cotizado: Annotated[Decimal, Field(ge=0, max_digits=14, decimal_places=4)] | None = None
    pagado: Annotated[Decimal, Field(ge=0, max_digits=14, decimal_places=4)] | None = None

    @model_validator(mode="after")
    def alguno(self):
        if self.cotizado is None and self.pagado is None:
            raise ValueError("Indicá el precio cotizado, el pagado o los dos.")
        return self


class MontoIn(Entrada):
    monto_ars_del_mes: Annotated[Decimal, Field(ge=0, max_digits=14, decimal_places=4)]


class ParametroIn(Entrada):
    """Exactly one of `valor` / `valor_texto`, according to the parameter's unit (checked by the service)."""

    valor: Annotated[Decimal, Field(max_digits=14, decimal_places=4)] | None = None
    valor_texto: str | None = None
    fuente_estado: Literal[*servicios.ESTADOS_DE_PARAMETRO]
    nota: Annotated[str, Field(max_length=300)] | None = None


class PersonaIn(Entrada):
    nombre: Annotated[str, Field(min_length=1, max_length=120)]
    rol: Literal[*servicios.PERSONA_ROLES]
    vinculo: Literal[*servicios.PERSONA_VINCULOS]
    nota: str | None = None


class CatalogoIn(Entrada):
    nombre: Annotated[str, Field(min_length=1, max_length=120)]
    nota: str | None = None


Metros = Annotated[Decimal, Field(ge=0, max_digits=12, decimal_places=6)]
Importe = Annotated[Decimal, Field(ge=0, max_digits=14, decimal_places=4)]


class ConsumosIn(Entrada):
    """Every consumption field must be sent (null = missing data, 0 = "no lleva"): a partial body is refused, so
    nothing is cleared by leaving it out."""

    cuero_m2_por_unidad: Metros
    forro: str | None
    forro_m2_por_unidad: Metros | None
    flex_m2_por_unidad: Metros | None
    goma_eva_m2_por_unidad: Metros | None
    herrajes_usd_por_unidad: Importe | None
    hilo_y_cemento: Metros | None
    confeccion_estimada_ars: Importe | None
    horas_de_confeccion: Metros | None
    origen_de_los_consumos: Literal[*servicios.ORIGENES]


class ModeloIn(ConsumosIn):
    nombre_del_modelo: Annotated[str, Field(min_length=1, max_length=200)]
    categoria: str
    tamano: Literal[*servicios.TAMANOS] | None = None
    nota: str | None = None


class ValidadoIn(Entrada):
    validado: bool


# --- Responses -------------------------------------------------------------------------------------------

class ProductoResumen(Salida):
    codigo: str
    nombre: str
    categoria: str | None
    estado_del_ciclo: str
    es_kit: bool
    costo_hoy_ars: Decimal | None
    costo_hoy_usd: Decimal | None
    avisos: list[str]


class LineaRecetaOut(Salida):
    etapa: str
    material: str
    color: str | None
    consumo: Decimal


class ComponenteOut(Salida):
    producto: str
    cantidad: Decimal


class DesgloseOut(Salida):
    fecha: date
    dolar: Decimal
    etapas: dict[str, Decimal]
    subtotal: Decimal
    componentes_kit: Decimal
    iva_compras: Decimal
    arreglos: Decimal
    total_ars: Decimal
    total_usd: Decimal


class CotizacionOut(Salida):
    producto: str
    tipo: str
    fecha: date
    dolar: Decimal
    cuero: Decimal
    forro: Decimal
    flex: Decimal
    goma_eva: Decimal
    herrajes: Decimal
    hilo_cemento: Decimal
    corte: Decimal
    confeccion: Decimal
    subtotal_etapas: Decimal
    componentes_kit: Decimal
    iva_compras: Decimal
    arreglos: Decimal
    total_ars: Decimal
    total_usd: Decimal
    estado: str | None


class FichaOut(Salida):
    codigo: str
    nombre: str
    categoria: str | None
    modelo: str | None
    cuero: str | None
    color: str | None
    quien_lo_confecciona: str | None
    estado_del_ciclo: str
    es_kit: bool
    nota: str | None
    fecha_de_alta: date | None
    fecha_de_recotizacion: date | None
    fecha_de_cierre: date | None
    receta: list[LineaRecetaOut]
    componentes: list[ComponenteOut]
    confeccion_estimada_ars: Decimal
    costo_hoy: DesgloseOut | None
    avisos: list[str]
    recotizar: bool | None
    cotizaciones: list[CotizacionOut]


class ModeloOut(Salida):
    codigo: str
    nombre_del_modelo: str
    categoria: str | None
    tamano: str | None
    cuero_m2_por_unidad: Decimal | None
    forro: str | None
    forro_m2_por_unidad: Decimal | None
    flex_m2_por_unidad: Decimal | None
    goma_eva_m2_por_unidad: Decimal | None
    herrajes_usd_por_unidad: Decimal | None
    hilo_y_cemento: Decimal | None
    confeccion_estimada_ars: Decimal | None
    origen_de_los_consumos: str | None
    validado: bool


class ModeloDetalleOut(ModeloOut):
    horas_de_confeccion: Decimal | None
    nota: str | None
    modelo_excel_viejo: str | None
    fila_excel_viejo: int | None
    productos: int  # products made from this model


class MaterialOut(Salida):
    codigo: str
    nombre: str
    nombre_corto: str | None
    etapa: str
    unidad_de_consumo: str
    cotizable: bool
    controla_inventario: bool
    desperdicio_manual: Decimal | None


class PrecioOut(Salida):
    codigo: str
    material: str
    color: str | None
    proveedor: str | None
    precio: Decimal
    moneda: str
    unidad_del_precio: str
    iva_incluido: bool
    vigente_desde: date
    nota_fuente: str | None
    vigente: bool
    variacion_pct: Decimal | None
    salto_grande: bool


class PrecioChequeoOut(Salida):
    anterior: Decimal | None
    variacion_pct: Decimal | None
    salto_grande: bool


class CatalogosOut(Salida):
    colores: list[str]
    categorias: list[str]


class ConteoOut(Salida):
    total: int


class DolarOut(Salida):
    fecha: date
    ars_por_usd: Decimal
    fuente: str
    tipo: str | None
    nota: str | None


class ParametroOut(Salida):
    codigo: str
    constante: str
    valor: Decimal | None
    valor_texto: str | None
    unidad: str | None
    que_es: str | None
    fuente_estado: str | None


class TallerOut(Salida):
    codigo: str
    nombre: str
    cuit: str | None
    telefono: str | None
    direccion: str | None
    contacto: str | None
    activo: bool
    nota: str | None
    ejemplo: bool
    lotes: int
    unidades: Decimal
    ultimo_lote: date | None
    cobro_total_ars: Decimal


class GastoOut(Salida):
    codigo: str
    concepto: str
    fabrica_o_tienda: str
    categoria: str
    persona: str | None
    monto_ars_del_mes: Decimal | None
    ficticio: bool
    nota_fuente: str | None


class ImpuestoOut(Salida):
    codigo: str
    nombre: str
    alicuota: Decimal | None
    base: str | None
    es_costo_del_producto: bool
    nota: str | None


class CatalogoItemOut(Salida):
    codigo: str
    nombre: str
    nota: str | None


class PersonaOut(Salida):
    codigo: str
    nombre: str
    rol: str
    activo: bool


class CostosFijosOut(Salida):
    periodo: str
    total_fabrica: Decimal
    total_tienda: Decimal
    total: Decimal
    pendientes: int
    incluye_ficticios: bool
    gastos: list[GastoOut]


class ItemOut(Salida):
    codigo: str
    producto: str
    cantidad: Decimal
    taller_precio_cotizado_por_unidad_ars: Decimal | None
    taller_precio_pagado_por_unidad_ars: Decimal | None
    nota: str | None


class OrdenOut(Salida):
    codigo: str
    donde_se_hace: str
    taller: str | None
    persona: str | None
    fecha_de_envio: date | None
    fecha_de_entrega: date | None
    estado: str
    nota: str | None
    items: list[ItemOut]


class PeriodosOut(Salida):
    vigente: str | None
    periodos: list[str]


class OrdenResumenOut(Salida):
    codigo: str
    donde_se_hace: str
    taller: str | None
    taller_nombre: str | None
    persona: str | None
    persona_nombre: str | None
    fecha_de_envio: date | None
    fecha_de_entrega: date | None
    periodo: str | None
    estado: str
    nota: str | None
    productos: int
    unidades: Decimal
    total_cotizado: Decimal
    total_cobrado: Decimal
    costo_total: Decimal | None
    costo_promedio_por_unidad: Decimal | None
    avisos: list[str]


class RenglonOut(Salida):
    codigo: str
    producto: str
    producto_nombre: str
    categoria: str | None
    tamano: str | None
    cantidad: Decimal
    cotizado: Decimal | None
    pagado: Decimal | None
    nota: str | None
    confeccion_por_unidad: Decimal | None
    materiales_por_unidad: Decimal | None
    costo_por_unidad: Decimal | None
    total_linea: Decimal | None
    avisos: list[str]


class EstadoOut(Salida):
    estado: str
    fecha: date
    quien: str | None
    quien_nombre: str | None


class OrdenDetalleOut(OrdenResumenOut):
    items: list[RenglonOut]
    estados: list[EstadoOut]


class TallerDetalleOut(TallerOut):
    ordenes: list[OrdenResumenOut]


class MesCasaTallerOut(Salida):
    periodo: str
    lotes_casa: int
    lotes_taller: int
    unidades_casa: Decimal
    unidades_taller: Decimal
    porcentaje_taller: Decimal | None
    pagado_a_talleres: Decimal
    unidades_por_taller: dict[str, Decimal]


class TallerCorto(Salida):
    codigo: str
    nombre: str


class CasaVsTallerOut(Salida):
    talleres: list[TallerCorto]
    meses: list[MesCasaTallerOut]


class PrecioPorTallerOut(Salida):
    taller: str
    taller_nombre: str | None
    hizo: bool
    precio: Decimal | None
    fecha: date | None
    lote: str | None
    cantidad: Decimal | None
    veces: int
    precio_anterior: Decimal | None
    variacion_pct: Decimal | None


class PrecioParecidoOut(Salida):
    fecha: date
    producto: str
    nombre: str
    tamano: str | None
    taller: str
    taller_nombre: str | None
    cantidad: Decimal
    precio: Decimal
    lote: str
    es_mismo_producto: bool


class PreciosTalleresOut(Salida):
    producto: str
    nombre: str
    categoria: str | None
    tamano: str | None
    veces_en_taller: int
    por_taller: list[PrecioPorTallerOut]
    parecidos: list[PrecioParecidoOut]


class HallazgoOut(Salida):
    severidad: Literal["alta", "media", "baja"]
    entidad: str
    mensaje: str
    ruta: str


class GrupoCalidadOut(Salida):
    clave: str
    titulo: str
    total: int
    hallazgos: list[HallazgoOut]


class ResumenCalidadOut(Salida):
    alta: int
    media: int
    baja: int
    total: int


class CalidadOut(Salida):
    resumen: ResumenCalidadOut
    grupos: list[GrupoCalidadOut]


# --- Read ----------------------------------------------------------------------------------------------------

@router.get("/productos", response_model=list[ProductoResumen])
def productos(
    session: Sesion, limit: int = Query(100, ge=1, le=500), offset: int = Query(0, ge=0),
    q: str | None = Query(None, max_length=100), categoria: str | None = None,
):
    return servicios.listar_productos(session, limit, offset, q, categoria)


# Declared before `/productos/{codigo}` so "conteo" is not read as a product code.
@router.get("/productos/conteo", response_model=ConteoOut)
def productos_conteo(session: Sesion, q: str | None = Query(None, max_length=100), categoria: str | None = None):
    return {"total": servicios.contar_productos(session, q, categoria)}


@router.get("/productos/{codigo}", response_model=FichaOut)
def ficha(codigo: str, session: Sesion):
    return servicios.ficha_producto(session, codigo)


@router.get("/modelos", response_model=list[ModeloOut])
def modelos(
    session: Sesion, limit: int = Query(500, ge=1, le=1000), offset: int = Query(0, ge=0),
    q: str | None = Query(None, max_length=100), categoria: str | None = None, validado: bool | None = None,
    tamano: Literal[*servicios.TAMANOS] | None = None,
):
    return servicios.listar_modelos(session, limit, offset, q, categoria, validado, tamano)


@router.get("/modelos/{codigo}", response_model=ModeloDetalleOut)
def modelo(codigo: str, session: Sesion):
    return servicios.detalle_modelo(session, codigo)


@router.get("/materiales", response_model=list[MaterialOut])
def materiales(session: Sesion):
    return servicios.listar_materiales(session)


@router.get("/precios", response_model=list[PrecioOut])
def precios(session: Sesion, material: str | None = None, a_fecha: date | None = None):
    return servicios.listar_precios(session, material, a_fecha)


@router.get("/precios/chequeo", response_model=PrecioChequeoOut)
def precio_chequeo(
    session: Sesion, material: str, precio: Annotated[Decimal, Query(ge=0, max_digits=14, decimal_places=4)],
    moneda: Literal[*ARS_USD], vigente_desde: date, color: str | None = None,
):
    """How far a price about to be loaded is from the previous one. Reads only; saves nothing."""
    return servicios.chequear_precio(session, material, color, precio, moneda, vigente_desde)


@router.get("/catalogos", response_model=CatalogosOut)
def catalogos(session: Sesion):
    return servicios.listar_catalogos(session)


@router.get("/colores", response_model=list[CatalogoItemOut])
def colores(session: Sesion):
    return servicios.listar_colores(session)


@router.get("/categorias", response_model=list[CatalogoItemOut])
def categorias(session: Sesion):
    return servicios.listar_categorias(session)


@router.get("/impuestos", response_model=list[ImpuestoOut])
def impuestos(session: Sesion):
    """Read only: whether VAT counts as a product cost is an open business decision."""
    return servicios.listar_impuestos(session)


@router.get("/dolar", response_model=list[DolarOut])
def dolar(session: Sesion):
    return servicios.listar_dolar(session)


@router.get("/parametros", response_model=list[ParametroOut])
def parametros(session: Sesion):
    return servicios.listar_parametros(session)


@router.get("/talleres", response_model=list[TallerOut])
def talleres(session: Sesion):
    return servicios.listar_talleres(session)


@router.get("/personas", response_model=list[PersonaOut])
def personas(session: Sesion):
    return servicios.listar_personas(session)


@router.get("/talleres/{codigo}", response_model=TallerDetalleOut)
def taller(codigo: str, session: Sesion):
    return servicios.detalle_taller(session, codigo)


@router.get("/costos-fijos", response_model=CostosFijosOut)
def costos_fijos(session: Sesion, periodo: Annotated[str | None, Query(pattern=PERIODO)] = None):
    return servicios.costos_fijos(session, periodo)


@router.get("/costos-fijos/periodos", response_model=PeriodosOut)
def periodos_de_costos_fijos(session: Sesion):
    return servicios.periodos_de_costos_fijos(session)


@router.get("/ordenes", response_model=list[OrdenResumenOut])
def ordenes(
    session: Sesion, estado: Literal[*LOT_STATES] | None = None, donde: Literal[*WHERE_MADE] | None = None,
    taller: str | None = None,
):
    return servicios.listar_ordenes(session, estado, donde, taller)


@router.get("/ordenes/{codigo}", response_model=OrdenDetalleOut)
def orden(codigo: str, session: Sesion):
    return servicios.detalle_orden(session, codigo)


@router.get("/fabricacion/casa-vs-taller", response_model=CasaVsTallerOut)
def casa_vs_taller(session: Sesion, hasta: Annotated[str | None, Query(pattern=PERIODO)] = None):
    """The last 12 months up to `hasta` (default: this month). A lot counts in the month of its delivery date, else of its shipping date."""
    return servicios.casa_vs_taller(session, hasta)


@router.get("/productos/{codigo}/precios-talleres", response_model=PreciosTalleresOut)
def precios_de_talleres(codigo: str, session: Sesion, mismo_tamano: bool = True):
    return servicios.precios_de_talleres(session, codigo, mismo_tamano)


@router.get("/calidad", response_model=CalidadOut)
def calidad(session: Sesion):
    return servicios.calidad_de_datos(session)


# --- Write ----------------------------------------------------------------------------------------------------

@router.post("/productos", dependencies=ESCRITURA, response_model=FichaOut, status_code=201)
def crear_producto(cuerpo: ProductoIn, session: Sesion):
    return servicios.crear_producto(session, **cuerpo.model_dump())


@router.post("/productos/{codigo}/extras", dependencies=ESCRITURA, response_model=FichaOut, status_code=201)
def agregar_extra(codigo: str, cuerpo: ExtraIn, session: Sesion):
    return servicios.agregar_extra(session, codigo, **cuerpo.model_dump())


@router.post("/productos/{codigo}/componentes", dependencies=ESCRITURA, response_model=FichaOut, status_code=201)
def agregar_componente(codigo: str, cuerpo: ComponenteIn, session: Sesion):
    return servicios.agregar_componente(session, codigo, **cuerpo.model_dump())


@router.post("/productos/{codigo}/cotizaciones", dependencies=ESCRITURA, response_model=CotizacionOut, status_code=201)
def guardar_cotizacion(codigo: str, cuerpo: CotizacionIn, session: Sesion):
    return servicios.guardar_cotizacion(session, codigo, cuerpo.tipo, cuerpo.fecha)


@router.post("/precios", dependencies=ESCRITURA, response_model=PrecioOut, status_code=201)
def crear_precio(cuerpo: PrecioIn, session: Sesion):
    return servicios.crear_precio(session, **cuerpo.model_dump())


@router.post("/dolar", dependencies=ESCRITURA, response_model=DolarOut, status_code=201)
def crear_dolar(cuerpo: DolarIn, session: Sesion):
    return servicios.crear_dolar(session, **cuerpo.model_dump())


@router.post("/costos-fijos", dependencies=ESCRITURA, response_model=CostosFijosOut, status_code=201)
def crear_gasto(cuerpo: GastoIn, session: Sesion):
    return servicios.crear_gasto(session, **cuerpo.model_dump())


@router.post("/ordenes", dependencies=ESCRITURA, response_model=OrdenOut, status_code=201)
def crear_orden(cuerpo: OrdenIn, session: Sesion):
    datos = cuerpo.model_dump()
    return servicios.crear_orden(session, **datos)


@router.post("/ordenes/{codigo}/estado", dependencies=ESCRITURA, response_model=OrdenDetalleOut, status_code=201)
def cambiar_estado_de_orden(codigo: str, cuerpo: EstadoIn, session: Sesion):
    return servicios.registrar_estado(session, codigo, **cuerpo.model_dump())


@router.post("/ordenes/{codigo}/items", dependencies=ESCRITURA, response_model=OrdenDetalleOut, status_code=201)
def agregar_item_a_orden(codigo: str, cuerpo: ItemIn, session: Sesion):
    datos = cuerpo.model_dump()
    return servicios.agregar_item_a_orden(
        session, codigo, producto=datos["producto"], cantidad=datos["cantidad"],
        cotizado=datos["taller_precio_cotizado_por_unidad_ars"], pagado=datos["taller_precio_pagado_por_unidad_ars"],
        nota=datos["nota"],
    )


@router.post("/ordenes/{codigo}/items/{item}/precios", dependencies=ESCRITURA, response_model=OrdenDetalleOut)
def registrar_precios_de_item(codigo: str, item: str, cuerpo: PreciosItemIn, session: Sesion):
    return servicios.registrar_precios_item(session, codigo, item, **cuerpo.model_dump())


@router.post("/talleres", dependencies=ESCRITURA, response_model=TallerDetalleOut, status_code=201)
def crear_taller(cuerpo: TallerIn, session: Sesion):
    return servicios.crear_taller(session, **cuerpo.model_dump())


@router.post("/talleres/{codigo}/activo", dependencies=ESCRITURA, response_model=TallerDetalleOut)
def cambiar_activo_de_taller(codigo: str, cuerpo: ActivoIn, session: Sesion):
    return servicios.cambiar_activo_taller(session, codigo, cuerpo.activo)


@router.post("/costos-fijos/{codigo}/monto", dependencies=ESCRITURA, response_model=CostosFijosOut)
def cargar_monto_de_gasto(codigo: str, cuerpo: MontoIn, session: Sesion):
    """Only while the amount is still empty (409 otherwise): a correction is a new row."""
    return servicios.cargar_monto_de_gasto(session, codigo, cuerpo.monto_ars_del_mes)


@router.post("/parametros/{codigo}", response_model=ParametroOut)
def cambiar_parametro(codigo: str, cuerpo: ParametroIn, session: Sesion, usuario: SoloAdmin):
    """Admin only. Overwrites the value in place and keeps no history (no column for it): the change is logged."""
    return servicios.cambiar_parametro(
        session, codigo, valor=cuerpo.valor, valor_texto=cuerpo.valor_texto, estado=cuerpo.fuente_estado,
        nota=cuerpo.nota, quien=usuario.id,
    )


@router.post("/personas", dependencies=ADMINISTRACION, response_model=PersonaOut, status_code=201)
def crear_persona(cuerpo: PersonaIn, session: Sesion):
    return servicios.crear_persona(session, **cuerpo.model_dump())


@router.post("/personas/{codigo}/activo", dependencies=ADMINISTRACION, response_model=PersonaOut)
def cambiar_activo_de_persona(codigo: str, cuerpo: ActivoIn, session: Sesion):
    return servicios.cambiar_activo_persona(session, codigo, cuerpo.activo)


@router.post("/colores", dependencies=ADMINISTRACION, response_model=CatalogoItemOut, status_code=201)
def crear_color(cuerpo: CatalogoIn, session: Sesion):
    return servicios.crear_color(session, **cuerpo.model_dump())


@router.post("/categorias", dependencies=ADMINISTRACION, response_model=CatalogoItemOut, status_code=201)
def crear_categoria(cuerpo: CatalogoIn, session: Sesion):
    return servicios.crear_categoria(session, **cuerpo.model_dump())


@router.post("/modelos", dependencies=ESCRITURA, response_model=ModeloDetalleOut, status_code=201)
def crear_modelo(cuerpo: ModeloIn, session: Sesion):
    """The server assigns `MOD-nnnn`; a new model is never validated."""
    return servicios.crear_modelo(session, **cuerpo.model_dump())


@router.post("/modelos/{codigo}/validado", dependencies=ESCRITURA, response_model=ModeloDetalleOut)
def cambiar_validado_de_modelo(codigo: str, cuerpo: ValidadoIn, session: Sesion):
    return servicios.cambiar_validado(session, codigo, cuerpo.validado)


@router.post("/modelos/{codigo}/consumos", response_model=ModeloDetalleOut)
def cambiar_consumos_de_modelo(codigo: str, cuerpo: ConsumosIn, session: Sesion, usuario: SoloAdmin):
    """Admin only. Overwrites the consumptions, resets `validado` and logs the previous values."""
    return servicios.cambiar_consumos(session, codigo, quien=usuario.id, **cuerpo.model_dump())


# --- Google Sheet display copy (T6) ------------------------------------------------------------------------------
# The Sheet is DISPLAY ONLY: the app builds the tabs (sheets_export.py), pushes them (sheets_client.py) and never reads
# anything back. Admin only to run or preview; any signed-in user can read the status.

# SUPUESTO: validar. Argentina has no daylight saving time, so a fixed UTC-3 offset keeps the "today" of the export
# (which price is in force) the local one without needing the tz database in the container.
ZONA_HORARIA = timezone(timedelta(hours=-3))
FILAS_DE_VISTA = 50
MENSAJE_GENERICO_DE_SYNC = "No se pudo sincronizar con Google Sheets."


class EstadoDeSincronizacion:
    """Process-level lock (one run at a time) and the summary of the last run.

    SUPUESTO: validar. Kept in memory only (no table, no migration): it is lost on a restart and each replica of the
    service has its own lock and summary.
    """

    def __init__(self):
        self.lock = threading.Lock()
        self.ultima: dict | None = None


_ESTADO_SYNC = EstadoDeSincronizacion()


class SincronizarIn(Entrada):
    """`simular` left out: a dry run while the Google variables are missing, a real push once they are set."""

    simular: bool | None = None


class PestanaOut(Salida):
    nombre: str
    filas: int


class SincronizacionOut(Salida):
    simulacion: bool
    configurado: bool
    iniciado: datetime
    finalizado: datetime
    duracion_ms: int
    total_filas: int
    pestanas: list[PestanaOut]


class UltimaSincronizacionOut(SincronizacionOut):
    ok: bool
    error: str | None


class EstadoSincronizacionOut(Salida):
    configurado: bool
    variables: list[str]  # names only, never the values
    faltantes: list[str]
    pestanas: list[str]
    en_curso: bool
    ultima: UltimaSincronizacionOut | None


class VistaOut(Salida):
    pestana: str
    encabezados: list[str]
    filas: list[list[str]]
    total_filas: int
    mostradas: int


@lru_cache(maxsize=1)
def version_de_la_app() -> str:
    try:
        return importlib.metadata.version("backend")
    except importlib.metadata.PackageNotFoundError:
        return "desconocida"


def ahora() -> datetime:
    return datetime.now(ZONA_HORARIA)


def get_fuente_sheets(session: Sesion) -> Fuente:
    return FuenteSQL(session)


def get_cliente_sheets() -> SheetsClient | None:
    """The real client while both variables are set (building it makes no network call), else None."""
    return sheets_client.crear_cliente() if sheets_client.leer_config() is not None else None


def _texto_de_celda(valor: object) -> str:
    return format(valor, "f") if isinstance(valor, Decimal) else str(valor)


@router.get("/sync/sheets/estado", response_model=EstadoSincronizacionOut)
def estado_de_sync():
    faltantes = sheets_client.faltantes()
    return {
        "configurado": not faltantes, "variables": list(sheets_client.VARIABLES), "faltantes": faltantes,
        "pestanas": list(NOMBRES_DE_PESTANAS), "en_curso": _ESTADO_SYNC.lock.locked(), "ultima": _ESTADO_SYNC.ultima,
    }


@router.get("/sync/sheets/vista/{pestana}", dependencies=ADMINISTRACION, response_model=VistaOut)
def vista_de_sync(pestana: str, fuente: Annotated[Fuente, Depends(get_fuente_sheets)]):
    """The first rows of one tab as the Sheet would get it (money as text). Reads only; does not call Google."""
    if pestana not in NOMBRES_DE_PESTANAS:
        raise servicios.NoEncontrado(f"No existe la pestaña {pestana}.")
    tab = construir_tab(pestana, fuente, generado_en=ahora(), version=version_de_la_app())
    return {
        "pestana": tab.name, "encabezados": list(tab.headers), "total_filas": len(tab.rows),
        "filas": [[_texto_de_celda(c) for c in fila] for fila in tab.rows[:FILAS_DE_VISTA]],
        "mostradas": min(len(tab.rows), FILAS_DE_VISTA),
    }


@router.post("/sync/sheets", dependencies=ADMINISTRACION, response_model=SincronizacionOut)
def sincronizar_sheets(
    fuente: Annotated[Fuente, Depends(get_fuente_sheets)],
    cliente: Annotated[SheetsClient | None, Depends(get_cliente_sheets)],
    cuerpo: SincronizarIn | None = None,
):
    """Build every tab and, unless it is a dry run, replace the values of those tabs in the Google Sheet.

    409 while another run is in progress, 422 for a real push without the Google variables, 502 (safe message) when Google fails.
    """
    configurado = sheets_client.leer_config() is not None
    simular = cuerpo.simular if cuerpo is not None and cuerpo.simular is not None else not configurado
    if not simular and (not configurado or cliente is None):
        raise HTTPException(422, "Para sincronizar con Google hay que configurar " + " y ".join(sheets_client.faltantes())
                            + ". Mientras tanto se puede simular.")
    if not _ESTADO_SYNC.lock.acquire(blocking=False):
        raise HTTPException(409, "Ya hay una sincronización en curso. Esperá a que termine.")
    try:
        iniciado, reloj = ahora(), time.monotonic()
        error = None
        try:
            tabs = construir_tabs(fuente, generado_en=iniciado, version=version_de_la_app())
        except Exception:
            _ESTADO_SYNC.ultima = _resumen(simular, configurado, iniciado, reloj, [], "No se pudo generar la vista de los datos.")
            raise
        if not simular:
            try:
                cliente.reemplazar_pestanas(tabs)
            except ErrorDeSheets as falla:
                error = falla.mensaje
            except Exception as falla:  # noqa: BLE001 - the answer must never carry the raw error (it may hold secrets)
                logger.warning("Sheets sync failed: %s", type(falla).__name__)
                error = MENSAJE_GENERICO_DE_SYNC
        resumen = _resumen(simular, configurado, iniciado, reloj, tabs, error)
        _ESTADO_SYNC.ultima = resumen
        if error is not None:
            raise HTTPException(502, error)
        return resumen
    finally:
        _ESTADO_SYNC.lock.release()


def _resumen(simular: bool, configurado: bool, iniciado: datetime, reloj: float, tabs, error: str | None) -> dict:
    pestanas = [{"nombre": t.name, "filas": len(t.rows)} for t in tabs]
    return {
        "simulacion": simular, "configurado": configurado, "iniciado": iniciado, "finalizado": ahora(),
        "duracion_ms": int((time.monotonic() - reloj) * 1000), "total_filas": sum(p["filas"] for p in pestanas),
        "pestanas": pestanas, "ok": error is None, "error": error,
    }


# --- Errors ----------------------------------------------------------------------------------------------------

def registrar_errores(app: FastAPI) -> None:
    """Map service errors to HTTP codes: 404 missing, 409 already there, 422 refused."""

    @app.exception_handler(servicios.NoEncontrado)
    async def no_encontrado(request: Request, error: servicios.NoEncontrado):
        return JSONResponse(status_code=404, content={"detail": str(error)})

    @app.exception_handler(servicios.Conflicto)
    async def conflicto(request: Request, error: servicios.Conflicto):
        return JSONResponse(status_code=409, content={"detail": str(error)})

    @app.exception_handler(servicios.CotizacionIncompleta)
    async def incompleta(request: Request, error: servicios.CotizacionIncompleta):
        return JSONResponse(status_code=422, content={"detail": str(error), "avisos": error.avisos})

    @app.exception_handler(servicios.DatosInvalidos)
    async def invalidos(request: Request, error: servicios.DatosInvalidos):
        return JSONResponse(status_code=422, content={"detail": str(error)})
