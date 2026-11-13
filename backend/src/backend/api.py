"""Costing API: read and load endpoints. Routers only validate input and call `servicios`.

Every route requires a signed-in user (see auth.py; fail-closed without a verifier). Reads are open to
any signed-in role; existing POST routes need `admin` or `cotizador`. Cutting and remainder POST routes
also allow `corte`; the admin area (parameters, people, catalogs, model consumptions) needs `admin`.
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

from fastapi import APIRouter, Depends, FastAPI, File, Form, HTTPException, Path, Query, Request, UploadFile
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy.orm import Session

from backend import cueros, formulario, ocr_llm, proveedores, reventa, servicios, sheets_client, voz, voz_llm
from backend import materiales as grilla_materiales  # `materiales` is the name of the GET /materiales route below
from backend.auth import (
    CORTE, CUALQUIER_ROL, FORMULARIO_LEER, FORMULARIO_TRABAJAR, PRODUCTOS, SOLO_ADMIN, Usuario, require_user,
)
from backend.database import get_session
from backend.models import ARS_USD, DOCUMENT_TYPES, FORM_SECTIONS, FORM_STATES, LOT_STATES, UNITS, WHERE_MADE
from backend.sheets_client import ErrorDeSheets, SheetsClient
from backend.sheets_export import NOMBRES_DE_PESTANAS, Fuente, FuenteSQL, _catalogo, _costos_variables, construir_tab, construir_tabs

logger = logging.getLogger("uvicorn.error")

router = APIRouter(dependencies=[Depends(require_user)])
# Access matrix, deny by default: EVERY endpoint carries one of these gates (test_roles.py fails otherwise).
# `require_role` builds on `require_user`, so no session still answers 401, not 403. SUPUESTO: validar.
#   admin    everything.
#   gerente  read only, and only Productos, Modelos and the scenario simulator: product and quote data
#            (LECTURA_PRODUCTOS, which also holds GET /cvu/periodo and the POST /cvu/escenario calculation: it saves
#            nothing) and what those pages read (LECTURA_GENERAL: products, models, materials, catalogs). Exactly that:
#            Panel, grid, prices, dollar, colors, categories, lots, workshops, suppliers, leather stock and consumption
#            forms are closed to it (S8, test_roles.py fixes the list).
#   taller   voice, cutting and leather stock (CORTES, LECTURA_CORTE), plus, read only, everything needed to quote or
#            assemble a new product: products and their sheet, models, materials, catalogs (LECTURA_GENERAL) and prices,
#            dollar, colors, categories (LECTURA_CORTE, which the gerente does not read), but not profitability / sale
#            prices (gerente + admin) nor the workshop history (admin only).
# Every write is admin only (ESCRITURA) except cutting and the voice interpreter (CORTES).
ESCRITURA = [Depends(SOLO_ADMIN)]
CORTES = [Depends(CORTE)]
# The admin area (the front also hides it, and re-checks the role in every server action).
ADMINISTRACION = [Depends(SOLO_ADMIN)]
LECTURA_ADMIN = [Depends(SOLO_ADMIN)]  # costs, prices, fixed costs, orders' money, quality, sync: admin only
LECTURA_PRODUCTOS = [Depends(PRODUCTOS)]  # admin + gerente: product, quote and scenario data
LECTURA_CORTE = [Depends(CORTE)]  # admin + taller (lots and leather stock too: the gerente does not read them)
LECTURA_GENERAL = [Depends(CUALQUIER_ROL)]  # any of the three roles
SoloAdmin = Annotated[Usuario, Depends(SOLO_ADMIN)]
Escritor = SoloAdmin
Sesion = Annotated[Session, Depends(get_session)]

PERIODO = r"^[0-9]{4}-(0[1-9]|1[0-2])$"
Dinero = Annotated[Decimal, Field(max_digits=14, decimal_places=4)]
Cantidad = Annotated[Decimal, Field(max_digits=12, decimal_places=6)]


class Entrada(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class Salida(BaseModel):
    pass


class PiezaCueroIn(Entrada):
    origen: Literal["COMPRA", "SOBRANTE_EXISTENTE"]
    material: str
    color: str | None = None
    m2_iniciales: Annotated[Decimal, Field(gt=0, max_digits=12, decimal_places=6)]
    fecha_de_compra: date | None = None
    precio_pagado_por_m2: Annotated[Decimal, Field(ge=0, max_digits=14, decimal_places=4)] | None = None
    moneda: Literal[*ARS_USD] | None = None
    proveedor: str | None = None


class CorteCueroIn(Entrada):
    m2: Annotated[Decimal, Field(gt=0, max_digits=12, decimal_places=6)]
    orden_item: str
    fecha: date | None = None
    registro_id: Annotated[int, Field(gt=0)] | None = None
    unidades: Annotated[Decimal, Field(gt=0, max_digits=12, decimal_places=6)] | None = None


class SobranteCueroIn(Entrada):
    decision: Literal["REUTILIZABLE", "IRRECUPERABLE"]
    fecha: date | None = None


class MovimientoCueroOut(Salida):
    id: int
    fecha: date
    tipo: Literal["CORTE", "DESPERDICIO", "AJUSTE", "ENTRADA"]
    m2: Decimal
    orden_item_id: int | None
    registro_id: int | None
    unidades: Decimal | None


class PiezaCueroOut(Salida):
    codigo: str
    material: str
    color: str | None
    fecha_de_compra: date | None
    proveedor: str | None
    m2_iniciales: Decimal
    precio_pagado_por_m2: Decimal | None
    moneda: Literal[*ARS_USD] | None
    estado: Literal["ENTERA", "EN_USO", "RETAZO", "CERRADA"]
    disponible: Decimal
    natural: Decimal
    irrecuperable: Decimal
    cortado: Decimal


class PiezaCueroDetalleOut(PiezaCueroOut):
    movimientos: list[MovimientoCueroOut]


class UmbralMedidoOut(Salida):
    casos: int
    promedio_m2: Decimal
    promedio_pct_comprado: Decimal | None


class GrupoCueroOut(Salida):
    material: str
    color: str | None
    comprado: Decimal
    natural: Decimal
    cuero_total_real: Decimal
    cortado: Decimal
    irrecuperable: Decimal
    disponible: Decimal
    porcentaje_desperdicio_neto: Decimal | None
    costo_desperdicio_ars: Decimal | None
    piezas: list[PiezaCueroOut]
    umbral_medido: UmbralMedidoOut | None
    umbral_retazo_m2: Decimal | None
    avisos: list[str]


class PiezaDisponibleOut(Salida):
    codigo: str
    material: str
    color: str | None
    estado: Literal["ENTERA", "EN_USO", "RETAZO"]
    disponible: Decimal


class AlternativaCueroOut(Salida):
    material: str
    color: str | None
    disponible: Decimal


class AlcanzaCueroOut(Salida):
    producto: str
    cantidad: Decimal
    necesario: Decimal | None
    disponible: Decimal
    alcanza: bool
    faltante: Decimal | None
    piezas: list[PiezaDisponibleOut]
    alternativas: list[AlternativaCueroOut]
    mensaje: str | None


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


class ProductoReventaIn(Entrada):
    nombre: Annotated[str, Field(min_length=1, max_length=200)]
    categoria: str | None = None
    proveedor: Annotated[str, Field(max_length=200)] | None = None
    nota: Annotated[str, Field(max_length=2000)] | None = None


class CompraReventaIn(Entrada):
    # Without units it is a price update, not a purchase.
    unidades: Annotated[Decimal, Field(gt=0, max_digits=12, decimal_places=6)] | None = None
    costo_unitario_ars: Annotated[Decimal, Field(gt=0, max_digits=14, decimal_places=4)]
    precio_venta_unitario_ars: Annotated[Decimal, Field(gt=0, max_digits=14, decimal_places=4)] | None = None
    fecha: date | None = None
    proveedor: Annotated[str, Field(max_length=200)] | None = None
    nota: Annotated[str, Field(max_length=2000)] | None = None


class ReventaCambioIn(Entrada):
    codigo: str
    nombre: Annotated[str, Field(max_length=200)] | None = None
    categoria: str | None = None  # "" or null clears it
    proveedor: Annotated[str, Field(max_length=200)] | None = None
    nota: Annotated[str, Field(max_length=2000)] | None = None
    costo: Annotated[Decimal, Field(gt=0, max_digits=14, decimal_places=4)] | None = None
    precio_venta: Annotated[Decimal, Field(gt=0, max_digits=14, decimal_places=4)] | None = None


class ReventaNuevoIn(Entrada):
    nombre: Annotated[str, Field(min_length=1, max_length=200)]
    categoria: str | None = None
    proveedor: Annotated[str, Field(max_length=200)] | None = None
    nota: Annotated[str, Field(max_length=2000)] | None = None
    costo: Annotated[Decimal, Field(gt=0, max_digits=14, decimal_places=4)] | None = None
    precio_venta: Annotated[Decimal, Field(gt=0, max_digits=14, decimal_places=4)] | None = None
    unidades: Annotated[Decimal, Field(gt=0, max_digits=12, decimal_places=6)] | None = None


class ReventaLoteIn(Entrada):
    cambios: list[ReventaCambioIn] = []
    nuevos: list[ReventaNuevoIn] = []


class PrecioVentaIn(Entrada):
    precio_ars: Annotated[Decimal, Field(gt=0, max_digits=14, decimal_places=4)]
    vigente_desde: date | None = None
    nota: str | None = None
    # The margin used to reach the price, a fraction of the price (0.30 = 30 %); None = typed by hand.
    margen: Annotated[Decimal, Field(ge=0, lt=1, max_digits=6, decimal_places=3)] | None = None


class PrecioPorMargenIn(Entrada):
    codigo: str
    # Margin over the sale price in percent (30 = 30 %). One decimal so it is stored exactly as a fraction (0.305).
    margen_pct: Annotated[Decimal, Field(ge=0, lt=100, max_digits=4, decimal_places=1)]


class PreciosLoteIn(Entrada):
    items: list[PrecioPorMargenIn]


class EscenarioItemIn(Entrada):
    codigo: str
    unidades: Annotated[Decimal, Field(gt=0, max_digits=12, decimal_places=6)]
    precio: Annotated[Decimal, Field(gt=0, max_digits=14, decimal_places=4)] | None = None


class EscenarioIn(Entrada):
    periodo: Annotated[str, Field(pattern=PERIODO)] | None = None
    items: list[EscenarioItemIn]


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


class CorreccionIn(Entrada):
    monto_ars_del_mes: Annotated[Decimal, Field(ge=0, max_digits=14, decimal_places=4)]
    nota: str | None = None
    ficticio: bool | None = None  # None: keep the flag of the corrected row


class CopiaIn(Entrada):
    desde: Annotated[str, Field(pattern=PERIODO)]
    hasta: Annotated[str, Field(pattern=PERIODO)]
    con_montos: bool = True
    categorias: list[str] | None = None


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


class ImpuestoIn(Entrada):
    nombre: Annotated[str, Field(min_length=1, max_length=120)]
    alicuota: Annotated[Decimal, Field(max_digits=6, decimal_places=3)]


class AlicuotaIn(Entrada):
    alicuota: Annotated[Decimal, Field(max_digits=6, decimal_places=3)]


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


class ConsumosFilaIn(ConsumosIn):
    codigo: str


class ConsumosLoteIn(Entrada):
    filas: list[ConsumosFilaIn]


class GastoCambioIn(Entrada):
    codigo: str
    monto: Annotated[Decimal, Field(ge=0, max_digits=14, decimal_places=4)] | None = None
    concepto: str | None = None
    fabrica_o_tienda: Literal["FABRICA", "TIENDA"] | None = None
    categoria: Literal["SUELDOS", "CARGAS_SOCIALES", "ALQUILER", "SERVICIOS", "IMPUESTOS_FIJOS", "OTROS"] | None = None
    persona: str | None = None  # person code; sent as null or "" it clears the person
    nota_fuente: str | None = None


class GastoNuevoIn(Entrada):
    concepto: str
    fabrica_o_tienda: Literal["FABRICA", "TIENDA"]
    categoria: Literal["SUELDOS", "CARGAS_SOCIALES", "ALQUILER", "SERVICIOS", "IMPUESTOS_FIJOS", "OTROS"]
    persona: str | None = None
    monto_ars_del_mes: Annotated[Decimal, Field(ge=0, max_digits=14, decimal_places=4)] | None = None
    nota_fuente: str | None = None


class GastosLoteIn(Entrada):
    periodo: Annotated[str, Field(pattern=PERIODO)]
    cambios: list[GastoCambioIn] = []
    nuevos: list[GastoNuevoIn] = []
    anulados: list[str] = []  # codes of current rows to delete (soft)


class MaterialCambioIn(Entrada):
    codigo: str
    # What is not sent stays as in the price in force today. A new price is always a new dated row.
    precio: Annotated[Decimal, Field(gt=0, max_digits=14, decimal_places=4)] | None = None
    moneda: Literal[*ARS_USD] | None = None
    proveedor: Annotated[str, Field(max_length=200)] | None = None  # "" clears it


class MaterialNuevoIn(Entrada):
    nombre: Annotated[str, Field(min_length=1, max_length=200)]
    etapa: str
    unidad_de_consumo: Literal[*UNITS]
    precio: Annotated[Decimal, Field(gt=0, max_digits=14, decimal_places=4)] | None = None
    moneda: Literal[*ARS_USD] | None = None
    proveedor: Annotated[str, Field(max_length=200)] | None = None


class MaterialesLoteIn(Entrada):
    cambios: list[MaterialCambioIn] = []
    nuevos: list[MaterialNuevoIn] = []


# --- Responses -------------------------------------------------------------------------------------------

class ProductoResumen(Salida):
    codigo: str
    nombre: str
    categoria: str | None
    modelo: str | None
    estado_del_ciclo: str
    es_kit: bool
    costo_hoy_ars: Decimal | None
    costo_hoy_usd: Decimal | None
    avisos: list[str]
    revisar: bool
    motivos_revisar: list[str]
    # Sale price columns of the grid: None without a saved price, and always None for the taller role.
    precio_venta_ars: Decimal | None = None
    margen_pct: Decimal | None = None
    precio_final_ars: Decimal | None = None


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
    horas_de_confeccion: Decimal | None
    origen_de_los_consumos: str | None
    validado: bool


class InsumoModeloOut(Salida):
    codigo: str
    material: str
    nombre: str
    etapa: str
    unidad_de_consumo: str
    cantidad_por_unidad: Decimal
    precio_unitario: Decimal | None  # the price in force today; None when the material has none
    moneda: str | None


class ModeloDetalleOut(ModeloOut):
    nota: str | None
    modelo_excel_viejo: str | None
    fila_excel_viejo: int | None
    productos: int  # products made from this model
    insumos: list[InsumoModeloOut] = []


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


class DolarBnaOut(DolarOut):
    estado: Literal["creado", "ya_existia"]


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
    reemplaza_a: str | None = None  # code of the row this one corrects


class ImpuestoOut(Salida):
    codigo: str
    nombre: str
    alicuota: Decimal | None
    base: str | None
    es_costo_del_producto: bool
    nota: str | None
    activo: bool = True


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


class EquilibrioOut(Salida):
    margen_por_unidad: Decimal | None
    unidades: Decimal | None
    motivo: str | None


class CvuOut(Salida):
    ingresos: Decimal
    costo_variable_total: Decimal
    margen_contribucion: Decimal
    margen_contribucion_unidad: Decimal
    margen_contribucion_pct: Decimal
    costos_fijos: Decimal
    utilidad: Decimal
    equilibrio_unidades: Decimal
    equilibrio_ingresos: Decimal
    margen_seguridad_pct: Decimal


class PanelPeriodoOut(Salida):
    periodo: str
    unidades: Decimal
    unidades_sin_costo: Decimal
    costo_variable_por_unidad: Decimal | None
    fijos_fabrica: Decimal
    fijos_cargados: bool
    fijos_pendientes: int
    fijos_ficticios: bool
    fijo_por_unidad: Decimal | None
    total_por_unidad: Decimal | None
    equilibrio: EquilibrioOut
    cvu: CvuOut | None = None
    costo_variable_total: Decimal | None = None
    costo_total: Decimal | None = None
    fijos_pct_del_total: Decimal | None = None


class PanelVariacionOut(Salida):
    costo_variable_por_unidad: Decimal | None
    fijos_fabrica: Decimal | None
    total_por_unidad: Decimal | None


class PanelPrecioSubioOut(Salida):
    material: str
    color: str | None
    precio: Decimal
    moneda: str
    vigente_desde: date
    variacion_pct: Decimal
    salto_grande: bool


class PanelPrecioViejoOut(Salida):
    material: str
    color: str | None
    vigente_desde: date


class PanelPreciosViejosOut(Salida):
    cantidad: int
    mas_viejos: list[PanelPrecioViejoOut]


class PanelDolarOut(Salida):
    fecha: date
    ars_por_usd: Decimal
    fuente: str


class PanelAvisoOut(Salida):
    codigo: str
    texto: str


class PeriodoEscenarioOut(Salida):
    periodo: str


class PanelCostosOut(Salida):
    periodo: str
    periodo_anterior: str
    actual: PanelPeriodoOut
    anterior: PanelPeriodoOut
    variacion_pct: PanelVariacionOut
    precios_que_subieron: list[PanelPrecioSubioOut]
    precios_viejos: PanelPreciosViejosOut
    dolar: PanelDolarOut | None
    dolar_viejo: bool
    avisos: list[PanelAvisoOut]


class CompraReventaOut(Salida):
    fecha: date
    unidades: Decimal | None
    costo_unitario_ars: Decimal
    costo_total_ars: Decimal | None
    precio_venta_unitario_ars: Decimal | None
    margen_unitario_ars: Decimal | None
    margen_pct: Decimal | None
    proveedor: str | None
    nota: str | None
    creado_por: str | None
    creado_en: datetime | None


class ProductoReventaOut(Salida):
    codigo: str
    nombre: str
    categoria: str | None
    proveedor: str | None
    nota: str | None
    activo: bool
    costo_unitario_ars: Decimal | None
    precio_venta_unitario_ars: Decimal | None
    margen_unitario_ars: Decimal | None
    margen_pct: Decimal | None
    ultima_compra: date | None
    compras: int
    unidades_compradas: Decimal


class ProductoReventaDetalleOut(ProductoReventaOut):
    historial: list[CompraReventaOut]


class ImpuestoDelPrecioOut(Salida):
    codigo: str
    nombre: str
    alicuota: Decimal
    monto: Decimal


class PrecioVentaOut(Salida):
    producto: str
    precio_ars: Decimal
    margen: Decimal | None
    vigente_desde: date
    nota: str | None
    creado_por: str | None
    creado_en: datetime | None
    # Taxes of today over `precio_ars` (the price without taxes); the cost never carries them.
    impuestos: list[ImpuestoDelPrecioOut] = []
    total_impuestos: Decimal | None = None
    precio_final: Decimal | None = None


class RentabilidadOut(Salida):
    producto: str
    fuente_precio: Literal["INGRESADO", "GUARDADO"] | None
    precio: Decimal | None
    costo_variable: Decimal | None
    margen_unidad: Decimal | None
    margen_pct: Decimal | None
    markup_pct: Decimal | None
    veredicto: Literal["NO_CUBRE_VARIABLE", "MC_BAJO", "SALUDABLE"] | None
    motivo: Literal["SIN_PRECIO", "SIN_COSTO_VARIABLE"] | None


class PrecioSugeridoOut(Salida):
    producto: str
    costo: Decimal | None
    margen_pct: Decimal
    precio: Decimal | None


class EscenarioFijosOut(Salida):
    total_fabrica: Decimal
    cargados: bool
    pendientes: int
    ficticios: bool


class EscenarioResultadoOut(Salida):
    ingresos: Decimal | None
    margen_contribucion: Decimal | None
    margen_contribucion_pct: Decimal | None
    costos_fijos: Decimal | None
    utilidad: Decimal | None
    equilibrio_ingresos: Decimal | None
    equilibrio_unidades: Decimal | None
    margen_seguridad_pct: Decimal | None
    motivo: Literal["SIN_VENTAS", "MC_NO_POSITIVO"] | None


class EscenarioLineaOut(Salida):
    codigo: str
    unidades: Decimal
    precio: Decimal
    fuente_precio: Literal["INGRESADO", "GUARDADO"]
    costo_variable: Decimal
    gasto_venta_unidad: Decimal
    iibb_unidad: Decimal
    margen_unidad: Decimal
    margen_pct: Decimal | None
    veredicto: Literal["NO_CUBRE_VARIABLE", "MC_BAJO", "SALUDABLE"]
    contribucion_total: Decimal
    participacion_pct: Decimal | None
    horas_confeccion: Decimal | None
    margen_por_hora: Decimal | None
    ranking_por_hora: int | None


class EscenarioOmitidoOut(Salida):
    codigo: str
    motivo: Literal["PRODUCTO_NO_ENCONTRADO", "SIN_PRECIO", "SIN_COSTO_VARIABLE"]


class EscenarioOut(Salida):
    periodo: str
    fijos: EscenarioFijosOut
    resultado: EscenarioResultadoOut
    lineas: list[EscenarioLineaOut]
    omitidos: list[EscenarioOmitidoOut]
    mejor_por_hora: str | None
    avisos: list[PanelAvisoOut]
    confiable: bool


class TendenciaMesOut(Salida):
    periodo: str
    unidades: Decimal
    unidades_sin_costo: Decimal
    fijos_fabrica: Decimal
    fijos_cargados: bool
    fijos_pendientes: int
    fijos_ficticios: bool
    costo_variable_por_unidad: Decimal | None
    fijo_por_unidad: Decimal | None
    total_por_unidad: Decimal | None
    incompleto: list[str]
    variacion_pct_total_por_unidad: Decimal | None


class TendenciaOut(Salida):
    hasta: str
    meses: list[TendenciaMesOut]
    nota: str


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


class UnidadProductoOut(Salida):
    producto: str
    producto_nombre: str
    categoria: str | None
    unidades: Decimal
    lotes: int


class UnidadesProducidasOut(Salida):
    periodo: str | None
    productos: list[UnidadProductoOut]
    total_unidades: Decimal


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


class LoteDeTallerOut(Salida):
    lote: str
    fecha: date | None
    estado: str
    productos: int
    unidades: Decimal
    unidades_con_precio_pagado: Decimal
    total_cotizado: Decimal
    total_pagado: Decimal
    precio_pagado_promedio: Decimal | None
    barra_pct: int | None


class PagoDeProductoOut(Salida):
    item: str
    fecha: date | None
    lote: str
    cantidad: Decimal
    cotizado: Decimal | None
    pagado: Decimal | None
    variacion_pct: Decimal | None
    salto_grande: bool
    barra_pct: int | None


class ProductoDeTallerOut(Salida):
    producto: str
    producto_nombre: str
    categoria: str | None
    lotes: int
    unidades: Decimal
    primer_pagado: Decimal | None
    ultimo_pagado: Decimal | None
    variacion_ultima_pct: Decimal | None
    variacion_total_pct: Decimal | None
    ultima_fecha: date | None
    historial: list[PagoDeProductoOut]


class HistorialDeTallerOut(Salida):
    taller: str
    taller_nombre: str
    lotes: list[LoteDeTallerOut]
    productos: list[ProductoDeTallerOut]


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


class ReferenciaItemOut(Salida):
    fecha: date
    dias: int
    producto: str
    nombre: str
    tamano: str | None
    taller: str
    taller_nombre: str | None
    cantidad: Decimal
    precio: Decimal
    lote: str
    veces: int
    precio_anterior: Decimal | None
    variacion_pct: Decimal | None


class ReferenciaOut(Salida):
    nivel: Literal["MISMO_PRODUCTO", "MISMA_CATEGORIA_Y_TAMANO", "MISMA_CATEGORIA", "SIN_DATOS"]
    categoria: str | None
    tamano: str | None
    items: list[ReferenciaItemOut]


class PreciosTalleresOut(Salida):
    producto: str
    nombre: str
    categoria: str | None
    tamano: str | None
    veces_en_taller: int
    por_taller: list[PrecioPorTallerOut]
    parecidos: list[PrecioParecidoOut]
    referencia: ReferenciaOut


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

EstadoDelCiclo = Literal["EN_DEFINICION", "COTIZADO", "EN_PRODUCCION", "PRODUCIDO"]


def _filtros_extra_de_productos(sin_cuero: bool, sin_color: bool, estado: str | None) -> dict:
    """The leather / color / state filters of the list, only the active ones, so no filter means the same call as before."""
    activos = {"sin_cuero": sin_cuero or None, "sin_color": sin_color or None, "estado": estado}
    return {nombre: valor for nombre, valor in activos.items() if valor is not None}


@router.get("/productos", dependencies=LECTURA_GENERAL, response_model=list[ProductoResumen])
def productos(
    session: Sesion, usuario: Annotated[Usuario, Depends(require_user)], limit: int = Query(100, ge=1, le=500), offset: int = Query(0, ge=0),
    q: str | None = Query(None, max_length=100), categoria: str | None = None,
    revisar: bool = Query(False, description="true: only products whose note has a `REVISAR:` mark; false: no filter."),
    sin_cuero: bool = Query(False, description="true: only products with no leather chosen; false: no filter."),
    sin_color: bool = Query(False, description="true: only products with no color chosen; false: no filter."),
    estado: EstadoDelCiclo | None = Query(None, description="Only the products in this lifecycle state."),
):
    # Sale prices are for admin and gerente (PRODUCTOS); the taller reads the same list without them.
    # Only sent when it is False, like the filters above: admin and gerente call the service as before.
    sin_precios = {} if usuario.roles & PRODUCTOS.roles_permitidos else {"con_precios": False}
    return servicios.listar_productos(
        session, limit, offset, q, categoria, revisar, **_filtros_extra_de_productos(sin_cuero, sin_color, estado),
        **sin_precios,
    )


# Declared before `/productos/{codigo}` so "conteo" is not read as a product code.
# Same filters as `/productos`; open to every role because it paginates the list, which taller also reads.
@router.get("/productos/conteo", dependencies=LECTURA_GENERAL, response_model=ConteoOut)
def productos_conteo(
    session: Sesion, q: str | None = Query(None, max_length=100), categoria: str | None = None,
    revisar: bool = Query(False, description="true: only products whose note has a `REVISAR:` mark; false: no filter."),
    sin_cuero: bool = Query(False, description="true: only products with no leather chosen; false: no filter."),
    sin_color: bool = Query(False, description="true: only products with no color chosen; false: no filter."),
    estado: EstadoDelCiclo | None = Query(None, description="Only the products in this lifecycle state."),
):
    extra = _filtros_extra_de_productos(sin_cuero, sin_color, estado)
    return {"total": servicios.contar_productos(session, q, categoria, revisar, **extra)}


@router.get("/productos/{codigo}", dependencies=LECTURA_GENERAL, response_model=FichaOut)
def ficha(codigo: str, session: Sesion):
    return servicios.ficha_producto(session, codigo)


@router.get("/modelos", dependencies=LECTURA_GENERAL, response_model=list[ModeloOut])
def modelos(
    session: Sesion, limit: int = Query(500, ge=1, le=1000), offset: int = Query(0, ge=0),
    q: str | None = Query(None, max_length=100), categoria: str | None = None, validado: bool | None = None,
    tamano: Literal[*servicios.TAMANOS] | None = None,
):
    return servicios.listar_modelos(session, limit, offset, q, categoria, validado, tamano)


@router.get("/modelos/{codigo}", dependencies=LECTURA_GENERAL, response_model=ModeloDetalleOut)
def modelo(codigo: str, session: Sesion):
    return servicios.detalle_modelo(session, codigo)


@router.get("/materiales", dependencies=LECTURA_GENERAL, response_model=list[MaterialOut])
def materiales(session: Sesion):
    return servicios.listar_materiales(session)


@router.get("/cueros", dependencies=LECTURA_CORTE, response_model=list[GrupoCueroOut])
def listar_cueros(session: Sesion, material: str | None = None, color: str | None = None):
    return cueros.listar_cueros(session, material, color)


@router.get("/cueros/alcanza", dependencies=LECTURA_CORTE, response_model=AlcanzaCueroOut)
def alcanza_cuero(
    session: Sesion, producto: str, cantidad: Annotated[Decimal, Query(gt=0, max_digits=12, decimal_places=6)],
):
    return cueros.alcanza(session, producto, cantidad)


@router.get("/cueros/{codigo}", dependencies=LECTURA_CORTE, response_model=PiezaCueroDetalleOut)
def detalle_cuero(codigo: str, session: Sesion):
    return cueros.detalle_pieza(session, codigo)


@router.post("/cueros", dependencies=ESCRITURA, response_model=PiezaCueroDetalleOut, status_code=201)
def alta_cuero(cuerpo: PiezaCueroIn, session: Sesion):
    return cueros.crear_pieza(session, **cuerpo.model_dump())


@router.post("/cueros/{codigo}/cortes", dependencies=CORTES, response_model=PiezaCueroDetalleOut, status_code=201)
def cortar_cuero(codigo: str, cuerpo: CorteCueroIn, session: Sesion):
    return cueros.cortar(session, codigo, **{**cuerpo.model_dump(), "fecha": cuerpo.fecha or date.today()})


@router.post("/cueros/{codigo}/sobrante", dependencies=CORTES, response_model=PiezaCueroDetalleOut)
def sobrante_cuero(codigo: str, cuerpo: SobranteCueroIn, session: Sesion):
    return cueros.decidir_sobrante(session, codigo, decision=cuerpo.decision, fecha=cuerpo.fecha or date.today())


@router.get("/precios", dependencies=LECTURA_CORTE, response_model=list[PrecioOut])
def precios(session: Sesion, material: str | None = None, a_fecha: date | None = None):
    return servicios.listar_precios(session, material, a_fecha)


@router.get("/precios/chequeo", dependencies=LECTURA_ADMIN, response_model=PrecioChequeoOut)
def precio_chequeo(
    session: Sesion, material: str, precio: Annotated[Decimal, Query(ge=0, max_digits=14, decimal_places=4)],
    moneda: Literal[*ARS_USD], vigente_desde: date, color: str | None = None,
):
    """How far a price about to be loaded is from the previous one. Reads only; saves nothing."""
    return servicios.chequear_precio(session, material, color, precio, moneda, vigente_desde)


@router.get("/catalogos", dependencies=LECTURA_GENERAL, response_model=CatalogosOut)
def catalogos(session: Sesion):
    return servicios.listar_catalogos(session)


@router.get("/colores", dependencies=LECTURA_CORTE, response_model=list[CatalogoItemOut])
def colores(session: Sesion):
    return servicios.listar_colores(session)


@router.get("/categorias", dependencies=LECTURA_CORTE, response_model=list[CatalogoItemOut])
def categorias(session: Sesion):
    return servicios.listar_categorias(session)


@router.get("/impuestos", dependencies=LECTURA_ADMIN, response_model=list[ImpuestoOut])
def impuestos(session: Sesion):
    """Every tax, active or not. Whether VAT counts as a product cost is an open business decision and is not edited."""
    return servicios.listar_impuestos(session)


@router.get("/dolar", dependencies=LECTURA_CORTE, response_model=list[DolarOut])
def dolar(session: Sesion):
    return servicios.listar_dolar(session)


@router.get("/parametros", dependencies=LECTURA_ADMIN, response_model=list[ParametroOut])
def parametros(session: Sesion):
    return servicios.listar_parametros(session)


@router.get("/talleres", dependencies=LECTURA_ADMIN, response_model=list[TallerOut])
def talleres(session: Sesion):
    return servicios.listar_talleres(session)


@router.get("/personas", dependencies=LECTURA_ADMIN, response_model=list[PersonaOut])
def personas(session: Sesion):
    return servicios.listar_personas(session)


@router.get("/talleres/{codigo}", dependencies=LECTURA_ADMIN, response_model=TallerDetalleOut)
def taller(codigo: str, session: Sesion):
    return servicios.detalle_taller(session, codigo)


@router.get("/talleres/{codigo}/historial", dependencies=LECTURA_ADMIN, response_model=HistorialDeTallerOut)
def historial_de_taller(codigo: str, session: Sesion):
    """Lots given to the workshop (units, total paid) and, per product, what was paid each time and how it changed."""
    return servicios.historial_taller(session, codigo)


@router.get("/costos-fijos", dependencies=LECTURA_ADMIN, response_model=CostosFijosOut)
def costos_fijos(session: Sesion, periodo: Annotated[str | None, Query(pattern=PERIODO)] = None):
    return servicios.costos_fijos(session, periodo)


@router.get("/panel/costos", dependencies=LECTURA_ADMIN, response_model=PanelCostosOut)
def panel_de_costos(
    session: Sesion, periodo: Annotated[str | None, Query(pattern=PERIODO)] = None,
    precio: Annotated[Decimal | None, Query(gt=0, max_digits=14, decimal_places=4)] = None,
):
    """Cost of the month (default: this calendar month) against the previous one; `precio` only feeds the break-even simulator."""
    return servicios.panel_de_costos(session, periodo, precio)


@router.get("/productos/{codigo}/precio-venta", dependencies=LECTURA_PRODUCTOS, response_model=list[PrecioVentaOut])
def historial_de_precio_de_venta(codigo: str, session: Sesion):
    """Saved sale prices of the product, newest first."""
    return servicios.listar_precios_de_venta(session, codigo)


@router.get("/productos/{codigo}/rentabilidad", dependencies=LECTURA_PRODUCTOS, response_model=RentabilidadOut)
def rentabilidad_de_producto(
    codigo: str, session: Sesion,
    precio: Annotated[Decimal | None, Query(gt=0, max_digits=14, decimal_places=4)] = None,
):
    """Contribution margin at `precio` (typed) or at the latest saved price; saves nothing."""
    return servicios.rentabilidad_de_producto(session, codigo, precio)


@router.get("/productos/{codigo}/precio-sugerido", dependencies=LECTURA_PRODUCTOS, response_model=PrecioSugeridoOut)
def precio_sugerido_de_producto(
    codigo: str, session: Sesion,
    margen: Annotated[Decimal, Query(ge=0, lt=100, max_digits=6, decimal_places=3)],
):
    """Price that leaves `margen` % of the sale price over today's cost (cost / (1 - margin)); saves nothing."""
    return servicios.precio_sugerido_de_producto(session, codigo, margen)


