"""Costing API: read and load endpoints. Routers only validate input and call `servicios`.

Every route requires a signed-in user (see auth.py; fail-closed without a verifier). Reads are open to
any signed-in role; every POST also needs the role `admin` or `cotizador` (`consulta` gets 403).
Calculated values (names, categories, totals, costs) are never accepted from the client:
request models forbid unknown fields. Money leaves as strings because the response models
keep Decimal and pydantic serializes it as text in JSON.
"""

from datetime import date
from decimal import Decimal
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, FastAPI, Query, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy.orm import Session

from backend import servicios
from backend.auth import require_role, require_user
from backend.database import get_session
from backend.models import ARS_USD, LOT_STATES, UNITS, WHERE_MADE

router = APIRouter(dependencies=[Depends(require_user)])
# Roles that may write. `require_role` builds on `require_user`, so no session still answers 401, not 403.
ESCRITURA = [Depends(require_role("admin", "cotizador"))]
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
def modelos(session: Sesion, limit: int = Query(500, ge=1, le=1000), offset: int = Query(0, ge=0)):
    return servicios.listar_modelos(session, limit, offset)


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