@router.get("/panel/tendencia", dependencies=LECTURA_ADMIN, response_model=TendenciaOut)
def tendencia_de_costos(
    session: Sesion, hasta: Annotated[str | None, Query(pattern=PERIODO)] = None,
    meses: Annotated[int, Query(ge=1, le=servicios.MAX_MESES_DE_TENDENCIA)] = servicios.MESES_DE_TENDENCIA,
):
    """Last `meses` months ending at `hasta` (default: this calendar month), oldest first; incomplete months are listed with reasons."""
    return servicios.tendencia_de_costos(session, hasta, meses)


@router.get("/costos-fijos/periodos", dependencies=LECTURA_ADMIN, response_model=PeriodosOut)
def periodos_de_costos_fijos(session: Sesion):
    return servicios.periodos_de_costos_fijos(session)


@router.get("/ordenes", dependencies=LECTURA_CORTE, response_model=list[OrdenResumenOut])
def ordenes(
    session: Sesion, estado: Literal[*LOT_STATES] | None = None, donde: Literal[*WHERE_MADE] | None = None,
    taller: str | None = None,
):
    return servicios.listar_ordenes(session, estado, donde, taller)


@router.get("/ordenes/unidades-por-producto", dependencies=LECTURA_ADMIN, response_model=UnidadesProducidasOut)
def unidades_por_producto(session: Sesion, periodo: str | None = Query(None, pattern=PERIODO)):
    return servicios.unidades_por_producto(session, periodo)


@router.get("/ordenes/{codigo}", dependencies=LECTURA_CORTE, response_model=OrdenDetalleOut)
def orden(codigo: str, session: Sesion):
    return servicios.detalle_orden(session, codigo)


@router.get("/fabricacion/casa-vs-taller", dependencies=LECTURA_ADMIN, response_model=CasaVsTallerOut)
def casa_vs_taller(session: Sesion, hasta: Annotated[str | None, Query(pattern=PERIODO)] = None):
    """The last 12 months up to `hasta` (default: this month). A lot counts in the month of its delivery date, else of its shipping date."""
    return servicios.casa_vs_taller(session, hasta)


@router.get("/productos/{codigo}/precios-talleres", dependencies=LECTURA_ADMIN, response_model=PreciosTalleresOut)
def precios_de_talleres(codigo: str, session: Sesion, mismo_tamano: bool = True):
    return servicios.precios_de_talleres(session, codigo, date.today(), mismo_tamano)


@router.get("/calidad", dependencies=LECTURA_ADMIN, response_model=CalidadOut)
def calidad(session: Sesion):
    return servicios.calidad_de_datos(session)


# --- Write ----------------------------------------------------------------------------------------------------

@router.post("/productos", dependencies=ESCRITURA, response_model=FichaOut, status_code=201)
def crear_producto(cuerpo: ProductoIn, session: Sesion):
    return servicios.crear_producto(session, **cuerpo.model_dump())


@router.post("/productos/{codigo}/precio-venta", dependencies=ESCRITURA, response_model=PrecioVentaOut, status_code=201)
def guardar_precio_de_venta(codigo: str, cuerpo: PrecioVentaIn, session: Sesion, usuario: Escritor):
    """Appends a dated sale price; history is never edited or deleted."""
    return servicios.guardar_precio_de_venta(
        session, codigo, precio_ars=cuerpo.precio_ars, vigente_desde=cuerpo.vigente_desde, nota=cuerpo.nota,
        margen=cuerpo.margen, quien=usuario.id,
    )


@router.post("/productos/precios-lote", dependencies=ESCRITURA, response_model=list[ProductoResumen])
def guardar_precios_por_margen(cuerpo: PreciosLoteIn, session: Sesion, usuario: Escritor):
    """Grid save: a new sale price per product = today's cost / (1 - margin). All rows or none; history is only appended."""
    return servicios.guardar_precios_por_margen(
        session, [item.model_dump() for item in cuerpo.items], quien=usuario.id)


@router.get("/cvu/periodo", dependencies=LECTURA_PRODUCTOS, response_model=PeriodoEscenarioOut)
def periodo_del_escenario():
    """The month the simulator starts on (this calendar month). Nothing else of the Panel: that one is admin only."""
    return {"periodo": servicios.mes_de(date.today())}


@router.post("/cvu/escenario", dependencies=LECTURA_PRODUCTOS, response_model=EscenarioOut)
def escenario_cvu(cuerpo: EscenarioIn, session: Sesion):
    """Break-even of the factory for a mix typed by the owner. A POST only because of the body: it reads and saves nothing."""
    return servicios.escenario_cvu(session, cuerpo.periodo, [item.model_dump() for item in cuerpo.items])


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


@router.post("/dolar/actualizar-bna", dependencies=ESCRITURA, response_model=DolarBnaOut)
def actualizar_dolar_bna(session: Sesion):
    """Loads the BNA sell quote of the day from bna.com.ar. No body: the page is never supplied by the client.
    Idempotent (`ya_existia` changes nothing); 502 with a fixed Spanish message when the BNA page fails."""
    return servicios.actualizar_dolar_bna(session)


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


# SUPUESTO: validar. A taller loads its own price by voice (S3 of the roles feature); nothing else of /ordenes.
@router.post("/ordenes/{codigo}/items/{item}/precios", dependencies=CORTES, response_model=OrdenDetalleOut)
def registrar_precios_de_item(codigo: str, item: str, cuerpo: PreciosItemIn, session: Sesion):
    return servicios.registrar_precios_item(session, codigo, item, **cuerpo.model_dump())


@router.post("/talleres", dependencies=ESCRITURA, response_model=TallerDetalleOut, status_code=201)
def crear_taller(cuerpo: TallerIn, session: Sesion):
    return servicios.crear_taller(session, **cuerpo.model_dump())


@router.post("/talleres/{codigo}/activo", dependencies=ESCRITURA, response_model=TallerDetalleOut)
def cambiar_activo_de_taller(codigo: str, cuerpo: ActivoIn, session: Sesion):
    return servicios.cambiar_activo_taller(session, codigo, cuerpo.activo)


@router.post("/costos-fijos/lote", dependencies=ESCRITURA, response_model=CostosFijosOut)
def guardar_costos_fijos_en_lote(cuerpo: GastosLoteIn, session: Sesion):
    """Grid save of one month: corrections (new rows that replace), new rows and annulments, all or nothing."""
    return servicios.guardar_gastos_en_lote(
        session, cuerpo.periodo, [c.model_dump(exclude_unset=True) for c in cuerpo.cambios],
        [n.model_dump() for n in cuerpo.nuevos], anulados=cuerpo.anulados)


@router.post("/costos-fijos/{codigo}/monto", dependencies=ESCRITURA, response_model=CostosFijosOut)
def cargar_monto_de_gasto(codigo: str, cuerpo: MontoIn, session: Sesion):
    """Only while the amount is still empty (409 otherwise): a correction goes through `/corregir`."""
    return servicios.cargar_monto_de_gasto(session, codigo, cuerpo.monto_ars_del_mes)


@router.post("/costos-fijos/{codigo}/corregir", dependencies=ESCRITURA, response_model=CostosFijosOut, status_code=201)
def corregir_gasto(codigo: str, cuerpo: CorreccionIn, session: Sesion):
    """Creates a NEW row that replaces `codigo` (kept, no longer counted); 409 if it was already replaced."""
    return servicios.corregir_gasto(
        session, codigo, cuerpo.monto_ars_del_mes, nota=cuerpo.nota, ficticio=cuerpo.ficticio)


@router.post("/costos-fijos/{codigo}/anular", dependencies=ESCRITURA, response_model=CostosFijosOut)
def anular_gasto(codigo: str, session: Sesion):
    """Soft delete: the row is kept flagged `anulado` and stops counting; 409 if it was already corrected or annulled."""
    return servicios.anular_gasto(session, codigo)


@router.post("/costos-fijos/copiar", dependencies=ESCRITURA, response_model=CostosFijosOut, status_code=201)
def copiar_mes_de_gastos(cuerpo: CopiaIn, session: Sesion):
    """Copies the current rows of `desde` into `hasta`; 422 if `desde` is empty, 409 if `hasta` already has rows."""
    return servicios.copiar_mes_de_gastos(session, cuerpo.desde, cuerpo.hasta, con_montos=cuerpo.con_montos,
                                           categorias=cuerpo.categorias)


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


@router.post("/impuestos", dependencies=ADMINISTRACION, response_model=ImpuestoOut, status_code=201)
def crear_impuesto(cuerpo: ImpuestoIn, session: Sesion):
    """A tax on the sale price (not on the cost): name and percentage, as a fraction (0.21 = 21 %)."""
    return servicios.crear_impuesto(session, **cuerpo.model_dump())


@router.post("/impuestos/{codigo}/alicuota", dependencies=ADMINISTRACION, response_model=ImpuestoOut)
def cambiar_alicuota_de_impuesto(codigo: str, cuerpo: AlicuotaIn, session: Sesion, usuario: Escritor):
    return servicios.cambiar_alicuota_impuesto(session, codigo, cuerpo.alicuota, usuario.id)


@router.post("/impuestos/{codigo}/activo", dependencies=ADMINISTRACION, response_model=ImpuestoOut)
def cambiar_activo_de_impuesto(codigo: str, cuerpo: ActivoIn, session: Sesion):
    """Nothing is deleted: a deactivated tax stops showing in the price breakdown."""
    return servicios.cambiar_activo_impuesto(session, codigo, cuerpo.activo)


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


@router.post("/modelos/consumos/lote")
def cambiar_consumos_en_lote(cuerpo: ConsumosLoteIn, session: Sesion, usuario: SoloAdmin):
    """Admin only. Grid save: all rows or none; each row resets `validado` like the single-model route."""
    return servicios.cambiar_consumos_en_lote(
        session, [f.model_dump() for f in cuerpo.filas], quien=usuario.id)


@router.post("/modelos/{codigo}/validado", dependencies=ESCRITURA, response_model=ModeloDetalleOut)
def cambiar_validado_de_modelo(codigo: str, cuerpo: ValidadoIn, session: Sesion):
    return servicios.cambiar_validado(session, codigo, cuerpo.validado)


@router.post("/modelos/{codigo}/consumos", response_model=ModeloDetalleOut)
def cambiar_consumos_de_modelo(codigo: str, cuerpo: ConsumosIn, session: Sesion, usuario: SoloAdmin):
    """Admin only. Overwrites the consumptions, resets `validado` and logs the previous values."""
    return servicios.cambiar_consumos(session, codigo, quien=usuario.id, **cuerpo.model_dump())


# --- Google Sheet display copy (T6) ------------------------------------------------------------------------------
# The Sheet is DISPLAY ONLY: the app builds the tabs (sheets_export.py), pushes them (sheets_client.py) and never reads
# anything back. Admin only to run, preview or read the status.

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


class FilaGrillaOut(Salida):
    codigo: str
    catalogo: list[str]
    costos_variables: list[str]


class GrillaOut(Salida):
    encabezados_catalogo: list[str]
    encabezados_costos_variables: list[str]
    filas: list[FilaGrillaOut]


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


@router.get("/grilla", dependencies=LECTURA_ADMIN, response_model=GrillaOut)
def obtener_grilla(
    fuente: Annotated[Fuente, Depends(get_fuente_sheets)],
    texto: str = "",
    categoria: str = "",
):
    hoy = ahora().date()
    catalogo = _catalogo(fuente, hoy)
    costos = _costos_variables(fuente, hoy)
    costos_por_codigo = {fila[0]: fila for fila in costos.rows}
    texto_buscado = texto.strip().casefold()
    categoria_buscada = categoria.strip().casefold()
    filas = []
    for fila in catalogo.rows:
        codigo, nombre, categoria_producto = (_texto_de_celda(celda) for celda in fila[:3])
        if texto_buscado and texto_buscado not in codigo.casefold() and texto_buscado not in nombre.casefold():
            continue
        if categoria_buscada and categoria_producto.casefold() != categoria_buscada:
            continue
        filas.append({
            "codigo": codigo,
            "catalogo": [_texto_de_celda(celda) for celda in fila],
            "costos_variables": [_texto_de_celda(celda) for celda in costos_por_codigo[codigo]],
        })
    return {
        "encabezados_catalogo": list(catalogo.headers),
        "encabezados_costos_variables": list(costos.headers),
        "filas": filas,
    }


@router.get("/sync/sheets/estado", dependencies=LECTURA_ADMIN, response_model=EstadoSincronizacionOut)
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


# --- Suppliers and their documents (invoices, images) ------------------------------------------------------------------
# Admin only, reads and writes alike. The files live in the database; the OCR text is untrusted data and travels as plain
# JSON text. The OCR never fills the typed fields (a person confirms them) and never creates or changes a price.

DocumentoId = Annotated[int, Path(ge=1, le=2**63 - 1)]
NumeroDeDocumento = Annotated[str, Field(max_length=proveedores.MAX_NUMBER_LENGTH)]
TotalDeDocumento = Annotated[Decimal, Field(ge=0, max_digits=14, decimal_places=4)]


class ProveedorDatosIn(Entrada):
    nombre: Annotated[str, Field(min_length=1, max_length=200)]
    cuit: Annotated[str, Field(max_length=40)] | None = None
    contacto: Annotated[str, Field(max_length=200)] | None = None
    telefono: Annotated[str, Field(max_length=100)] | None = None
    direccion: Annotated[str, Field(max_length=300)] | None = None
    nota: Annotated[str, Field(max_length=2000)] | None = None


class ProveedorIn(ProveedorDatosIn):
    # SUPUESTO: validar. Optional PRV-NNNN code; without it the next free number is assigned.
    codigo: Annotated[str, Field(pattern=r"^PRV-[0-9]{4,}$", max_length=20)] | None = None


class DatosDeDocumentoIn(Entrada):
    """What a person typed or confirmed. Nothing the OCR read, and nothing about the file, can be sent here."""
    tipo: Literal[*DOCUMENT_TYPES]
    numero: NumeroDeDocumento | None = None
    fecha_documento: date | None = None
    total: TotalDeDocumento | None = None
    moneda: Literal[*ARS_USD] | None = None


class ProveedorOut(Salida):
    codigo: str
    nombre: str
    cuit: str | None
    contacto: str | None
    telefono: str | None
    direccion: str | None
    nota: str | None
    activo: bool
    documentos: int


class SugerenciaOcrOut(Salida):
    """What the OCR thinks the document says; every value is text, the total included."""
    numero: str | None = None
    fecha: str | None = None
    total: str | None = None
    moneda: str | None = None


class DocumentoProveedorOut(Salida):
    """A stored document without its file (`contenido` is never part of a response model)."""
    id: int
    proveedor: str
    tipo: Literal[*DOCUMENT_TYPES]
    nombre_archivo: str
    mime: str
    tamano_bytes: int
    sha256: str
    numero: str | None
    fecha_documento: date | None
    total: Decimal | None
    moneda: Literal[*ARS_USD] | None
    ocr_estado: Literal["PENDIENTE", "LISTO", "ERROR", "NO_CONFIGURADO"]
    ocr_texto: str | None
    ocr_sugerencia: SugerenciaOcrOut | None
    ocr_error: str | None
    subido_por: str
    created_at: datetime


class PrecioDeProveedorIn(Entrada):
    """A price of a material from this supplier. The supplier comes from the URL, never from the body."""
    material: str
    color: str | None = None
    precio: Annotated[Decimal, Field(ge=0, max_digits=14, decimal_places=4)]
    moneda: Literal[*ARS_USD]
    unidad_del_precio: Literal[*UNITS]
    iva_incluido: bool = False
    vigente_desde: date
    nota_fuente: Annotated[str, Field(max_length=500)] | None = None


class PrecioHistorialOut(Salida):
    codigo: str
    vigente_desde: date
    precio: Decimal
    moneda: str
    unidad_del_precio: str
    iva_incluido: bool
    nota_fuente: str | None
    variacion_pct: Decimal | None
    salto_grande: bool
    barra_pct: int | None


class MaterialDeProveedorOut(Salida):
    material: str
    material_nombre: str
    color: str | None
    ultimo_precio: Decimal
    moneda: str
    unidad_del_precio: str
    ultima_fecha: date
    variacion_ultima_pct: Decimal | None
    variacion_total_pct: Decimal | None
    cargas: int
    historial: list[PrecioHistorialOut]


class MaterialesDeProveedorOut(Salida):
    proveedor: str
    proveedor_nombre: str
    materiales: list[MaterialDeProveedorOut]


class PedidoLineaIn(Entrada):
    """One material that arrived. The content is in the consumption unit of the material (m2, m, unidad...)."""
    material: str
    cantidad_presentaciones: Annotated[Decimal, Field(gt=0, max_digits=12, decimal_places=6)]
    presentacion: Annotated[str, Field(min_length=1, max_length=proveedores.MAX_PRESENTATION)]
    contenido_por_presentacion: Annotated[Decimal, Field(gt=0, max_digits=12, decimal_places=6)]
    precio_por_presentacion: Annotated[Decimal, Field(ge=0, max_digits=14, decimal_places=4)]
    moneda: Literal[*ARS_USD]
    iva_incluido: bool = False


class PedidoProveedorIn(Entrada):
    """An order from this supplier. The supplier comes from the URL, never from the body."""
    fecha_de_recepcion: date
    remito: Annotated[str, Field(max_length=proveedores.MAX_ORDER_TEXT)] | None = None
    documento_id: Annotated[int, Field(ge=1, le=2**63 - 1)] | None = None
    nota: Annotated[str, Field(max_length=2000)] | None = None
    lineas: Annotated[list[PedidoLineaIn], Field(min_length=1, max_length=200)]


class PedidoLineaOut(Salida):
    orden: int
    material: str
    material_nombre: str
    unidad_de_consumo: str
    cantidad_presentaciones: Decimal
    presentacion: str
    contenido_por_presentacion: Decimal
    precio_por_presentacion: Decimal
    moneda: str
    iva_incluido: bool
    precio_unitario: Decimal
    precio_codigo: str


class PedidoProveedorOut(Salida):
    codigo: str
    proveedor: str
    fecha_de_recepcion: date
    remito: str | None
    documento_id: int | None
    nota: str | None
    creado_por: str
    created_at: datetime
    lineas: list[PedidoLineaOut]


def get_ocr_llm() -> ocr_llm.OcrLLM | None:
    """The real reader while `ANTHROPIC_API_KEY` is set (building it makes no network call), else None."""
    return ocr_llm.create_client()


@router.get("/reventa", dependencies=LECTURA_ADMIN, response_model=list[ProductoReventaOut])
def listar_reventa(session: Sesion):
    return reventa.listar(session)


@router.post("/reventa", dependencies=ESCRITURA, response_model=ProductoReventaDetalleOut, status_code=201)
def crear_producto_de_reventa(cuerpo: ProductoReventaIn, session: Sesion):
    return reventa.crear(
        session, nombre=cuerpo.nombre, categoria=cuerpo.categoria, proveedor=cuerpo.proveedor, nota=cuerpo.nota,
    )


@router.post("/reventa/lote", dependencies=ESCRITURA, response_model=list[ProductoReventaOut])
def guardar_reventa_en_lote(cuerpo: ReventaLoteIn, session: Sesion, usuario: Escritor):
    """Grid save: edits, new products and price updates, all or nothing."""
    return reventa.guardar_en_lote(
        session, [c.model_dump(exclude_unset=True) for c in cuerpo.cambios], [n.model_dump() for n in cuerpo.nuevos],
        quien=usuario.id)


@router.get("/reventa/{codigo}", dependencies=LECTURA_ADMIN, response_model=ProductoReventaDetalleOut)
def detalle_de_reventa(codigo: str, session: Sesion):
    return reventa.detalle(session, codigo)


@router.post("/reventa/{codigo}/activo", dependencies=ESCRITURA, response_model=ProductoReventaDetalleOut)
def cambiar_activo_de_reventa(codigo: str, cuerpo: ActivoIn, session: Sesion):
    return reventa.cambiar_activo(session, codigo, cuerpo.activo)


@router.post("/reventa/{codigo}/compras", dependencies=ESCRITURA, response_model=ProductoReventaDetalleOut, status_code=201)
def registrar_compra_de_reventa(codigo: str, cuerpo: CompraReventaIn, session: Sesion, usuario: Escritor):
    """Appends a purchase (units and unit cost); history is never edited or deleted."""
    return reventa.registrar_compra(session, codigo, **cuerpo.model_dump(), quien=usuario.id)


@router.get("/proveedores", dependencies=LECTURA_ADMIN, response_model=list[ProveedorOut])
def listar_proveedores(
    session: Sesion, q: Annotated[str | None, Query(max_length=100)] = None, activo: bool | None = None,
):
    return proveedores.list_suppliers(session, q=q, activo=activo)


@router.post("/proveedores", dependencies=ESCRITURA, response_model=ProveedorOut, status_code=201)
def crear_proveedor(cuerpo: ProveedorIn, session: Sesion):
    return proveedores.create_supplier(session, **cuerpo.model_dump())


@router.get("/proveedores/{codigo}", dependencies=LECTURA_ADMIN, response_model=ProveedorOut)
def detalle_de_proveedor(codigo: str, session: Sesion):
    return proveedores.get_supplier(session, codigo)


@router.post("/proveedores/{codigo}", dependencies=ESCRITURA, response_model=ProveedorOut)
def editar_proveedor(codigo: str, cuerpo: ProveedorDatosIn, session: Sesion):
    return proveedores.update_supplier(session, codigo, **cuerpo.model_dump())


@router.post("/proveedores/{codigo}/activo", dependencies=ESCRITURA, response_model=ProveedorOut)
def cambiar_activo_de_proveedor(codigo: str, cuerpo: ActivoIn, session: Sesion):
    return proveedores.set_supplier_active(session, codigo, cuerpo.activo)


@router.get("/proveedores/{codigo}/materiales", dependencies=LECTURA_ADMIN, response_model=MaterialesDeProveedorOut)
def materiales_de_proveedor(codigo: str, session: Sesion):
    """The materials a supplier has priced and the history of each (oldest to newest in time, newest first in the list)."""
    return proveedores.list_supplier_materials(session, codigo)


@router.post("/proveedores/{codigo}/precios", dependencies=ESCRITURA, response_model=PrecioOut, status_code=201)
def cargar_precio_de_proveedor(codigo: str, cuerpo: PrecioDeProveedorIn, session: Sesion):
    """Adds a dated price of a material linked to this supplier (a new row; older ones are never changed)."""
    return proveedores.add_supplier_price(session, codigo, **cuerpo.model_dump())


@router.get("/proveedores/{codigo}/pedidos", dependencies=LECTURA_ADMIN, response_model=list[PedidoProveedorOut])
def listar_pedidos_de_proveedor(codigo: str, session: Sesion):
    """What arrived from this supplier, newest first, with the unit price each line created."""
    return proveedores.list_orders(session, codigo)


@router.post("/proveedores/{codigo}/pedidos", dependencies=ESCRITURA, response_model=PedidoProveedorOut, status_code=201)
def registrar_pedido_de_proveedor(codigo: str, cuerpo: PedidoProveedorIn, session: Sesion, usuario: Escritor):
    """Registers an order and the price of each line, all or nothing. Orders are never edited or deleted."""
    datos = cuerpo.model_dump()
    return proveedores.create_order(session, codigo, **datos, creado_por=usuario.id)


@router.get("/proveedores/{codigo}/documentos", dependencies=LECTURA_ADMIN, response_model=list[DocumentoProveedorOut])
def listar_documentos_de_proveedor(codigo: str, session: Sesion, q: Annotated[str | None, Query(max_length=100)] = None):
    """Newest first; `q` searches the file name, the number and the OCR text. Never includes the files."""
    return proveedores.list_documents(session, codigo, q=q)


@router.post("/proveedores/{codigo}/documentos", dependencies=ESCRITURA, response_model=DocumentoProveedorOut, status_code=201)
def subir_documento_de_proveedor(
    codigo: str, session: Sesion, usuario: Escritor, ocr: Annotated[ocr_llm.OcrLLM | None, Depends(get_ocr_llm)],
    archivo: Annotated[UploadFile, File()],
    tipo: Annotated[Literal[*DOCUMENT_TYPES], Form()],
    numero: Annotated[NumeroDeDocumento | None, Form()] = None,
    fecha_documento: Annotated[date | None, Form()] = None,
    total: Annotated[TotalDeDocumento | None, Form()] = None,
    moneda: Annotated[Literal[*ARS_USD] | None, Form()] = None,
):
    """Stores the file (10 MB at most; its type is checked by its bytes), then reads it with the OCR. The answer shows the
    stored document and its OCR state: without the model key the upload still works and the state is NO_CONFIGURADO."""
    contenido = archivo.file.read(proveedores.MAX_FILE_BYTES + 1)
    if len(contenido) > proveedores.MAX_FILE_BYTES:
        raise proveedores.ArchivoMuyGrande(proveedores.MESSAGE_TOO_BIG)
    return proveedores.add_document(
        session, codigo, contenido=contenido, nombre_archivo=archivo.filename, tipo=tipo, numero=numero,
        fecha_documento=fecha_documento, total=total, moneda=moneda, subido_por=usuario.id, ocr=ocr)


@router.get("/documentos-proveedor/{id}/archivo", dependencies=LECTURA_ADMIN, response_class=Response)
def archivo_de_documento(id: DocumentoId, session: Sesion):
    """The stored bytes with their detected type, `nosniff`, inline for images and attachment for PDF."""
    contenido, mime, nombre = proveedores.get_file(session, id)
    return Response(content=contenido, media_type=mime, headers=proveedores.file_headers(mime, nombre))


@router.post("/documentos-proveedor/{id}/ocr", dependencies=ESCRITURA, response_model=DocumentoProveedorOut)
def reintentar_ocr_de_documento(
    id: DocumentoId, session: Sesion, ocr: Annotated[ocr_llm.OcrLLM | None, Depends(get_ocr_llm)],
):
    return proveedores.retry_ocr(session, id, ocr=ocr)


@router.post("/documentos-proveedor/{id}/datos", dependencies=ESCRITURA, response_model=DocumentoProveedorOut)
def confirmar_datos_de_documento(id: DocumentoId, cuerpo: DatosDeDocumentoIn, session: Sesion):
    """The only update of a document: the type, number, date, total and currency a person confirms."""
    return proveedores.confirm_document_data(session, id, **cuerpo.model_dump())


# --- Consumption forms (formulario de consumos y herrajes) ---------------------------------------------------------------
# One digital sheet per new article; the rules, states and who may do what are in formulario.py. No costing happens here.
# Gates: read = admin, taller (the service shows the taller only ENVIADO / COMPLETADO); edit rows and complete =
# admin + taller (the service lets a taller touch only the rows, only while ENVIADO); everything else is admin only.

FormularioLector = Annotated[Usuario, Depends(FORMULARIO_LEER)]
FormularioTrabajador = Annotated[Usuario, Depends(FORMULARIO_TRABAJAR)]
Articulo = Annotated[str, Field(min_length=1, max_length=200)]
NotaDeFormulario = Annotated[str, Field(max_length=2000)]


class FormularioNuevoIn(Entrada):
    articulo: Articulo
    taller: Annotated[str, Field(max_length=40)] | None = None  # TAL-NNNN
    producto: Annotated[str, Field(max_length=40)] | None = None  # PRD-NNNN
    nota: NotaDeFormulario | None = None


class FormularioLineaIn(Entrada):
    seccion: Literal[*FORM_SECTIONS]
    nombre: Annotated[str, Field(min_length=1, max_length=200)]
    cantidad: Annotated[Decimal, Field(ge=0, max_digits=12, decimal_places=6)] | None = None
    comentario: Annotated[str, Field(max_length=2000)] | None = None


class FormularioGuardarIn(Entrada):
    """The full sheet: the order of `lineas` is the order of the rows inside each section."""
    articulo: Articulo
    nota: NotaDeFormulario | None = None
    lineas: Annotated[list[FormularioLineaIn], Field(max_length=formulario.MAX_LINEAS)]


class FormularioDevolverIn(Entrada):
    comentario: Annotated[str, Field(min_length=1, max_length=2000)]


class FormularioDuplicarIn(Entrada):
    articulo: Articulo


class FormularioLineaOut(Salida):
    seccion: Literal[*FORM_SECTIONS]
    orden: int
    nombre: str
    cantidad: Decimal | None
    comentario: str | None


class FormularioResumenOut(Salida):
    codigo: str
    articulo: str
    estado: Literal[*FORM_STATES]
    producto: str | None
    modelo: str | None
    taller: str | None
    creado_por: str
    created_at: datetime
    enviado_en: datetime | None
    completado_en: datetime | None
    validado_en: datetime | None


class FormularioOut(FormularioResumenOut):
    nota: str | None
    comentario_revision: str | None
    completado_por: str | None
    validado_por: str | None
    lineas: list[FormularioLineaOut]
    # Only the answer of `validar` fills it: the rows with a quantity that matched no material (not saved as supplies).
    sin_material: list[str] | None = None


@router.post("/formularios", response_model=FormularioOut, status_code=201)
def crear_formulario(cuerpo: FormularioNuevoIn, session: Sesion, usuario: SoloAdmin):
    """A BORRADOR with the preloaded rows (CONSUMOS and HERRAJES, empty quantities)."""
    return formulario.crear_formulario(session, quien=usuario.id, **cuerpo.model_dump())


class ProductoNuevoIn(Entrada):
    """A new model: name, category and notes. No consumption (the workshop measures it in the form that is sent)."""
    nombre: Annotated[str, Field(min_length=1, max_length=200)]
    categoria: str
    tamano: Literal[*servicios.TAMANOS] | None = None
    nota: NotaDeFormulario | None = None


class ProductoNuevoOut(BaseModel):
    modelo: str
    formulario: str
    nombre: str


@router.post("/productos/nuevo", response_model=ProductoNuevoOut, status_code=201)
def crear_producto_solo_con_nombre(cuerpo: ProductoNuevoIn, session: Sesion, usuario: SoloAdmin):
    """New model (name, category, size and notes; no consumption): the app makes the model code and its consumption form,
    already sent to the workshop, which reads the notes there. The product comes after the admin validates the form."""
    return formulario.alta_rapida(session, quien=usuario.id, **cuerpo.model_dump())


@router.get("/formularios", response_model=list[FormularioResumenOut])
def listar_formularios(
    session: Sesion, usuario: FormularioLector, q: Annotated[str | None, Query(max_length=100)] = None,
    estado: Literal[*FORM_STATES] | None = None, producto: Annotated[str | None, Query(max_length=40)] = None,
    modelo: Annotated[str | None, Query(max_length=40)] = None,
):
    """Newest first. A taller only gets the ENVIADO and COMPLETADO ones. `producto` (PRD-NNNN) / `modelo` (MOD-NNNN) keep the forms of that product / model."""
    return formulario.listar_formularios(
        session, q=q, estado=estado, producto=producto, modelo=modelo, roles=usuario.roles)


@router.get("/formularios/{codigo}", response_model=FormularioOut)
def obtener_formulario(codigo: str, session: Sesion, usuario: FormularioLector):
    """404 when it does not exist or the caller may not see it (a taller never sees BORRADOR or VALIDADO)."""
    return formulario.obtener_formulario(session, codigo, usuario.roles)


@router.put("/formularios/{codigo}", response_model=FormularioOut)
def guardar_formulario(codigo: str, cuerpo: FormularioGuardarIn, session: Sesion, usuario: FormularioTrabajador):
    """Replaces articulo, nota and the full set of rows. 409 if VALIDADO; a taller only edits rows, only while ENVIADO."""
    return formulario.guardar_formulario(
        session, codigo, articulo=cuerpo.articulo, nota=cuerpo.nota,
        lineas=[linea.model_dump() for linea in cuerpo.lineas], roles=usuario.roles)


@router.post("/formularios/{codigo}/enviar", response_model=FormularioOut)
def enviar_formulario(codigo: str, session: Sesion, usuario: SoloAdmin):
    """BORRADOR | ENVIADO -> ENVIADO."""
    return formulario.cambiar_estado(session, codigo, "enviar", roles=usuario.roles, quien=usuario.id)


@router.post("/formularios/{codigo}/completar", response_model=FormularioOut)
def completar_formulario(codigo: str, session: Sesion, usuario: FormularioTrabajador):
    """ENVIADO -> COMPLETADO."""
    return formulario.cambiar_estado(session, codigo, "completar", roles=usuario.roles, quien=usuario.id)


@router.post("/formularios/{codigo}/devolver", response_model=FormularioOut)
def devolver_formulario(codigo: str, cuerpo: FormularioDevolverIn, session: Sesion, usuario: SoloAdmin):
    """COMPLETADO -> ENVIADO with a review comment."""
    return formulario.cambiar_estado(
        session, codigo, "devolver", roles=usuario.roles, quien=usuario.id, comentario=cuerpo.comentario)


@router.post("/formularios/{codigo}/validar", response_model=FormularioOut)
def validar_formulario(codigo: str, session: Sesion, usuario: SoloAdmin):
    """COMPLETADO -> VALIDADO (immutable from then on)."""
    return formulario.cambiar_estado(session, codigo, "validar", roles=usuario.roles, quien=usuario.id)


@router.post("/formularios/{codigo}/duplicar", response_model=FormularioOut, status_code=201)
def duplicar_formulario(codigo: str, cuerpo: FormularioDuplicarIn, session: Sesion, usuario: SoloAdmin):
    """A new BORRADOR for another article copying the rows of this form, in any state."""
    return formulario.duplicar_formulario(session, codigo, articulo=cuerpo.articulo, quien=usuario.id, roles=usuario.roles)


# --- Voice module (T7) ---------------------------------------------------------------------------------------------------
# The model only EXTRACTS intent and raw mentions from one short sentence; `voz.proponer` resolves them against the database
# with deterministic code and answers a PROPOSAL (resolved fields, candidates, missing data, the endpoint and the body for
# it). Nothing is written here: the person confirms and the screen calls the existing write endpoints with their session.

MENSAJE_VOZ_SIN_CLAVE = "El módulo de voz no está configurado: falta la clave del modelo."
MENSAJE_VOZ_LIMITE = "Pediste demasiadas interpretaciones seguidas. Esperá un minuto y probá de nuevo."
# SUPUESTO: validar. 20 requests per minute per user, counted per process (lost on restart, each replica counts its own).
_LIMITADOR_VOZ = voz.LimitadorPorUsuario()


class InterpretarIn(Entrada):
    texto: Annotated[str, Field(min_length=1, max_length=voz_llm.MAX_TEXTO)]


class EstadoVozOut(Salida):
    configurado: bool
    acciones: list[str]
    max_caracteres: int
    limite_por_minuto: int


def get_voz_llm() -> voz_llm.VozLLM | None:
    """The real model client while `ANTHROPIC_API_KEY` is set (building it makes no network call), else None."""
    return voz_llm.crear_cliente()


def get_fuente_voz(session: Sesion) -> voz.FuenteVoz:
    return voz.FuenteSQL(session)


@router.get("/voz/estado", dependencies=LECTURA_CORTE, response_model=EstadoVozOut)
def estado_de_voz(llm: Annotated[voz_llm.VozLLM | None, Depends(get_voz_llm)]):
    """Whether the model is configured, yes or no: never the key, the model name or the address."""
    return {"configurado": llm is not None, "acciones": list(voz_llm.ACCIONES), "max_caracteres": voz_llm.MAX_TEXTO,
            "limite_por_minuto": _LIMITADOR_VOZ.maximo}


@router.post("/voz/interpretar", dependencies=CORTES, response_model=voz.PropuestaOut)
def interpretar_voz(
    cuerpo: InterpretarIn, usuario: Annotated[Usuario, Depends(require_user)],
    llm: Annotated[voz_llm.VozLLM | None, Depends(get_voz_llm)],
    fuente: Annotated[voz.FuenteVoz, Depends(get_fuente_voz)],
):
    """Interprets one sentence and answers a proposal. 503 without the model key, 429 over the per-user limit, 502 / 504
    (fixed Spanish message, never the provider's text) when the model fails. Saves nothing."""
    if llm is None:
        raise HTTPException(503, MENSAJE_VOZ_SIN_CLAVE)
    if not _LIMITADOR_VOZ.permitir(usuario.id):
        raise HTTPException(429, MENSAJE_VOZ_LIMITE, headers={"Retry-After": str(int(_LIMITADOR_VOZ.ventana))})
    hoy = ahora().date()  # the model is told the Argentine day, so "hoy / ayer / el lunes" come back as ISO dates
    try:
        interpretacion = llm.interpretar(cuerpo.texto, hoy)
    except voz_llm.ErrorDeVoz as error:
        logger.info("voz interpretar resultado=%s largo=%d", error.clase, len(cuerpo.texto))
        raise HTTPException(error.estado, error.mensaje) from None
    except Exception as error:  # noqa: BLE001 - the answer must never carry the raw error (it may hold the key)
        logger.warning("voz interpretar fallo inesperado: %s", type(error).__name__)
        raise HTTPException(502, voz_llm.MENSAJE_NO_DISPONIBLE) from None
    propuesta = voz.proponer(interpretacion, cuerpo.texto, hoy, fuente)
    logger.info("voz propuesta accion=%s faltantes=%d avisos=%d largo=%d", propuesta.accion, len(propuesta.faltantes),
                len(propuesta.avisos), len(cuerpo.texto))
    return propuesta


# --- Materials grid -------------------------------------------------------------------------------------------------------

class MaterialesLoteOut(Salida):
    precios: list[PrecioOut]  # the rows the save added (a price that did not change adds none)
    materiales_nuevos: list[str]


@router.post("/materiales/lote", dependencies=ESCRITURA, response_model=MaterialesLoteOut)
def guardar_materiales_en_lote(cuerpo: MaterialesLoteIn, session: Sesion):
    """Grid save: new prices (new dated rows, nothing is edited) and new materials, all or nothing."""
    return grilla_materiales.guardar_en_lote(
        session, [c.model_dump(exclude_unset=True) for c in cuerpo.cambios], [n.model_dump() for n in cuerpo.nuevos])


# --- Errors ----------------------------------------------------------------------------------------------------

def registrar_errores(app: FastAPI) -> None:
    """Map service errors to HTTP codes: 403 role cannot do it on this resource, 404 missing, 409 already there / invalid transition, 413 file too big, 422 refused, 502 outside source down."""

    @app.exception_handler(servicios.FuenteNoDisponible)
    async def fuente_no_disponible(request: Request, error: servicios.FuenteNoDisponible):
        return JSONResponse(status_code=502, content={"detail": str(error)})

    @app.exception_handler(proveedores.ArchivoMuyGrande)
    async def archivo_muy_grande(request: Request, error: proveedores.ArchivoMuyGrande):
        return JSONResponse(status_code=413, content={"detail": str(error)})

    @app.exception_handler(formulario.SinPermiso)
    async def sin_permiso(request: Request, error: formulario.SinPermiso):
        return JSONResponse(status_code=403, content={"detail": str(error)})

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
