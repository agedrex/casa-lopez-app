"""Service layer: loads rows, delegates every rule to the pure modules, persists snapshots.

Routers only call this module. Cost rules live in costeo.py and receta.py and are not
re-implemented here: this file loads plain data, calls them and stores the result.
Money is Decimal end to end; the API layer serializes it as strings.
"""

import logging
import re
import unicodedata
from collections import Counter
from dataclasses import dataclass, field, replace
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import Integer, and_, cast, func, or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, aliased

from backend.costeo import (
    Desglose, ItemLote, PrecioVigente, Precios, ZERO, confeccion_externa, costo_kit, necesita_recotizar,
)
from backend.models import (
    Categoria, Color, Cotizacion, Etapa, GastoPeriodo, Impuesto, KitComponente, Material, Modelo,
    OrdenEstado, OrdenFabricacion, OrdenItem, Parametro, Persona, PrecioMaterial, Producto, RecetaLinea, Taller,
    TipoCambio,
)
from backend.receta import (
    Cotizado, Extra, ModeloReceta, ProductoReceta, Receta, cotizar_producto, generar_receta,
)

# Audit lines (who changed which parameter or consumption) go to uvicorn's logger: uvicorn sets it to INFO, whereas the
# application's own root logger is left at WARNING and would drop them. Only ids and values are logged, never secrets.
logger = logging.getLogger("uvicorn.error")

QUOTE_TYPES = ("INICIAL", "RECOTIZACION", "FINAL")
# Product column that holds the date of each quote type.
DATE_OF_TYPE = {"INICIAL": "fecha_de_alta", "RECOTIZACION": "fecha_de_recotizacion", "FINAL": "fecha_de_cierre"}
# SUPUESTO: validar. Kits inside kits are allowed up to this depth; the sheet says nothing about it.
MAX_PROFUNDIDAD_KIT = 5
STAGE_COLUMNS = {
    "CUERO": "cuero", "FORRO": "forro", "FLEX": "flex", "GOMA_EVA": "goma_eva", "HERRAJES": "herrajes",
    "HILO_CEMENTO": "hilo_cemento", "CORTE": "corte", "CONFECCION": "confeccion",
}
UNIQUE_VIOLATION = "23505"
# SUPUESTO: validar. A price more than this many percent away from the previous one of the same material,
# color and currency is flagged (never blocked). The 50 comes from the task, not from the plantilla.
SALTO_PRECIO_PCT = Decimal("50")


class DatosInvalidos(ValueError):
    """The request cannot be honoured with the data given (HTTP 422)."""


class CotizacionIncompleta(DatosInvalidos):
    def __init__(self, avisos: list[str]):
        super().__init__("La cotización está incompleta: " + "; ".join(avisos) + ".")
        self.avisos = avisos


class NoEncontrado(LookupError):
    """The addressed resource does not exist (HTTP 404)."""


class Conflicto(Exception):
    """The row already exists; history is append-only, so nothing is updated (HTTP 409)."""


@dataclass(frozen=True)
class Parametros:
    desperdicio_default: Decimal
    arreglos_pct: Decimal
    tolerancia_desvio: Decimal | None
    variacion_dolar: Decimal | None
    iva_pct: Decimal
    iva_es_costo: bool


@dataclass(frozen=True)
class Contexto:
    """Everything shared by all quotes: prices, dollar history, stages, waste and parameters."""

    precios: Precios
    etapa_de_material: dict[str, str]
    desperdicio_manual: dict[str, Decimal]
    dolares: list[tuple[date, Decimal]]  # newest first
    parametros: Parametros


@dataclass(frozen=True)
class DatosProducto:
    id: int
    codigo: str
    nombre: str
    categoria: str | None
    modelo_codigo: str | None
    cuero: str | None
    color: str | None
    quien: str | None
    estado_del_ciclo: str
    es_kit: bool
    nota: str | None
    fecha_de_alta: date | None
    fecha_de_recotizacion: date | None
    fecha_de_cierre: date | None
    modelo: ModeloReceta
    extras: list[Extra] = field(default_factory=list)
    lotes: list[ItemLote] = field(default_factory=list)
    componentes: list[tuple[str, Decimal]] = field(default_factory=list)
    tamano: str | None = None

    @property
    def producto(self) -> ProductoReceta:
        return ProductoReceta(self.cuero, self.color, self.quien, self.es_kit)


@dataclass(frozen=True)
class ResultadoCotizacion:
    codigo: str
    fecha: date
    cotizado: Cotizado
    receta: Receta


# --- Pure part: rows already loaded -> dated quote ----------------------------------------------

def cotizar_datos(
    datos: DatosProducto, ctx: Contexto, fecha: date, catalogo: dict[str, DatosProducto],
    _ruta: tuple[str, ...] = (),
) -> ResultadoCotizacion:
    """Quote one product at `fecha`. `catalogo` must hold every kit component, recursively."""
    if datos.codigo in _ruta:
        raise DatosInvalidos("Hay un ciclo de kits: " + " > ".join((*_ruta, datos.codigo)) + ".")
    if len(_ruta) > MAX_PROFUNDIDAD_KIT:
        raise DatosInvalidos(f"Hay kits anidados a más de {MAX_PROFUNDIDAD_KIT} niveles.")
    receta = generar_receta(datos.modelo, datos.producto, datos.extras)
    confeccion = confeccion_externa(datos.lotes, receta.confeccion_estimada, fecha)

    avisos_kit: list[str] = []
    componentes: list[tuple[Decimal, Decimal]] = []
    for codigo, cantidad in datos.componentes:
        parcial = cotizar_datos(catalogo[codigo], ctx, fecha, catalogo, (*_ruta, datos.codigo)).cotizado
        if parcial.desglose is None or not parcial.completa:
            avisos_kit.append(f"El componente {codigo} está incompleto")
        else:
            # Plantilla rule (Cotizaciones!O): a component counts at its stage subtotal, so IVA and
            # repairs are applied once, on the kit's own subtotal plus components.
            componentes.append((cantidad, parcial.desglose.subtotal))
    if datos.es_kit and not datos.componentes:
        avisos_kit.append("El kit no tiene componentes")

    p = ctx.parametros
    cotizado = cotizar_producto(
        receta, ctx.precios, ctx.etapa_de_material, ctx.dolares, fecha,
        confeccion=confeccion, desperdicio_por_material=ctx.desperdicio_manual,
        desperdicio_default=p.desperdicio_default, componentes_kit=costo_kit(componentes),
        iva_es_costo=p.iva_es_costo, iva_pct=p.iva_pct, arreglos_pct=p.arreglos_pct,
    )
    if avisos_kit:
        cotizado = replace(cotizado, avisos=[*cotizado.avisos, *avisos_kit], completa=False)
    return ResultadoCotizacion(datos.codigo, fecha, cotizado, receta)


def fecha_de_cotizacion(datos: DatosProducto, tipo: str, fecha: date | None) -> date:
    """Date of a quote: the explicit one, else the product's date for that type."""
    if tipo not in QUOTE_TYPES:
        raise DatosInvalidos(f"El tipo de cotización debe ser uno de: {', '.join(QUOTE_TYPES)}.")
    elegida = fecha or getattr(datos, DATE_OF_TYPE[tipo])
    if elegida is None:
        raise DatosInvalidos(f"Falta la fecha: el producto no tiene {DATE_OF_TYPE[tipo]} y no se indicó una fecha.")
    return elegida


def columnas_cotizacion(desglose: Desglose) -> dict[str, Decimal]:
    columnas = {columna: desglose.etapas[etapa] for etapa, columna in STAGE_COLUMNS.items()}
    columnas.update(
        dolar=desglose.dolar, subtotal_etapas=desglose.subtotal, componentes_kit=desglose.componentes_kit,
        iva_compras=desglose.iva_compras, arreglos=desglose.arreglos,
        total_ars=desglose.total_ars, total_usd=desglose.total_usd,
    )
    return columnas


def marca_recotizar(
    desglose: Desglose | None, ultima_total: Decimal | None, ultima_dolar: Decimal | None, p: Parametros,
) -> bool | None:
    """RECOTIZAR flag; None when it cannot be decided (no stored quote, no cost today, no tolerance)."""
    if desglose is None or ultima_total is None or ultima_dolar is None:
        return None
    if p.tolerancia_desvio is None or p.variacion_dolar is None:
        return None
    return necesita_recotizar(
        desglose.total_ars, ultima_total, ultima_dolar, desglose.dolar,
        desvio_tol=p.tolerancia_desvio, dolar_tol=p.variacion_dolar,
    )


def nombre_de_producto(nombre_propio: str | None, modelo: str | None, cuero: str | None, color: str | None) -> str:
    # SUPUESTO: validar. The sheet calculates the product name; until its rule is confirmed: own name,
    # else model + leather + color.
    return nombre_propio or " - ".join(parte for parte in (modelo, cuero, color) if parte)


# --- Loading --------------------------------------------------------------------------------------

def cargar_contexto(session: Session) -> Contexto:
    materiales = session.execute(
        select(Material.codigo, Etapa.codigo, Material.desperdicio_manual).join(Etapa, Etapa.id == Material.etapa_id)
    ).all()
    filas = session.execute(
        select(Material.codigo, Color.nombre, PrecioMaterial.precio, PrecioMaterial.moneda, PrecioMaterial.vigente_desde)
        .join(Material, Material.id == PrecioMaterial.material_id)
        .outerjoin(Color, Color.id == PrecioMaterial.color_id)
    ).all()
    # Newest first, and on the same date the newest row wins (dolar_a_la_fecha keeps the first of a tie).
    dolares = [tuple(f) for f in session.execute(
        select(TipoCambio.fecha, TipoCambio.ars_por_usd).order_by(TipoCambio.fecha.desc(), TipoCambio.id.desc())
    ).all()]
    valores = dict(session.execute(select(Parametro.codigo, Parametro.valor)).all())
    iva = session.execute(
        select(Impuesto.alicuota, Impuesto.es_costo_del_producto).where(Impuesto.codigo == "IVA")
    ).one_or_none()
    parametros = Parametros(
        # SUPUESTO: validar. A missing parameter counts as 0 % (the seeded values of both are 0).
        desperdicio_default=valores.get("FACTOR_DESPERDICIO_DEFAULT") or ZERO,
        arreglos_pct=valores.get("ARREGLOS_PCT") or ZERO,
        tolerancia_desvio=valores.get("TOLERANCIA_DESVIO_PCT"),
        variacion_dolar=valores.get("VARIACION_DOLAR_RECOTIZAR_PCT"),
        iva_pct=(iva[0] or ZERO) if iva else ZERO,
        iva_es_costo=bool(iva[1]) if iva else False,
    )
    return Contexto(
        precios=Precios([PrecioVigente(*fila) for fila in filas]),
        etapa_de_material={codigo: etapa for codigo, etapa, _ in materiales},
        # SUPUESTO: validar. `desperdicio_manual` is a fraction (0.2 = 20 %), like every other percentage.
        desperdicio_manual={codigo: d for codigo, _, d in materiales if d is not None},
        dolares=dolares,
        parametros=parametros,
    )


def _patron(palabra: str) -> str:
    """LIKE pattern that finds `palabra` anywhere, with the wildcards of the visitor's text escaped."""
    escapada = palabra.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escapada}%"


def _filtrar_productos(consulta, cuero, q: str | None, categoria: str | None):
    """Search: every word of `q` must appear in the code or in a part of the computed name."""
    for palabra in (q or "").split():
        patron = _patron(palabra)
        consulta = consulta.where(or_(
            *(columna.ilike(patron, escape="\\") for columna in (
                Producto.codigo, Producto.nombre_propio, Modelo.codigo, Modelo.nombre_del_modelo,
                cuero.nombre_corto, Color.nombre,
            ))
        ))
    if categoria:
        consulta = consulta.where(Categoria.nombre == categoria)
    return consulta


def cargar_productos(
    session: Session, codigos: list[str] | None = None, limit: int | None = None, offset: int = 0,
    q: str | None = None, categoria: str | None = None,
) -> list[DatosProducto]:
    cuero, forro = aliased(Material), aliased(Material)
    consulta = (
        select(Producto, Modelo, Categoria.nombre, cuero.codigo, cuero.nombre_corto, forro.codigo, Color.nombre)
        .outerjoin(Modelo, Modelo.id == Producto.modelo_id)
        .outerjoin(Categoria, Categoria.id == Modelo.categoria_id)
        .outerjoin(cuero, cuero.id == Producto.cuero_id)
        .outerjoin(forro, forro.id == Modelo.forro_id)
        .outerjoin(Color, Color.id == Producto.color_id)
        .order_by(Producto.id)
    )
    if codigos is not None:
        consulta = consulta.where(Producto.codigo.in_(codigos))
    consulta = _filtrar_productos(consulta, cuero, q, categoria)
    if limit is not None:
        consulta = consulta.limit(limit).offset(offset)
    filas = session.execute(consulta).all()
    ids = [fila[0].id for fila in filas]
    extras: dict[int, list[Extra]] = {}
    lotes: dict[int, list[ItemLote]] = {}
    componentes: dict[int, list[tuple[str, Decimal]]] = {}
    if ids:
        for producto_id, material, etapa, color, consumo in session.execute(
            select(RecetaLinea.producto_id, Material.codigo, Etapa.codigo, Color.nombre, RecetaLinea.consumo_neto_por_unidad)
            .join(Material, Material.id == RecetaLinea.material_id)
            .join(Etapa, Etapa.id == Material.etapa_id)
            .outerjoin(Color, Color.id == RecetaLinea.color_id)
            .where(RecetaLinea.producto_id.in_(ids)).order_by(RecetaLinea.id)
        ):
            extras.setdefault(producto_id, []).append(Extra(material, etapa, color, consumo))
        # A lot counts on its delivery date, else on its shipping date; one without either has no date.
        dia = func.coalesce(OrdenFabricacion.fecha_de_entrega, OrdenFabricacion.fecha_de_envio)
        for producto_id, fecha, cotizado, pagado in session.execute(
            select(OrdenItem.producto_id, dia, OrdenItem.taller_precio_cotizado_por_unidad_ars,
                   OrdenItem.taller_precio_pagado_por_unidad_ars)
            .join(OrdenFabricacion, OrdenFabricacion.id == OrdenItem.orden_fabricacion_id)
            .where(OrdenItem.producto_id.in_(ids), dia.is_not(None))
        ):
            lotes.setdefault(producto_id, []).append(ItemLote(fecha, cotizado, pagado))
        componente = aliased(Producto)
        for kit_id, codigo, cantidad in session.execute(
            select(KitComponente.kit_id, componente.codigo, KitComponente.cantidad)
            .join(componente, componente.id == KitComponente.componente_id)
            .where(KitComponente.kit_id.in_(ids)).order_by(KitComponente.id)
        ):
            componentes.setdefault(kit_id, []).append((codigo, cantidad))
    resultado = []
    for producto, modelo, categoria, cuero_codigo, cuero_corto, forro_codigo, color in filas:
        receta_modelo = ModeloReceta(
            modelo.cuero_m2_por_unidad, forro_codigo, modelo.forro_m2_por_unidad, modelo.flex_m2_por_unidad,
            modelo.goma_eva_m2_por_unidad, modelo.herrajes_usd_por_unidad, modelo.hilo_y_cemento,
            modelo.confeccion_estimada_ars,
        ) if modelo else ModeloReceta(None, None, None, None, None, None, None, None)
        resultado.append(DatosProducto(
            id=producto.id, codigo=producto.codigo,
            nombre=nombre_de_producto(producto.nombre_propio, modelo.nombre_del_modelo if modelo else None, cuero_corto, color),
            categoria=categoria, modelo_codigo=modelo.codigo if modelo else None, cuero=cuero_codigo, color=color,
            quien=producto.quien_lo_confecciona, estado_del_ciclo=producto.estado_del_ciclo, es_kit=producto.es_kit,
            nota=producto.nota, fecha_de_alta=producto.fecha_de_alta,
            fecha_de_recotizacion=producto.fecha_de_recotizacion, fecha_de_cierre=producto.fecha_de_cierre,
            modelo=receta_modelo, extras=extras.get(producto.id, []), lotes=lotes.get(producto.id, []),
            componentes=componentes.get(producto.id, []), tamano=modelo.tamano if modelo else None,
        ))
    return resultado


def expandir_kits(session: Session, base: list[DatosProducto]) -> dict[str, DatosProducto]:
    """Catalog with `base` plus every kit component, recursively (cycles end: only unloaded codes are fetched)."""
    catalogo = {d.codigo: d for d in base}
    pendientes = {c for d in base for c, _ in d.componentes} - catalogo.keys()
    while pendientes:
        nuevos = cargar_productos(session, sorted(pendientes))
        catalogo.update({d.codigo: d for d in nuevos})
        pendientes = {c for d in nuevos for c, _ in d.componentes} - catalogo.keys()
    return catalogo


def _cargar_uno(session: Session, codigo: str) -> tuple[DatosProducto, dict[str, DatosProducto]]:
    base = cargar_productos(session, [codigo])
    if not base:
        raise NoEncontrado(f"No existe el producto {codigo}.")
    return base[0], expandir_kits(session, base)


def _hoy(ctx: Contexto) -> date | None:
    """The date of "costo hoy": the newest dollar on record (the engine never reads the clock)."""
    return max((f for f, _ in ctx.dolares), default=None)


def _costo_hoy(datos: DatosProducto, ctx: Contexto, catalogo: dict[str, DatosProducto]) -> ResultadoCotizacion | None:
    fecha = _hoy(ctx)
    return cotizar_datos(datos, ctx, fecha, catalogo) if fecha else None


# --- Quotes -----------------------------------------------------------------------------------------

def cotizar(session: Session, codigo_producto: str, fecha: date) -> ResultadoCotizacion:
    datos, catalogo = _cargar_uno(session, codigo_producto)
    return cotizar_datos(datos, cargar_contexto(session), fecha, catalogo)


def _insertar(session: Session, fila, conflicto: str) -> None:
    try:
        with session.begin_nested():
            session.add(fila)
            session.flush()
    except IntegrityError as error:
        if getattr(error.orig, "sqlstate", None) == UNIQUE_VIOLATION:
            raise Conflicto(conflicto) from None
        raise DatosInvalidos("Los datos no cumplen las reglas de la base.") from None


def _cotizacion_a_dict(c: Cotizacion, codigo: str) -> dict:
    campos = ("tipo", "fecha", "dolar", *STAGE_COLUMNS.values(), "subtotal_etapas", "componentes_kit",
              "iva_compras", "arreglos", "total_ars", "total_usd", "estado")
    return {"producto": codigo, **{campo: getattr(c, campo) for campo in campos}}


def guardar_cotizacion(session: Session, codigo_producto: str, tipo: str, fecha: date | None = None) -> dict:
    """Append one immutable snapshot. Never updates: a repeated (product, date, type) is a conflict."""
    datos, catalogo = _cargar_uno(session, codigo_producto)
    dia = fecha_de_cotizacion(datos, tipo, fecha)
    ya_existe = session.scalar(select(Cotizacion.id).where(
        Cotizacion.producto_id == datos.id, Cotizacion.fecha == dia, Cotizacion.tipo == tipo))
    if ya_existe:
        raise Conflicto(f"Ya existe una cotización {tipo} de {codigo_producto} para el {dia.isoformat()}.")
    resultado = cotizar_datos(datos, cargar_contexto(session), dia, catalogo)
    cotizado = resultado.cotizado
    if cotizado.desglose is None or not cotizado.completa:
        raise CotizacionIncompleta(cotizado.avisos)
    if cotizado.desglose.subtotal + cotizado.desglose.componentes_kit <= 0:
        raise CotizacionIncompleta([*cotizado.avisos, "Faltan datos de consumo"])
    fila = Cotizacion(producto_id=datos.id, tipo=tipo, fecha=dia, estado="COMPLETA",
                      **columnas_cotizacion(cotizado.desglose))
    _insertar(session, fila, f"Ya existe una cotización {tipo} de {codigo_producto} para el {dia.isoformat()}.")
    session.commit()
    session.refresh(fila)  # return what the database stored (NUMERIC(14,4)), not the unrounded engine value
    return _cotizacion_a_dict(fila, codigo_producto)


# --- Reads ----------------------------------------------------------------------------------------------

def _desglose_a_dict(r: ResultadoCotizacion | None) -> dict | None:
    if r is None or r.cotizado.desglose is None or not r.cotizado.completa:
        return None
    d = r.cotizado.desglose
    return {"fecha": r.fecha, "dolar": d.dolar, "etapas": dict(d.etapas), "subtotal": d.subtotal,
            "componentes_kit": d.componentes_kit, "iva_compras": d.iva_compras, "arreglos": d.arreglos,
            "total_ars": d.total_ars, "total_usd": d.total_usd}


def _costo_hoy_seguro(datos, ctx, catalogo) -> tuple[ResultadoCotizacion | None, list[str]]:
    try:
        resultado = _costo_hoy(datos, ctx, catalogo)
    except DatosInvalidos as error:
        return None, [str(error)]
    if resultado is None:
        return None, ["Falta el dólar"]
    return resultado, list(resultado.cotizado.avisos)


def contar_productos(session: Session, q: str | None = None, categoria: str | None = None) -> int:
    cuero = aliased(Material)
    consulta = (
        select(func.count(Producto.id)).select_from(Producto)
        .outerjoin(Modelo, Modelo.id == Producto.modelo_id)
        .outerjoin(Categoria, Categoria.id == Modelo.categoria_id)
        .outerjoin(cuero, cuero.id == Producto.cuero_id)
        .outerjoin(Color, Color.id == Producto.color_id)
    )
    return session.scalar(_filtrar_productos(consulta, cuero, q, categoria)) or 0


def listar_productos(
    session: Session, limit: int = 100, offset: int = 0, q: str | None = None, categoria: str | None = None,
) -> list[dict]:
    base = cargar_productos(session, limit=limit, offset=offset, q=q, categoria=categoria)
    catalogo = expandir_kits(session, base)
    ctx = cargar_contexto(session)
    filas = []
    for datos in base:
        resultado, avisos = _costo_hoy_seguro(datos, ctx, catalogo)
        costo = _desglose_a_dict(resultado)
        filas.append({
            "codigo": datos.codigo, "nombre": datos.nombre, "categoria": datos.categoria,
            "estado_del_ciclo": datos.estado_del_ciclo, "es_kit": datos.es_kit,
            "costo_hoy_ars": costo["total_ars"] if costo else None,
            "costo_hoy_usd": costo["total_usd"] if costo else None,
            "avisos": avisos,
        })
    return filas


def ficha_producto(session: Session, codigo: str) -> dict:
    datos, catalogo = _cargar_uno(session, codigo)
    ctx = cargar_contexto(session)
    resultado, avisos = _costo_hoy_seguro(datos, ctx, catalogo)
    receta = generar_receta(datos.modelo, datos.producto, datos.extras)
    guardadas = session.scalars(
        select(Cotizacion).where(Cotizacion.producto_id == datos.id).order_by(Cotizacion.fecha.desc(), Cotizacion.id.desc())
    ).all()
    costo = _desglose_a_dict(resultado)
    ultima = guardadas[0] if guardadas else None
    recotizar = marca_recotizar(
        resultado.cotizado.desglose if costo and resultado else None,
        ultima.total_ars if ultima else None, ultima.dolar if ultima else None, ctx.parametros,
    )
    return {
        "codigo": datos.codigo, "nombre": datos.nombre, "categoria": datos.categoria, "modelo": datos.modelo_codigo,
        "cuero": datos.cuero, "color": datos.color, "quien_lo_confecciona": datos.quien,
        "estado_del_ciclo": datos.estado_del_ciclo, "es_kit": datos.es_kit, "nota": datos.nota,
        "fecha_de_alta": datos.fecha_de_alta, "fecha_de_recotizacion": datos.fecha_de_recotizacion,
        "fecha_de_cierre": datos.fecha_de_cierre,
        "receta": [{"etapa": l.etapa, "material": l.material, "color": l.color, "consumo": l.consumo}
                   for l in receta.lineas],
        "componentes": [{"producto": c, "cantidad": q} for c, q in datos.componentes],
        "confeccion_estimada_ars": receta.confeccion_estimada,
        "costo_hoy": costo, "avisos": avisos, "recotizar": recotizar,
        "cotizaciones": [_cotizacion_a_dict(c, datos.codigo) for c in guardadas],
    }


def _modelo_a_dict(m: Modelo, categoria: str | None, forro_codigo: str | None) -> dict:
    return {
        "codigo": m.codigo, "nombre_del_modelo": m.nombre_del_modelo, "categoria": categoria, "tamano": m.tamano,
        "cuero_m2_por_unidad": m.cuero_m2_por_unidad, "forro": forro_codigo,
        "forro_m2_por_unidad": m.forro_m2_por_unidad, "flex_m2_por_unidad": m.flex_m2_por_unidad,
        "goma_eva_m2_por_unidad": m.goma_eva_m2_por_unidad, "herrajes_usd_por_unidad": m.herrajes_usd_por_unidad,
        "hilo_y_cemento": m.hilo_y_cemento, "confeccion_estimada_ars": m.confeccion_estimada_ars,
        "origen_de_los_consumos": m.origen_de_los_consumos, "validado": m.validado,
    }


def listar_modelos(
    session: Session, limit: int = 500, offset: int = 0, q: str | None = None, categoria: str | None = None,
    validado: bool | None = None, tamano: str | None = None,
) -> list[dict]:
    """Models in sheet order. Filters: every word of `q` in the code or name, exact category name, flag, size."""
    forro = aliased(Material)
    consulta = (
        select(Modelo, Categoria.nombre, forro.codigo)
        .outerjoin(Categoria, Categoria.id == Modelo.categoria_id)
        .outerjoin(forro, forro.id == Modelo.forro_id)
        .order_by(Modelo.id).limit(limit).offset(offset)
    )
    for palabra in (q or "").split():
        patron = _patron(palabra)
        consulta = consulta.where(or_(Modelo.codigo.ilike(patron, escape="\\"), Modelo.nombre_del_modelo.ilike(patron, escape="\\")))
    if categoria:
        consulta = consulta.where(Categoria.nombre == categoria)
    if validado is not None:
        consulta = consulta.where(Modelo.validado.is_(validado))
    if tamano:
        consulta = consulta.where(Modelo.tamano == tamano)
    return [_modelo_a_dict(m, nombre_categoria, forro_codigo) for m, nombre_categoria, forro_codigo in session.execute(consulta).all()]


def listar_materiales(session: Session) -> list[dict]:
    filas = session.execute(
        select(Material, Etapa.codigo).join(Etapa, Etapa.id == Material.etapa_id).order_by(Material.id)).all()
    return [{
        "codigo": m.codigo, "nombre": m.nombre, "nombre_corto": m.nombre_corto, "etapa": etapa,
        "unidad_de_consumo": m.unidad_de_consumo, "cotizable": m.cotizable,
        "controla_inventario": m.controla_inventario, "desperdicio_manual": m.desperdicio_manual,
    } for m, etapa in filas]


def variacion_de_precio(anterior: Decimal | None, nuevo: Decimal) -> tuple[Decimal | None, bool]:
    """Percent change against the previous price and whether it is a big jump; (None, False) if not comparable."""
    if anterior is None or anterior <= 0:
        return None, False
    cambio = (nuevo - anterior) / anterior * 100
    return cambio.quantize(Decimal("0.01"), ROUND_HALF_UP), abs(cambio) > SALTO_PRECIO_PCT


def listar_precios(session: Session, material: str | None = None, a_fecha: date | None = None) -> list[dict]:
    """Price history, newest first; `vigente` marks the row in force at `a_fecha` per material and color.

    `variacion_pct` / `salto_grande` compare each price with the previous one of the same material, color
    and currency (the first price of a series has nothing to compare with).
    """
    a_fecha = a_fecha or date.today()
    consulta = (
        select(PrecioMaterial, Material.codigo, Color.nombre)
        .join(Material, Material.id == PrecioMaterial.material_id)
        .outerjoin(Color, Color.id == PrecioMaterial.color_id)
        .order_by(PrecioMaterial.vigente_desde.desc(), PrecioMaterial.id.desc())
    )
    if material:
        consulta = consulta.where(Material.codigo == material)
    filas = session.execute(consulta).all()
    vigentes: dict[tuple, int] = {}
    for p, codigo, color in filas:  # newest first: the first one not after `a_fecha` is the one in force
        if p.vigente_desde <= a_fecha:
            vigentes.setdefault((p.material_id, p.color_id), p.id)
    saltos: dict[int, tuple[Decimal | None, bool]] = {}
    previo: dict[tuple, Decimal] = {}
    for p, _, _ in reversed(filas):  # oldest first, so `previo` is the price just before this one
        clave = (p.material_id, p.color_id, p.moneda)
        saltos[p.id] = variacion_de_precio(previo.get(clave), p.precio)
        previo[clave] = p.precio
    return [{
        "codigo": p.codigo, "material": codigo, "color": color, "proveedor": p.proveedor, "precio": p.precio,
        "moneda": p.moneda, "unidad_del_precio": p.unidad_del_precio, "iva_incluido": p.iva_incluido,
        "vigente_desde": p.vigente_desde, "nota_fuente": p.nota_fuente,
        "vigente": vigentes.get((p.material_id, p.color_id)) == p.id,
        "variacion_pct": saltos[p.id][0], "salto_grande": saltos[p.id][1],
    } for p, codigo, color in filas]


def chequear_precio(
    session: Session, material: str, color: str | None, precio: Decimal, moneda: str, vigente_desde: date,
) -> dict:
    """Compare a price that is about to be loaded with the latest earlier one; stores nothing."""
    material_fila = session.scalar(select(Material).where(Material.codigo == material))
    if material_fila is None:
        raise DatosInvalidos(f"No existe el material {material}.")
    color_id = _color_id(session, color)
    consulta = select(PrecioMaterial.precio).where(
        PrecioMaterial.material_id == material_fila.id, PrecioMaterial.moneda == moneda,
        PrecioMaterial.vigente_desde <= vigente_desde,
        PrecioMaterial.color_id.is_(None) if color_id is None else PrecioMaterial.color_id == color_id,
    ).order_by(PrecioMaterial.vigente_desde.desc(), PrecioMaterial.id.desc()).limit(1)
    anterior = session.scalar(consulta)
    variacion, salto = variacion_de_precio(anterior, precio)
    return {"anterior": anterior, "variacion_pct": variacion, "salto_grande": salto}


def listar_catalogos(session: Session) -> dict:
    return {
        "colores": list(session.scalars(select(Color.nombre).order_by(Color.nombre))),
        "categorias": list(session.scalars(select(Categoria.nombre).order_by(Categoria.nombre))),
    }


def listar_dolar(session: Session) -> list[dict]:
    return [
        {"fecha": t.fecha, "ars_por_usd": t.ars_por_usd, "fuente": t.fuente, "tipo": t.tipo, "nota": t.nota}
        for t in session.scalars(select(TipoCambio).order_by(TipoCambio.fecha.desc(), TipoCambio.id.desc()))
    ]


def _parametro_a_dict(p: Parametro) -> dict:
    return {
        "codigo": p.codigo, "constante": p.constante, "valor": p.valor, "valor_texto": p.valor_texto,
        "unidad": p.unidad, "que_es": p.que_es, "fuente_estado": p.fuente_estado,
    }


def listar_parametros(session: Session) -> list[dict]:
    return [_parametro_a_dict(p) for p in session.scalars(select(Parametro).order_by(Parametro.id))]


def _persona_a_dict(p: Persona) -> dict:
    return {"codigo": p.codigo, "nombre": p.nombre, "rol": p.rol, "activo": p.activo}


def listar_personas(session: Session) -> list[dict]:
    return [_persona_a_dict(p) for p in session.scalars(select(Persona).order_by(Persona.id))]


def costos_fijos(session: Session, periodo: str | None = None) -> dict:
    """Fixed costs of a month with factory/store totals; pending amounts (NULL) are counted, not summed."""
    if periodo is None:
        periodo = session.scalar(select(Parametro.valor_texto).where(Parametro.codigo == "PERIODO_VIGENTE"))
    if periodo is None:
        raise DatosInvalidos("Falta el período: indicá ?periodo=AAAA-MM.")
    filas = session.execute(
        select(GastoPeriodo, Persona.codigo).outerjoin(Persona, Persona.id == GastoPeriodo.persona_id)
        .where(GastoPeriodo.periodo == periodo).order_by(GastoPeriodo.id)
    ).all()
    totales = {"FABRICA": ZERO, "TIENDA": ZERO}
    for g, _ in filas:
        totales[g.fabrica_o_tienda] += g.monto_ars_del_mes or ZERO
    return {
        "periodo": periodo, "total_fabrica": totales["FABRICA"], "total_tienda": totales["TIENDA"],
        "total": totales["FABRICA"] + totales["TIENDA"],  # Costos_Fijos!L3: the screen must not add money itself
        "pendientes": sum(1 for g, _ in filas if g.monto_ars_del_mes is None),
        "incluye_ficticios": any(g.ficticio for g, _ in filas),
        "gastos": [{
            "codigo": g.codigo, "concepto": g.concepto, "fabrica_o_tienda": g.fabrica_o_tienda,
            "categoria": g.categoria, "persona": persona, "monto_ars_del_mes": g.monto_ars_del_mes,
            "ficticio": g.ficticio, "nota_fuente": g.nota_fuente,
        } for g, persona in filas],
    }


# --- Writes (append-only: nothing here updates or deletes) -----------------------------------------------

def _siguiente_numero(session: Session, columna, prefijo: str) -> int:
    ultimo = session.scalar(
        select(func.max(cast(func.substr(columna, len(prefijo) + 2), Integer))).where(columna.op("~")(f"^{prefijo}-[0-9]+$"))
    )
    return (ultimo or 0) + 1


def _por_codigo(session: Session, modelo, codigo: str | None, que: str):
    if codigo is None:
        return None
    fila = session.scalar(select(modelo).where(modelo.codigo == codigo))
    if fila is None:
        raise DatosInvalidos(f"No existe {que} {codigo}.")
    return fila


def _color_id(session: Session, nombre: str | None) -> int | None:
    if nombre is None:
        return None
    color = session.scalar(select(Color).where(Color.nombre == nombre))
    if color is None:
        raise DatosInvalidos(f"No existe el color {nombre}.")
    return color.id


def _material_de_receta(session: Session, codigo: str, etapa: str | None = None) -> Material:
    fila = session.execute(select(Material, Etapa).join(Etapa, Etapa.id == Material.etapa_id).where(Material.codigo == codigo)).one_or_none()
    if fila is None:
        raise DatosInvalidos(f"No existe el material {codigo}.")
    material, etapa_fila = fila
    if not material.cotizable:
        raise DatosInvalidos(f"El material {codigo} no es cotizable.")
    if etapa_fila.tipo != "MATERIAL" or (etapa and etapa_fila.codigo != etapa):
        raise DatosInvalidos(f"El material {codigo} no corresponde a esta línea de la receta.")
    return material


def crear_producto(
    session: Session, *, modelo: str | None, cuero: str | None, color: str | None,
    quien_lo_confecciona: str | None, fecha_de_alta: date | None, nombre_propio: str | None,
    es_kit: bool, nota: str | None = None,
) -> dict:
    if modelo is None and not es_kit:
        raise DatosInvalidos("Falta el modelo (solo un kit puede ir sin modelo).")
    modelo_fila = _por_codigo(session, Modelo, modelo, "el modelo")
    cuero_fila = _material_de_receta(session, cuero, "CUERO") if cuero else None
    codigo = f"PRD-{_siguiente_numero(session, Producto.codigo, 'PRD'):04d}"
    fila = Producto(
        codigo=codigo, modelo_id=modelo_fila.id if modelo_fila else None, cuero_id=cuero_fila.id if cuero_fila else None,
        color_id=_color_id(session, color), quien_lo_confecciona=quien_lo_confecciona,
        fecha_de_alta=fecha_de_alta, nombre_propio=nombre_propio, es_kit=es_kit, nota=nota,
    )
    _insertar(session, fila, "No se pudo asignar el código del producto; intentá de nuevo.")
    session.commit()
    return ficha_producto(session, codigo)


def agregar_extra(
    session: Session, codigo_producto: str, *, material: str, color: str | None, consumo_neto_por_unidad: Decimal, nota: str | None = None,
) -> dict:
    producto = session.scalar(select(Producto).where(Producto.codigo == codigo_producto))
    if producto is None:
        raise NoEncontrado(f"No existe el producto {codigo_producto}.")
    material_fila = _material_de_receta(session, material)
    # SUPUESTO: validar. The `REX-nnnn` prefix of an extra line's codigo is ours; the sheet does not define it.
    fila = RecetaLinea(
        codigo=f"REX-{_siguiente_numero(session, RecetaLinea.codigo, 'REX'):04d}", origen="EXTRA",
        producto_id=producto.id, material_id=material_fila.id, color_id=_color_id(session, color),
        consumo_neto_por_unidad=consumo_neto_por_unidad, nota=nota,
    )
    _insertar(session, fila, "No se pudo asignar el código de la línea; intentá de nuevo.")
    session.commit()
    return ficha_producto(session, codigo_producto)


def _alcanza(catalogo: dict[str, DatosProducto], desde: str, objetivo: str) -> bool:
    visto, pila = set(), [desde]
    while pila:
        actual = pila.pop()
        if actual == objetivo:
            return True
        if actual not in visto and actual in catalogo:
            visto.add(actual)
            pila.extend(c for c, _ in catalogo[actual].componentes)
    return False


def agregar_componente(session: Session, codigo_kit: str, *, componente: str, cantidad: Decimal) -> dict:
    kit, _ = _cargar_uno(session, codigo_kit)
    if not kit.es_kit:
        raise DatosInvalidos(f"El producto {codigo_kit} no es un kit.")
    base = cargar_productos(session, [componente])
    if not base:
        raise DatosInvalidos(f"No existe el producto {componente}.")
    if _alcanza(expandir_kits(session, base), componente, codigo_kit):
        raise DatosInvalidos(f"Hay un ciclo de kits: {componente} ya contiene a {codigo_kit}.")
    if any(c == componente for c, _ in kit.componentes):
        raise Conflicto(f"{componente} ya es componente de {codigo_kit}.")
    fila = KitComponente(kit_id=kit.id, componente_id=base[0].id, cantidad=cantidad)
    _insertar(session, fila, f"{componente} ya es componente de {codigo_kit}.")
    session.commit()
    return ficha_producto(session, codigo_kit)


def crear_precio(
    session: Session, *, material: str, color: str | None, proveedor: str | None, precio: Decimal, moneda: str,
    unidad_del_precio: str, iva_incluido: bool, vigente_desde: date, nota_fuente: str | None = None,
) -> dict:
    """A new price is a new row with its date; an existing (material, color, date) is a conflict."""
    material_fila = session.scalar(select(Material).where(Material.codigo == material))
    if material_fila is None:
        raise DatosInvalidos(f"No existe el material {material}.")
    if unidad_del_precio != material_fila.unidad_de_consumo:
        # Rule kept from the old DER: a price is only usable when its unit equals the consumption unit.
        raise DatosInvalidos(
            f"La unidad del precio ({unidad_del_precio}) no coincide con la de consumo ({material_fila.unidad_de_consumo}).")
    fila = PrecioMaterial(
        codigo=f"PRE-{_siguiente_numero(session, PrecioMaterial.codigo, 'PRE'):04d}", material_id=material_fila.id,
        color_id=_color_id(session, color), proveedor=proveedor, precio=precio, moneda=moneda,
        unidad_del_precio=unidad_del_precio, iva_incluido=iva_incluido, vigente_desde=vigente_desde,
        nota_fuente=nota_fuente,
    )
    _insertar(session, fila, "Ya hay un precio de ese material y color para esa fecha; cargá uno con otra fecha.")
    session.commit()
    return next(p for p in listar_precios(session, material, vigente_desde) if p["codigo"] == fila.codigo)


def crear_dolar(
    session: Session, *, fecha: date, ars_por_usd: Decimal, fuente: str, tipo: str | None, nota: str | None = None,
) -> dict:
    fila = TipoCambio(fecha=fecha, ars_por_usd=ars_por_usd, fuente=fuente, tipo=tipo, nota=nota)
    _insertar(session, fila, "Ya hay un dólar con esa fecha, tipo y fuente; cargá uno con otra fecha.")
    session.commit()
    return {"fecha": fila.fecha, "ars_por_usd": fila.ars_por_usd, "fuente": fila.fuente, "tipo": fila.tipo, "nota": fila.nota}


def crear_gasto(
    session: Session, *, periodo: str, concepto: str, fabrica_o_tienda: str, categoria: str, persona: str | None,
    monto_ars_del_mes: Decimal | None, ficticio: bool, nota_fuente: str | None = None,
) -> dict:
    persona_fila = _por_codigo(session, Persona, persona, "la persona")
    fila = GastoPeriodo(
        codigo=f"GF-{_siguiente_numero(session, GastoPeriodo.codigo, 'GF'):04d}", periodo=periodo, concepto=concepto,
        fabrica_o_tienda=fabrica_o_tienda, categoria=categoria, persona_id=persona_fila.id if persona_fila else None,
        monto_ars_del_mes=monto_ars_del_mes, ficticio=ficticio, nota_fuente=nota_fuente,
    )
    _insertar(session, fila, "No se pudo asignar el código del gasto; intentá de nuevo.")
    session.commit()
    return costos_fijos(session, periodo)


def crear_orden(
    session: Session, *, donde_se_hace: str, taller: str | None, persona: str | None, fecha_de_envio: date | None,
    fecha_de_entrega: date | None, estado: str, nota: str | None, items: list[dict],
) -> dict:
    """A lot with its items and the first row of its state history (costs are derived on read, never stored)."""
    taller_fila = _por_codigo(session, Taller, taller, "el taller")
    persona_fila = _por_codigo(session, Persona, persona, "la persona")
    productos = {}
    for item in items:
        if item["producto"] not in productos:
            productos[item["producto"]] = session.scalar(select(Producto).where(Producto.codigo == item["producto"]))
            if productos[item["producto"]] is None:
                raise DatosInvalidos(f"No existe el producto {item['producto']}.")
    # SUPUESTO: validar. The `LOT-nnnn` / `LIT-nnnn` codes of lots and their items are ours.
    orden = OrdenFabricacion(
        codigo=f"LOT-{_siguiente_numero(session, OrdenFabricacion.codigo, 'LOT'):04d}", donde_se_hace=donde_se_hace,
        taller_id=taller_fila.id if taller_fila else None, persona_id=persona_fila.id if persona_fila else None,
        fecha_de_envio=fecha_de_envio, fecha_de_entrega=fecha_de_entrega, estado=estado, nota=nota,
    )
    _insertar(session, orden, "No se pudo asignar el código del lote; intentá de nuevo.")
    # SUPUESTO: validar. The first history row is dated on the shipping date, else on the day it was loaded.
    _insertar(session, OrdenEstado(orden_fabricacion_id=orden.id, estado=estado, fecha=fecha_de_envio or date.today()),
              "No se pudo registrar el estado del lote; intentá de nuevo.")
    primero = _siguiente_numero(session, OrdenItem.codigo, "LIT")
    for posicion, item in enumerate(items):
        _insertar(session, OrdenItem(
            codigo=f"LIT-{primero + posicion:04d}", orden_fabricacion_id=orden.id,
            producto_id=productos[item["producto"]].id, cantidad=item["cantidad"],
            taller_precio_cotizado_por_unidad_ars=item["taller_precio_cotizado_por_unidad_ars"],
            taller_precio_pagado_por_unidad_ars=item["taller_precio_pagado_por_unidad_ars"], nota=item["nota"],
        ), "No se pudo asignar el código del renglón; intentá de nuevo.")
    session.commit()
    return {
        "codigo": orden.codigo, "donde_se_hace": orden.donde_se_hace, "taller": taller, "persona": persona,
        "fecha_de_envio": orden.fecha_de_envio, "fecha_de_entrega": orden.fecha_de_entrega, "estado": orden.estado,
        "nota": orden.nota, "items": [{**item, "codigo": f"LIT-{primero + i:04d}"} for i, item in enumerate(items)],
    }


# --- Fabricación: lots, workshops, house vs workshop ---------------------------------------------------------
# Plantilla sheets Lotes, Lote_Productos, Lote_Estados, Talleres, Casa_vs_Taller and Precios_Talleres. A lot's money is
# never stored: it is derived on every read from the item prices and the product cost of today.

AVISO_SIN_TALLER = "Falta el taller"
AVISO_SIN_ENVIO = "Falta la fecha de envío"
AVISO_SIN_PRODUCTOS = "Sin productos: agregá al menos uno"
AVISO_SIN_ENTREGA = "Falta la fecha de entrega (cierra la cotización final)"
AVISO_RENGLONES = "Hay productos con problemas"
AVISO_SIN_CANTIDAD = "Falta la cantidad"
AVISO_SIN_PRECIO_TALLER = "Falta el precio del taller"
AVISO_SIN_FECHA = "El lote no tiene fecha"
# Not in the sheet: its blank cost would silently drop the line from the lot total, so the app says it.
AVISO_SIN_COSTO = "No se puede calcular el costo de hoy del producto"
SEVERIDAD_DE_AVISO_DE_LOTE = {
    AVISO_SIN_TALLER: "alta", AVISO_SIN_ENTREGA: "alta", AVISO_SIN_ENVIO: "media", AVISO_SIN_PRODUCTOS: "media",
    AVISO_SIN_CANTIDAD: "media", AVISO_SIN_PRECIO_TALLER: "media", AVISO_SIN_COSTO: "media",
}
MESES_CASA_VS_TALLER = 12
# SUPUESTO: validar. The sheet lists the last 10 workshop prices of the category; the app lists the latest price per
# (workshop, similar product) instead, up to this many rows.
MAX_PARECIDOS = 20
CENTAVOS = Decimal("0.01")


@dataclass(frozen=True)
class LoteDatos:
    id: int
    codigo: str
    donde: str
    taller: str | None
    taller_nombre: str | None
    persona: str | None
    persona_nombre: str | None
    envio: date | None
    entrega: date | None
    estado: str
    nota: str | None

    @property
    def fecha(self) -> date | None:
        """The date a lot counts on: delivery, else shipping (Lotes!T)."""
        return self.entrega or self.envio


@dataclass(frozen=True)
class ItemDatos:
    id: int
    codigo: str
    lote: str  # codigo of the lot
    producto: str  # codigo of the product
    cantidad: Decimal
    cotizado: Decimal | None
    pagado: Decimal | None
    nota: str | None


@dataclass(frozen=True)
class InfoProducto:
    nombre: str
    categoria: str | None
    tamano: str | None
    materiales: Decimal | None  # materials per unit at today's prices; None when the cost cannot be computed


@dataclass(frozen=True)
class PrecioDeTaller:
    fecha: date
    orden: int  # tie-break on the same date: the newest item wins
    producto: str
    nombre: str
    categoria: str | None
    tamano: str | None
    taller: str
    taller_nombre: str | None
    cantidad: Decimal
    precio: Decimal
    lote: str


def confeccion_de_renglon(donde: str, fecha: date | None, cotizado: Decimal | None, pagado: Decimal | None) -> Decimal | None:
    """Sewing per unit of a lot line (Lote_Productos!P): in house 0; at a workshop what it charged, else what it quoted."""
    if fecha is None:
        return None
    if donde == "INTERNA":
        return ZERO
    if donde == "EXTERNA":
        if pagado is not None and pagado > 0:
            return pagado
        if cotizado is not None and cotizado > 0:
            return cotizado
    return None


def avisos_de_renglon(
    donde: str, fecha: date | None, cantidad: Decimal, cotizado: Decimal | None, pagado: Decimal | None, costo_ok: bool,
) -> list[str]:
    """Lote_Productos!AA. The sheet shows the first problem; the app lists all of them, in the same order."""
    avisos = []
    if cantidad <= 0:
        avisos.append(AVISO_SIN_CANTIDAD)
    if donde == "EXTERNA" and not (cotizado or 0) > 0 and not (pagado or 0) > 0:
        avisos.append(AVISO_SIN_PRECIO_TALLER)
    if fecha is None:
        avisos.append(AVISO_SIN_FECHA)
    if not costo_ok:
        avisos.append(AVISO_SIN_COSTO)
    return avisos


def avisos_de_lote(
    donde: str, taller: str | None, fecha: date | None, n_items: int, estado: str, entrega: date | None,
    n_renglones_con_problema: int,
) -> list[str]:
    """Lotes!Q, same order as the sheet but listing every problem."""
    avisos = []
    if donde == "EXTERNA" and taller is None:
        avisos.append(AVISO_SIN_TALLER)
    if fecha is None:
        avisos.append(AVISO_SIN_ENVIO)
    if n_items == 0:
        avisos.append(AVISO_SIN_PRODUCTOS)
    if estado == "CERRADA" and entrega is None:
        avisos.append(AVISO_SIN_ENTREGA)
    if n_renglones_con_problema > 0:
        avisos.append(AVISO_RENGLONES)
    return avisos


def es_taller_de_ejemplo(nota: str | None) -> bool:
    # SUPUESTO: validar. The three seeded workshops carry a note that starts with "Ejemplo"; nothing else marks them.
    return (nota or "").strip().lower().startswith("ejemplo")


def mes_de(fecha: date) -> str:
    return f"{fecha.year:04d}-{fecha.month:02d}"


def ultimos_meses(hasta: str, cantidad: int = MESES_CASA_VS_TALLER) -> list[str]:
    """`cantidad` periods AAAA-MM ending at `hasta`, newest first."""
    año, mes = int(hasta[:4]), int(hasta[5:7])
    indices = [año * 12 + (mes - 1) - atras for atras in range(cantidad)]
    return [f"{i // 12:04d}-{i % 12 + 1:02d}" for i in indices]


def resumen_casa_vs_taller(
    lotes: list[LoteDatos], items: list[ItemDatos], talleres: list[tuple[str, str]], meses: list[str],
) -> list[dict]:
    """Casa_vs_Taller: per month, lots and units made in house vs at a workshop, what was paid and units per workshop."""
    filas = {m: {
        "periodo": m, "lotes_casa": 0, "lotes_taller": 0, "unidades_casa": ZERO, "unidades_taller": ZERO,
        "pagado_a_talleres": ZERO, "unidades_por_taller": {codigo: ZERO for codigo, _ in talleres},
    } for m in meses}
    por_lote = {lote.codigo: lote for lote in lotes}
    for lote in lotes:
        fila = filas.get(mes_de(lote.fecha)) if lote.fecha else None
        if fila is not None:
            fila["lotes_taller" if lote.donde == "EXTERNA" else "lotes_casa"] += 1
    for item in items:
        lote = por_lote.get(item.lote)
        fila = filas.get(mes_de(lote.fecha)) if lote and lote.fecha else None
        if fila is None:
            continue
        if lote.donde == "EXTERNA":
            fila["unidades_taller"] += item.cantidad
            fila["pagado_a_talleres"] += item.cantidad * (item.pagado or ZERO)  # only what was paid, not what was quoted
            if lote.taller in fila["unidades_por_taller"]:
                fila["unidades_por_taller"][lote.taller] += item.cantidad
        else:
            fila["unidades_casa"] += item.cantidad
    for fila in filas.values():
        total = fila["unidades_casa"] + fila["unidades_taller"]
        fila["porcentaje_taller"] = (fila["unidades_taller"] / total * 100).quantize(CENTAVOS, ROUND_HALF_UP) if total else None
    return list(filas.values())


def _por_fecha(precio: PrecioDeTaller) -> tuple[date, int]:
    return precio.fecha, precio.orden


def precios_por_taller(precios: list[PrecioDeTaller], producto: str, talleres: list[tuple[str, str]]) -> list[dict]:
    """Precios_Talleres, block 1: per workshop, the latest price of this product, the one before it and the change."""
    filas = []
    for codigo, nombre in talleres:
        hechos = sorted((p for p in precios if p.producto == producto and p.taller == codigo), key=_por_fecha)
        if not hechos:
            filas.append({"taller": codigo, "taller_nombre": nombre, "hizo": False, "precio": None, "fecha": None,
                          "lote": None, "cantidad": None, "veces": 0, "precio_anterior": None, "variacion_pct": None})
            continue
        ultimo = hechos[-1]
        anterior = hechos[-2].precio if len(hechos) > 1 else None
        variacion, _ = variacion_de_precio(anterior, ultimo.precio)
        filas.append({"taller": codigo, "taller_nombre": nombre, "hizo": True, "precio": ultimo.precio,
                      "fecha": ultimo.fecha, "lote": ultimo.lote, "cantidad": ultimo.cantidad, "veces": len(hechos),
                      "precio_anterior": anterior, "variacion_pct": variacion})
    return filas


def precios_parecidos(
    precios: list[PrecioDeTaller], producto: str, categoria: str | None, tamano: str | None, mismo_tamano: bool,
    limite: int = MAX_PARECIDOS,
) -> list[dict]:
    """Precios_Talleres, block 2: same category (and size, if asked); the latest price per (workshop, product)."""
    if categoria is None:
        return []
    ultimo: dict[tuple[str, str], PrecioDeTaller] = {}
    for p in sorted((p for p in precios if p.categoria == categoria and (not mismo_tamano or p.tamano == tamano)), key=_por_fecha):
        ultimo[(p.taller, p.producto)] = p
    return [{
        "fecha": p.fecha, "producto": p.producto, "nombre": p.nombre, "tamano": p.tamano, "taller": p.taller,
        "taller_nombre": p.taller_nombre, "cantidad": p.cantidad, "precio": p.precio, "lote": p.lote,
        "es_mismo_producto": p.producto == producto,
    } for p in sorted(ultimo.values(), key=_por_fecha, reverse=True)[:limite]]


# --- Lots: loading and costing -----------------------------------------------------------------------------

def _dia_del_lote():
    return func.coalesce(OrdenFabricacion.fecha_de_entrega, OrdenFabricacion.fecha_de_envio)


def _cargar_lotes(
    session: Session, codigo: str | None = None, estado: str | None = None, donde: str | None = None,
    taller: str | None = None,
) -> list[LoteDatos]:
    """Newest first (by the date a lot counts on, undated last), then newest code."""
    consulta = (
        select(OrdenFabricacion, Taller.codigo, Taller.nombre, Persona.codigo, Persona.nombre)
        .outerjoin(Taller, Taller.id == OrdenFabricacion.taller_id)
        .outerjoin(Persona, Persona.id == OrdenFabricacion.persona_id)
        .order_by(_dia_del_lote().desc().nulls_last(), OrdenFabricacion.id.desc())
    )
    for columna, valor in ((OrdenFabricacion.codigo, codigo), (OrdenFabricacion.estado, estado),
                           (OrdenFabricacion.donde_se_hace, donde), (Taller.codigo, taller)):
        if valor:
            consulta = consulta.where(columna == valor)
    return [LoteDatos(
        id=o.id, codigo=o.codigo, donde=o.donde_se_hace, taller=t_codigo, taller_nombre=t_nombre, persona=p_codigo,
        persona_nombre=p_nombre, envio=o.fecha_de_envio, entrega=o.fecha_de_entrega, estado=o.estado, nota=o.nota,
    ) for o, t_codigo, t_nombre, p_codigo, p_nombre in session.execute(consulta).all()]


def _cargar_items(session: Session, lote_ids: list[int]) -> list[ItemDatos]:
    if not lote_ids:
        return []
    filas = session.execute(
        select(OrdenItem, OrdenFabricacion.codigo, Producto.codigo)
        .join(OrdenFabricacion, OrdenFabricacion.id == OrdenItem.orden_fabricacion_id)
        .join(Producto, Producto.id == OrdenItem.producto_id)
        .where(OrdenItem.orden_fabricacion_id.in_(lote_ids)).order_by(OrdenItem.id)
    ).all()
    return [ItemDatos(
        id=i.id, codigo=i.codigo, lote=lote, producto=producto, cantidad=i.cantidad,
        cotizado=i.taller_precio_cotizado_por_unidad_ars, pagado=i.taller_precio_pagado_por_unidad_ars, nota=i.nota,
    ) for i, lote, producto in filas]


def _info_productos(session: Session, codigos: set[str], con_costo: bool = True) -> dict[str, InfoProducto]:
    """Name, category, size and (optionally) materials per unit at today's prices: total cost minus its sewing stage."""
    if not codigos:
        return {}
    base = cargar_productos(session, sorted(codigos))
    catalogo = expandir_kits(session, base) if con_costo else {}
    ctx = cargar_contexto(session) if con_costo else None
    info = {}
    for datos in base:
        materiales = None
        if con_costo:
            costo = _desglose_a_dict(_costo_hoy_seguro(datos, ctx, catalogo)[0])
            if costo is not None:
                materiales = costo["total_ars"] - costo["etapas"]["CONFECCION"]
        info[datos.codigo] = InfoProducto(datos.nombre, datos.categoria, datos.tamano, materiales)
    return info


def _armar_lote(lote: LoteDatos, items: list[ItemDatos], info: dict[str, InfoProducto]) -> dict:
    renglones = []
    for item in items:
        producto = info.get(item.producto)
        materiales = producto.materiales if producto else None
        confeccion = confeccion_de_renglon(lote.donde, lote.fecha, item.cotizado, item.pagado)
        costo = None if materiales is None or item.cantidad == 0 else materiales + (confeccion or ZERO)
        renglones.append({
            "codigo": item.codigo, "producto": item.producto, "producto_nombre": producto.nombre if producto else item.producto,
            "categoria": producto.categoria if producto else None, "tamano": producto.tamano if producto else None,
            "cantidad": item.cantidad, "cotizado": item.cotizado, "pagado": item.pagado, "nota": item.nota,
            "confeccion_por_unidad": confeccion, "materiales_por_unidad": materiales, "costo_por_unidad": costo,
            "total_linea": None if costo is None else costo * item.cantidad,
            "avisos": avisos_de_renglon(lote.donde, lote.fecha, item.cantidad, item.cotizado, item.pagado, materiales is not None),
        })
    unidades = sum((r["cantidad"] for r in renglones), ZERO)
    con_costo = [r["total_linea"] for r in renglones if r["total_linea"] is not None]
    costo_total = sum(con_costo, ZERO) if con_costo else None
    return {
        "id": lote.id, "codigo": lote.codigo, "donde_se_hace": lote.donde, "taller": lote.taller,
        "taller_nombre": lote.taller_nombre, "persona": lote.persona, "persona_nombre": lote.persona_nombre,
        "fecha_de_envio": lote.envio, "fecha_de_entrega": lote.entrega, "periodo": mes_de(lote.fecha) if lote.fecha else None,
        "estado": lote.estado, "nota": lote.nota, "productos": len(renglones), "unidades": unidades,
        "total_cotizado": sum((r["cantidad"] * (r["cotizado"] or ZERO) for r in renglones), ZERO),
        "total_cobrado": sum((r["cantidad"] * (r["pagado"] or ZERO) for r in renglones), ZERO),
        "costo_total": costo_total,
        "costo_promedio_por_unidad": costo_total / unidades if costo_total is not None and unidades > 0 else None,
        "avisos": avisos_de_lote(lote.donde, lote.taller, lote.fecha, len(renglones), lote.estado, lote.entrega,
                                 sum(1 for r in renglones if r["avisos"])),
        "items": renglones,
    }


def _armar_lotes(session: Session, **filtros) -> list[dict]:
    lotes = _cargar_lotes(session, **filtros)
    items = _cargar_items(session, [lote.id for lote in lotes])
    info = _info_productos(session, {item.producto for item in items})
    por_lote: dict[str, list[ItemDatos]] = {}
    for item in items:
        por_lote.setdefault(item.lote, []).append(item)
    return [_armar_lote(lote, por_lote.get(lote.codigo, []), info) for lote in lotes]


def listar_ordenes(
    session: Session, estado: str | None = None, donde: str | None = None, taller: str | None = None,
) -> list[dict]:
    return _armar_lotes(session, estado=estado, donde=donde, taller=taller)


def detalle_orden(session: Session, codigo: str) -> dict:
    armados = _armar_lotes(session, codigo=codigo)
    if not armados:
        raise NoEncontrado(f"No existe el lote {codigo}.")
    lote = armados[0]
    lote["estados"] = [{
        "estado": e.estado, "fecha": e.fecha, "quien": p_codigo, "quien_nombre": p_nombre,
    } for e, p_codigo, p_nombre in session.execute(
        select(OrdenEstado, Persona.codigo, Persona.nombre).outerjoin(Persona, Persona.id == OrdenEstado.quien_id)
        .where(OrdenEstado.orden_fabricacion_id == lote["id"]).order_by(OrdenEstado.fecha, OrdenEstado.id)
    ).all()]
    return lote


def _orden_por_codigo(session: Session, codigo: str, bloquear: bool = False) -> OrdenFabricacion:
    consulta = select(OrdenFabricacion).where(OrdenFabricacion.codigo == codigo)
    orden = session.scalar(consulta.with_for_update() if bloquear else consulta)
    if orden is None:
        raise NoEncontrado(f"No existe el lote {codigo}.")
    return orden


def registrar_estado(
    session: Session, codigo: str, *, estado: str, fecha: date, quien: str | None, fecha_de_entrega: date | None,
) -> dict:
    """Append a history row and set the lot's state. A closed lot never changes state again."""
    orden = _orden_por_codigo(session, codigo, bloquear=True)
    if orden.estado == "CERRADA":
        raise Conflicto(f"El lote {codigo} ya está cerrado: no se puede cambiar su estado.")
    if estado == orden.estado:
        # SUPUESTO: validar. Repeating the current state is refused so a double click leaves one history row.
        raise Conflicto(f"El lote {codigo} ya está en estado {estado}.")
    quien_fila = _por_codigo(session, Persona, quien, "la persona")
    if estado == "CERRADA":
        entrega = fecha_de_entrega or orden.fecha_de_entrega
        if entrega is None:
            raise DatosInvalidos("Para cerrar el lote hace falta la fecha de entrega: es la que cierra la cotización final.")
        orden.fecha_de_entrega = entrega
    _insertar(session, OrdenEstado(orden_fabricacion_id=orden.id, estado=estado, fecha=fecha,
                                   quien_id=quien_fila.id if quien_fila else None),
              "No se pudo registrar el estado del lote; intentá de nuevo.")
    orden.estado = estado
    session.commit()
    return detalle_orden(session, codigo)


def agregar_item_a_orden(
    session: Session, codigo: str, *, producto: str, cantidad: Decimal, cotizado: Decimal | None,
    pagado: Decimal | None, nota: str | None = None,
) -> dict:
    orden = _orden_por_codigo(session, codigo)
    producto_fila = session.scalar(select(Producto).where(Producto.codigo == producto))
    if producto_fila is None:
        raise DatosInvalidos(f"No existe el producto {producto}.")
    _insertar(session, OrdenItem(
        codigo=f"LIT-{_siguiente_numero(session, OrdenItem.codigo, 'LIT'):04d}", orden_fabricacion_id=orden.id,
        producto_id=producto_fila.id, cantidad=cantidad, taller_precio_cotizado_por_unidad_ars=cotizado,
        taller_precio_pagado_por_unidad_ars=pagado, nota=nota,
    ), "No se pudo asignar el código del renglón; intentá de nuevo.")
    session.commit()
    return detalle_orden(session, codigo)


def registrar_precios_item(
    session: Session, codigo_lote: str, codigo_item: str, *, cotizado: Decimal | None, pagado: Decimal | None,
) -> dict:
    """Record what the workshop quoted / charged. The one in-place edit of the lots: the price arrives after the
    lot is sent. SUPUESTO: validar. `orden_estado` cannot hold prices and no table may be added, so the previous
    value is not kept anywhere (no audit trail)."""
    _orden_por_codigo(session, codigo_lote)
    item = session.scalar(
        select(OrdenItem).join(OrdenFabricacion, OrdenFabricacion.id == OrdenItem.orden_fabricacion_id)
        .where(OrdenItem.codigo == codigo_item, OrdenFabricacion.codigo == codigo_lote).with_for_update()
    )
    if item is None:
        raise NoEncontrado(f"El lote {codigo_lote} no tiene el renglón {codigo_item}.")
    if cotizado is not None:
        item.taller_precio_cotizado_por_unidad_ars = cotizado
    if pagado is not None:
        item.taller_precio_pagado_por_unidad_ars = pagado
    session.commit()
    return detalle_orden(session, codigo_lote)


def casa_vs_taller(session: Session, hasta: str | None = None) -> dict:
    """The last 12 months up to `hasta` (default: the current month), newest first."""
    meses = ultimos_meses(hasta or mes_de(date.today()))
    talleres = [(t["codigo"], t["nombre"]) for t in listar_talleres(session)]
    lotes = _cargar_lotes(session)
    items = _cargar_items(session, [lote.id for lote in lotes])
    return {
        "talleres": [{"codigo": c, "nombre": n} for c, n in talleres],
        "meses": resumen_casa_vs_taller(lotes, items, talleres, meses),
    }


def _precios_de_taller(session: Session) -> list[PrecioDeTaller]:
    lotes = {lote.codigo: lote for lote in _cargar_lotes(session)}
    items = _cargar_items(session, [lote.id for lote in lotes.values()])
    info = _info_productos(session, {item.producto for item in items}, con_costo=False)
    precios = []
    for item in items:
        lote = lotes[item.lote]
        precio = confeccion_de_renglon(lote.donde, lote.fecha, item.cotizado, item.pagado)
        if lote.donde != "EXTERNA" or lote.taller is None or not precio or precio <= 0:
            continue
        producto = info[item.producto]
        precios.append(PrecioDeTaller(
            fecha=lote.fecha, orden=item.id, producto=item.producto, nombre=producto.nombre, categoria=producto.categoria,
            tamano=producto.tamano, taller=lote.taller, taller_nombre=lote.taller_nombre, cantidad=item.cantidad,
            precio=precio, lote=lote.codigo,
        ))
    return precios


def precios_de_talleres(session: Session, codigo: str, mismo_tamano: bool = True) -> dict:
    """What each workshop charged for this product and for similar ones (same category and, by default, size)."""
    datos, _ = _cargar_uno(session, codigo)
    precios = _precios_de_taller(session)
    talleres = [(t["codigo"], t["nombre"]) for t in listar_talleres(session)]
    por_taller = precios_por_taller(precios, codigo, talleres)
    return {
        "producto": datos.codigo, "nombre": datos.nombre, "categoria": datos.categoria, "tamano": datos.tamano,
        "veces_en_taller": sum(fila["veces"] for fila in por_taller), "por_taller": por_taller,
        "parecidos": precios_parecidos(precios, codigo, datos.categoria, datos.tamano, mismo_tamano),
    }


# --- Workshops ------------------------------------------------------------------------------------------------

def _agregados_de_talleres(session: Session) -> dict[int, tuple]:
    """Per workshop: lots, units, last lot date and what it charged in total (Talleres!J:M)."""
    filas = session.execute(
        select(
            OrdenFabricacion.taller_id, func.count(func.distinct(OrdenFabricacion.id)),
            func.coalesce(func.sum(OrdenItem.cantidad), ZERO),
            func.coalesce(func.sum(OrdenItem.cantidad * func.coalesce(OrdenItem.taller_precio_pagado_por_unidad_ars, ZERO)), ZERO),
            func.max(_dia_del_lote()),
        ).select_from(OrdenFabricacion)
        .outerjoin(OrdenItem, OrdenItem.orden_fabricacion_id == OrdenFabricacion.id)
        .where(OrdenFabricacion.taller_id.is_not(None)).group_by(OrdenFabricacion.taller_id)
    ).all()
    return {taller_id: (lotes, unidades, cobro, ultimo) for taller_id, lotes, unidades, cobro, ultimo in filas}


def _taller_a_dict(t: Taller, agregados: dict[int, tuple]) -> dict:
    lotes, unidades, cobro, ultimo = agregados.get(t.id, (0, ZERO, ZERO, None))
    return {
        "codigo": t.codigo, "nombre": t.nombre, "cuit": t.cuit, "telefono": t.telefono, "direccion": t.direccion,
        "contacto": t.contacto, "activo": t.activo, "nota": t.nota, "ejemplo": es_taller_de_ejemplo(t.nota),
        "lotes": lotes, "unidades": unidades, "ultimo_lote": ultimo, "cobro_total_ars": cobro,
    }


def listar_talleres(session: Session) -> list[dict]:
    agregados = _agregados_de_talleres(session)
    return [_taller_a_dict(t, agregados) for t in session.scalars(select(Taller).order_by(Taller.id))]


def detalle_taller(session: Session, codigo: str) -> dict:
    taller = session.scalar(select(Taller).where(Taller.codigo == codigo))
    if taller is None:
        raise NoEncontrado(f"No existe el taller {codigo}.")
    return {**_taller_a_dict(taller, _agregados_de_talleres(session)), "ordenes": listar_ordenes(session, taller=codigo)}


def _texto_o_nada(valor: str | None) -> str | None:
    limpio = (valor or "").strip()
    return limpio or None


def crear_taller(
    session: Session, *, nombre: str, cuit: str | None, telefono: str | None, direccion: str | None,
    contacto: str | None, nota: str | None,
) -> dict:
    nombre = nombre.strip()
    cuit = _texto_o_nada(cuit)
    if not nombre:
        raise DatosInvalidos("Falta el nombre del taller.")
    if session.scalar(select(Taller.id).where(Taller.nombre == nombre)):
        raise Conflicto(f"Ya hay un taller con el nombre {nombre}.")
    if cuit and session.scalar(select(Taller.id).where(Taller.cuit == cuit)):
        raise Conflicto(f"Ya hay un taller con el CUIT {cuit}.")
    fila = Taller(
        codigo=f"TAL-{_siguiente_numero(session, Taller.codigo, 'TAL'):04d}", nombre=nombre, cuit=cuit,
        telefono=_texto_o_nada(telefono), direccion=_texto_o_nada(direccion), contacto=_texto_o_nada(contacto),
        nota=_texto_o_nada(nota),
    )
    _insertar(session, fila, "Ya hay un taller con ese nombre o ese CUIT, o no se pudo asignar el código; intentá de nuevo.")
    session.commit()
    return detalle_taller(session, fila.codigo)


def cambiar_activo_taller(session: Session, codigo: str, activo: bool) -> dict:
    """Deactivating hides nothing and deletes nothing: the lots of the workshop keep pointing at it."""
    taller = session.scalar(select(Taller).where(Taller.codigo == codigo))
    if taller is None:
        raise NoEncontrado(f"No existe el taller {codigo}.")
    taller.activo = activo
    session.commit()
    return detalle_taller(session, codigo)


# --- Fixed costs: periods and pending amounts -----------------------------------------------------------------

def periodos_de_costos_fijos(session: Session) -> dict:
    cargados = set(session.scalars(select(GastoPeriodo.periodo).distinct()))
    vigente = session.scalar(select(Parametro.valor_texto).where(Parametro.codigo == "PERIODO_VIGENTE"))
    return {"vigente": vigente, "periodos": sorted(cargados | ({vigente} if vigente else set()), reverse=True)}


def cargar_monto_de_gasto(session: Session, codigo: str, monto: Decimal) -> dict:
    """Set the amount of a pending row (monto NULL). Anything already filled in is corrected with a new row."""
    cargado = session.execute(
        update(GastoPeriodo).where(GastoPeriodo.codigo == codigo, GastoPeriodo.monto_ars_del_mes.is_(None))
        .values(monto_ars_del_mes=monto).returning(GastoPeriodo.periodo).execution_options(synchronize_session=False)
    ).first()
    if cargado is None:
        if session.scalar(select(GastoPeriodo.id).where(GastoPeriodo.codigo == codigo)) is None:
            raise NoEncontrado(f"No existe el gasto {codigo}.")
        raise Conflicto(f"El gasto {codigo} ya tiene monto: para corregirlo cargá un gasto nuevo.")
    session.commit()
    return costos_fijos(session, cargado[0])


# --- Admin area (T5c) ---------------------------------------------------------------------------------------------
# Parameters, people, taxes, catalogs and models. Every function here is reached only through admin-gated routes
# (models: admin or cotizador); the role is checked by the router, never here.

# Calculated by the app from other rows, so they are never edited (the plantilla marks them "Calculado").
PARAMETROS_CALCULADOS = frozenset({"DOLAR_VIGENTE", "FECHA_DOLAR_VIGENTE"})
ESTADOS_DE_PARAMETRO = ("Pendiente", "Propuesta", "Confirmado")
# These mirror the CHECK constraints of models.py (a test keeps them in sync).
PERSONA_ROLES = ("CONSUMO_MOLDES", "CORTE", "CONFECCION", "VENTAS", "ENCARGADO", "ADMINISTRACION", "OTRO")
PERSONA_VINCULOS = ("SUELDO_FIJO", "OTRO")
TAMANOS = ("CHICO", "MEDIANO", "GRANDE")
ORIGENES = ("EXCEL", "MOLDE", "ESTIMADO", "MEDIDO")
PERIODO_AAAA_MM = re.compile(r"^[0-9]{4}-(0[1-9]|1[0-2])$")
# Parameter units whose value is a number, and the rule each one gets (see `validar_valor_de_parametro`).
UNIDADES_NUMERICAS = ("%", "ARS/USD", "m2")


def validar_valor_de_parametro(unidad: str | None, valor: Decimal | None, valor_texto: str | None) -> None:
    """Range check by unit. SUPUESTO: validar. The sheet states no ranges: percentages are fractions between 0 and 1
    (0.05 = 5 %, like every other percentage in the app), dollars and areas must be above 0, the period is AAAA-MM."""
    if unidad == "AAAA-MM":
        if valor is not None:
            raise DatosInvalidos("Este parámetro es un texto AAAA-MM: no lleva un valor numérico.")
        if valor_texto is None or not PERIODO_AAAA_MM.match(valor_texto):
            raise DatosInvalidos("El período debe tener el formato AAAA-MM, por ejemplo 2026-11.")
        return
    if unidad == "fecha":
        raise DatosInvalidos("Un parámetro de tipo fecha es calculado: no se puede editar.")
    if unidad not in UNIDADES_NUMERICAS:
        raise DatosInvalidos("Este parámetro no tiene una regla de validación: no se edita desde la aplicación.")
    if valor is not None and valor_texto is not None:
        raise DatosInvalidos("Se carga uno solo: el valor numérico o el texto.")
    if valor_texto is not None:
        raise DatosInvalidos("Este parámetro es numérico: cargá el valor, no un texto.")
    if valor is None:
        raise DatosInvalidos("Falta el valor numérico.")
    if unidad == "%":
        if not ZERO <= valor <= Decimal(1):
            raise DatosInvalidos("Es una fracción entre 0 y 1: un 5 % se escribe 0,05.")
    elif valor <= 0:
        raise DatosInvalidos("Tiene que ser mayor que 0.")


def texto_de_estado(estado: str, nota: str | None) -> str:
    """`fuente_estado` keeps its leading word (Pendiente / Propuesta / Confirmado): the quality report reads it."""
    nota = (nota or "").strip()
    return f"{estado}: {nota}" if nota else estado


def cambiar_parametro(
    session: Session, codigo: str, *, valor: Decimal | None, valor_texto: str | None, estado: str,
    nota: str | None, quien: str,
) -> dict:
    """Overwrite a parameter in place. SUPUESTO: validar. `parametro` has no history column and no table may be added,
    so the previous value is not stored; the change is logged (who, old, new) and `fuente_estado` holds the new state.
    Quotes already saved are snapshots and do not change; the next quote reads the new value."""
    if codigo in PARAMETROS_CALCULADOS:
        raise DatosInvalidos(f"{codigo} es un valor calculado: no se puede editar.")
    fila = session.scalar(select(Parametro).where(Parametro.codigo == codigo).with_for_update())
    if fila is None:
        raise NoEncontrado(f"No existe el parámetro {codigo}.")
    if (fila.fuente_estado or "").strip().lower().startswith("calculado"):
        raise DatosInvalidos(f"{codigo} es un valor calculado: no se puede editar.")
    validar_valor_de_parametro(fila.unidad, valor, valor_texto)
    anterior = fila.valor if fila.valor is not None else fila.valor_texto
    fila.valor = valor
    fila.valor_texto = valor_texto
    fila.fuente_estado = texto_de_estado(estado, nota)
    session.commit()
    session.refresh(fila)  # answer with what the database stored (NUMERIC(14,4)), not the typed value
    logger.info(
        "Parameter %s changed by %s: %s -> %s (%s)", codigo, quien, anterior,
        valor if valor is not None else valor_texto, fila.fuente_estado,
    )
    return _parametro_a_dict(fila)


def _nombre_repetido(session: Session, columna, nombre: str) -> bool:
    """Case-insensitive in Python: the database collation may not fold accents or non-ASCII capitals."""
    buscado = nombre.casefold()
    return any(existente.casefold() == buscado for existente in session.scalars(select(columna)))


def crear_persona(session: Session, *, nombre: str, rol: str, vinculo: str, nota: str | None) -> dict:
    nombre = nombre.strip()
    if not nombre:
        raise DatosInvalidos("Falta el nombre de la persona.")
    if _nombre_repetido(session, Persona.nombre, nombre):
        raise Conflicto(f"Ya hay una persona con el nombre {nombre}.")
    fila = Persona(
        codigo=f"PER-{_siguiente_numero(session, Persona.codigo, 'PER'):04d}", nombre=nombre, rol=rol,
        vinculo=vinculo, activo=True, nota=_texto_o_nada(nota),
    )
    _insertar(session, fila, "No se pudo asignar el código de la persona; intentá de nuevo.")
    session.commit()
    return _persona_a_dict(fila)


def cambiar_activo_persona(session: Session, codigo: str, activo: bool) -> dict:
    """Deactivating deletes nothing: expenses and lots keep pointing at the person."""
    persona = session.scalar(select(Persona).where(Persona.codigo == codigo))
    if persona is None:
        raise NoEncontrado(f"No existe la persona {codigo}.")
    persona.activo = activo
    session.commit()
    return _persona_a_dict(persona)


def listar_impuestos(session: Session) -> list[dict]:
    """Read only: whether VAT is a product cost is an open business decision, so it is not edited from the app."""
    return [{
        "codigo": i.codigo, "nombre": i.nombre, "alicuota": i.alicuota, "base": i.base,
        "es_costo_del_producto": i.es_costo_del_producto, "nota": i.nota,
    } for i in session.scalars(select(Impuesto).order_by(Impuesto.id))]


def _catalogo_a_dict(fila) -> dict:
    return {"codigo": fila.codigo, "nombre": fila.nombre, "nota": fila.nota}


def listar_colores(session: Session) -> list[dict]:
    return [_catalogo_a_dict(c) for c in session.scalars(select(Color).order_by(Color.nombre))]


def listar_categorias(session: Session) -> list[dict]:
    return [_catalogo_a_dict(c) for c in session.scalars(select(Categoria).order_by(Categoria.nombre))]


def crear_color(session: Session, *, nombre: str, nota: str | None) -> dict:
    nombre = nombre.strip()
    if not nombre:
        raise DatosInvalidos("Falta el nombre del color.")
    if _nombre_repetido(session, Color.nombre, nombre):
        raise Conflicto(f"Ya hay un color con el nombre {nombre}.")
    fila = Color(codigo=f"COL-{_siguiente_numero(session, Color.codigo, 'COL'):04d}", nombre=nombre, nota=_texto_o_nada(nota))
    _insertar(session, fila, "Ya hay un color con ese nombre, o no se pudo asignar el código; intentá de nuevo.")
    session.commit()
    return _catalogo_a_dict(fila)


def codigo_de_categoria(nombre: str) -> str | None:
    """`CAT-` plus the first four letters of the name without accents (CAT-PORT, CAT-RINO...), or None if it has fewer.
    SUPUESTO: validar. 15 of the 16 seeded categories follow this; Portadocumentos is CAT-DOCU, so it is a convention
    and not a rule: a taken code falls back to a number."""
    letras = [c for c in unicodedata.normalize("NFKD", nombre) if c.isascii() and c.isalpha()]
    return "CAT-" + "".join(letras[:4]).upper() if len(letras) >= 4 else None


def crear_categoria(session: Session, *, nombre: str, nota: str | None) -> dict:
    nombre = nombre.strip()
    if not nombre:
        raise DatosInvalidos("Falta el nombre de la categoría.")
    if _nombre_repetido(session, Categoria.nombre, nombre):
        raise Conflicto(f"Ya hay una categoría con el nombre {nombre}.")
    codigo = codigo_de_categoria(nombre)
    if codigo is None or session.scalar(select(Categoria.id).where(Categoria.codigo == codigo)):
        codigo = f"CAT-{_siguiente_numero(session, Categoria.codigo, 'CAT'):04d}"
    fila = Categoria(codigo=codigo, nombre=nombre, nota=_texto_o_nada(nota))
    _insertar(session, fila, "Ya hay una categoría con ese nombre, o no se pudo asignar el código; intentá de nuevo.")
    session.commit()
    return _catalogo_a_dict(fila)


# Models. The consumption fields of the sheet's Modelos tab; NULL = missing data, 0 = "no lleva".
CAMPOS_DE_CONSUMO = (
    "cuero_m2_por_unidad", "forro_m2_por_unidad", "flex_m2_por_unidad", "goma_eva_m2_por_unidad",
    "herrajes_usd_por_unidad", "hilo_y_cemento", "confeccion_estimada_ars", "horas_de_confeccion",
    "origen_de_los_consumos",
)


def detalle_modelo(session: Session, codigo: str) -> dict:
    forro = aliased(Material)
    fila = session.execute(
        select(Modelo, Categoria.nombre, forro.codigo)
        .outerjoin(Categoria, Categoria.id == Modelo.categoria_id)
        .outerjoin(forro, forro.id == Modelo.forro_id)
        .where(Modelo.codigo == codigo)
    ).one_or_none()
    if fila is None:
        raise NoEncontrado(f"No existe el modelo {codigo}.")
    m, categoria, forro_codigo = fila
    return {
        **_modelo_a_dict(m, categoria, forro_codigo), "horas_de_confeccion": m.horas_de_confeccion, "nota": m.nota,
        "modelo_excel_viejo": m.modelo_excel_viejo, "fila_excel_viejo": m.fila_excel_viejo,
        "productos": session.scalar(select(func.count(Producto.id)).where(Producto.modelo_id == m.id)) or 0,
    }


def _forro_del_modelo(session: Session, forro: str | None, forro_m2: Decimal | None) -> Material | None:
    if forro is None:
        if forro_m2 is not None and forro_m2 > 0:
            raise DatosInvalidos("Elegí el forro: hay metros cuadrados de forro sin material.")
        return None
    if forro_m2 is None:
        raise DatosInvalidos("Indicá cuántos m² de forro lleva (0 si no lleva).")
    return _material_de_receta(session, forro, "FORRO")


def crear_modelo(
    session: Session, *, nombre_del_modelo: str, categoria: str, tamano: str | None, nota: str | None,
    forro: str | None, **consumos,
) -> dict:
    """A new model starts unvalidated. The name must be unique (the sheet asks to add something that tells two apart)."""
    nombre = nombre_del_modelo.strip()
    if not nombre:
        raise DatosInvalidos("Falta el nombre del modelo.")
    if _nombre_repetido(session, Modelo.nombre_del_modelo, nombre):
        raise Conflicto(f"Ya hay un modelo con el nombre {nombre}: agregá algo que lo distinga.")
    categoria_fila = session.scalar(select(Categoria).where(Categoria.nombre == categoria))
    if categoria_fila is None:
        raise DatosInvalidos(f"No existe la categoría {categoria}.")
    forro_fila = _forro_del_modelo(session, forro, consumos["forro_m2_por_unidad"])
    fila = Modelo(
        codigo=f"MOD-{_siguiente_numero(session, Modelo.codigo, 'MOD'):04d}", nombre_del_modelo=nombre,
        categoria_id=categoria_fila.id, tamano=tamano, forro_id=forro_fila.id if forro_fila else None,
        validado=False, nota=_texto_o_nada(nota), **consumos,
    )
    _insertar(session, fila, "Ya hay un modelo con ese nombre, o no se pudo asignar el código; intentá de nuevo.")
    session.commit()
    return detalle_modelo(session, fila.codigo)


def _modelo_por_codigo(session: Session, codigo: str) -> Modelo:
    modelo = session.scalar(select(Modelo).where(Modelo.codigo == codigo).with_for_update())
    if modelo is None:
        raise NoEncontrado(f"No existe el modelo {codigo}.")
    return modelo


def cambiar_validado(session: Session, codigo: str, validado: bool) -> dict:
    """The one in-place flag of a model that carries no consumption: a person confirms (or withdraws) the numbers."""
    _modelo_por_codigo(session, codigo).validado = validado
    session.commit()
    return detalle_modelo(session, codigo)


def cambiar_consumos(session: Session, codigo: str, *, forro: str | None, quien: str, **consumos) -> dict:
    """Overwrite the consumptions of a model and reset `validado`. SUPUESTO: validar. No table may be added, so the
    previous values are not stored; they are logged (who, old, new). Saved quotes are snapshots and keep their
    numbers; every product of the model is costed with the new ones from now on."""
    modelo = _modelo_por_codigo(session, codigo)
    forro_fila = _forro_del_modelo(session, forro, consumos["forro_m2_por_unidad"])
    anterior_forro = session.scalar(select(Material.codigo).where(Material.id == modelo.forro_id)) if modelo.forro_id else None
    cambios = {}
    for campo in CAMPOS_DE_CONSUMO:
        if getattr(modelo, campo) != consumos[campo]:
            cambios[campo] = f"{getattr(modelo, campo)} -> {consumos[campo]}"
        setattr(modelo, campo, consumos[campo])
    if anterior_forro != forro:
        cambios["forro"] = f"{anterior_forro} -> {forro}"
    modelo.forro_id = forro_fila.id if forro_fila else None
    modelo.validado = False
    session.commit()
    logger.info("Model %s consumptions changed by %s: %s", codigo, quien, cambios or "no value changed")
    return detalle_modelo(session, codigo)


# --- Data quality ------------------------------------------------------------------------------------------------
# One list of findings. Product, lot and price rules are the ones that already live above (quote warnings, the sheet's
# Control columns, price jumps): this section only gathers and classifies them, it does not decide anything new.

SEVERIDADES = ("alta", "media", "baja")
AVISOS_ALTOS = (
    "Sin precio", "Falta el dólar", "Falta elegir", "Falta cuero", "El kit no tiene", "El componente", "Hay un ciclo",
    "Hay kits",
)


def severidad_de_aviso(texto: str) -> str:
    # SUPUESTO: validar. High = the product cannot be quoted at all; medium = it is quoted but something is off.
    return "alta" if texto.startswith(AVISOS_ALTOS) else "media"


def _hallazgo(severidad: str, entidad: str, mensaje: str, ruta: str) -> dict:
    return {"severidad": severidad, "entidad": entidad, "mensaje": mensaje, "ruta": ruta}


def controles_de_producto(datos: DatosProducto, nombre_repetido: bool) -> list[str]:
    """Productos!T, the part that is not already a quote warning (leather, sewing and kit components are)."""
    avisos = []
    if nombre_repetido:
        avisos.append("Nombre repetido: cambiá el color o poné un nombre propio")
    if datos.modelo_codigo is None and not datos.es_kit:
        avisos.append("Falta el modelo")
    if datos.fecha_de_alta is None:
        avisos.append("Falta la fecha de alta")
    if datos.fecha_de_alta and datos.fecha_de_recotizacion and datos.fecha_de_recotizacion < datos.fecha_de_alta:
        avisos.append("La recotización es anterior al alta")
    if datos.fecha_de_alta and datos.fecha_de_cierre and datos.fecha_de_cierre < datos.fecha_de_alta:
        avisos.append("El cierre es anterior al alta")
    if datos.estado_del_ciclo == "PRODUCIDO" and datos.fecha_de_cierre is None:
        avisos.append("Falta la fecha de cierre")
    return avisos


def hallazgos_de_precios(filas: list[dict]) -> list[dict]:
    """Precios!L over the price history rows of `listar_precios`."""
    repetidos = Counter((f["material"], f["color"], f["vigente_desde"]) for f in filas)
    hallazgos = []
    for f in filas:
        codigo, material, ruta = f["codigo"], f["material"], "/materiales"
        if f["salto_grande"]:
            hallazgos.append(_hallazgo(
                "media", codigo, f"Salto grande de precio: {f['variacion_pct']} % contra el anterior de {material}", ruta))
        if f["precio"] <= 0:
            hallazgos.append(_hallazgo("alta", codigo, f"Precio en cero: {material} el {f['vigente_desde'].isoformat()}", ruta))
        if f["iva_incluido"]:
            hallazgos.append(_hallazgo("media", codigo, f"Cargar sin IVA: el precio de {material} tiene el IVA incluido", ruta))
        if repetidos[(material, f["color"], f["vigente_desde"])] > 1:
            hallazgos.append(_hallazgo(
                "media", codigo, f"Fecha repetida: hay más de un precio de {material} para el {f['vigente_desde'].isoformat()}", ruta))
    return hallazgos


def estado_de_parametro(fuente_estado: str | None) -> tuple[str, str] | None:
    """None when the parameter is confirmed; otherwise (severity, message). SUPUESTO: validar. The sheet has no list of
    values for this column: "confirmad..." counts as confirmed, "pendiente / propuesta / a confirmar" as open."""
    texto = (fuente_estado or "").strip()
    minusculas = texto.lower()
    if minusculas.startswith("confirmad"):
        return None
    if minusculas.startswith(("pendiente", "propuesta")) or "confirmar" in minusculas:
        return "media", f"Sin confirmar: {texto}"
    return "baja", f"Sin marca de confirmación (fuente: {texto})" if texto else "Sin fuente ni confirmación"


def _ultimas_cotizaciones(session: Session) -> dict[int, tuple[Decimal, Decimal]]:
    """Newest saved quote of each product: (total ARS, dollar)."""
    ultimas: dict[int, tuple[Decimal, Decimal]] = {}
    for producto_id, total, dolar in session.execute(
        select(Cotizacion.producto_id, Cotizacion.total_ars, Cotizacion.dolar)
        .order_by(Cotizacion.fecha.desc(), Cotizacion.id.desc())
    ).all():
        ultimas.setdefault(producto_id, (total, dolar))
    return ultimas


def _hallazgos_de_productos(session: Session) -> tuple[list[dict], list[dict]]:
    base = cargar_productos(session)
    ctx = cargar_contexto(session)
    catalogo = expandir_kits(session, base)
    nombres = Counter(d.nombre for d in base if d.nombre)
    ultimas = _ultimas_cotizaciones(session)
    productos, recotizar = [], []
    if not ctx.dolares:
        # One finding instead of one per product: without a dollar nothing can be quoted.
        productos.append(_hallazgo("alta", "dolar", "Falta cargar el dólar: sin él no se puede calcular ningún costo", "/dolar"))
    for datos in base:
        ruta = f"/productos/{datos.codigo}"
        resultado, avisos = _costo_hoy_seguro(datos, ctx, catalogo) if ctx.dolares else (None, [])
        for texto in dict.fromkeys([*avisos, *controles_de_producto(datos, nombres[datos.nombre] > 1)]):
            productos.append(_hallazgo(severidad_de_aviso(texto), datos.codigo, texto, ruta))
        completo = _desglose_a_dict(resultado) is not None
        ultima = ultimas.get(datos.id)
        if marca_recotizar(resultado.cotizado.desglose if completo else None,
                           ultima[0] if ultima else None, ultima[1] if ultima else None, ctx.parametros):
            recotizar.append(_hallazgo(
                "media", datos.codigo,
                "Conviene recotizar: el costo de hoy o el dólar se movieron más que la tolerancia desde la última cotización", ruta))
    return productos, recotizar


def _hallazgos_de_modelos(session: Session) -> tuple[list[dict], list[dict]]:
    sin_validar, con_problemas = [], []
    filas = session.execute(
        select(Modelo.codigo, Modelo.nombre_del_modelo, Modelo.categoria_id, Modelo.cuero_m2_por_unidad, Modelo.forro_id,
               Modelo.forro_m2_por_unidad, Modelo.validado).order_by(Modelo.id)
    ).all()
    for codigo, nombre, categoria_id, cuero, forro_id, forro_m2, validado in filas:
        if not validado:
            sin_validar.append(_hallazgo("baja", codigo, f"Modelo sin validar: {nombre}", "/admin/modelos"))
        for falla in (
            "Falta la categoría" if categoria_id is None else None,
            "Falta el consumo de cuero" if cuero is None else None,
            "Falta elegir el forro" if (forro_m2 or 0) > 0 and forro_id is None else None,
        ):
            if falla:
                con_problemas.append(_hallazgo("media", codigo, f"{falla}: {nombre}", "/admin/modelos"))
    return sin_validar, con_problemas


def _hallazgos_de_materiales(session: Session, hoy: date) -> list[dict]:
    filas = session.execute(
        select(Material.codigo, Material.nombre, Material.cotizable, func.count(PrecioMaterial.id))
        .outerjoin(PrecioMaterial, and_(PrecioMaterial.material_id == Material.id, PrecioMaterial.vigente_desde <= hoy))
        .group_by(Material.id).order_by(Material.id)
    ).all()
    return [
        _hallazgo("alta" if cotizable else "baja", codigo,
                  f"Sin precio vigente: {nombre}" + ("" if cotizable else " (no es cotizable)"), "/materiales")
        for codigo, nombre, cotizable, precios in filas if precios == 0
    ]


def _hallazgos_de_lotes(session: Session) -> list[dict]:
    hallazgos = []
    for lote in _armar_lotes(session):
        ruta = f"/fabricacion/{lote['codigo']}"
        for aviso in lote["avisos"]:
            if aviso != AVISO_RENGLONES:  # the lines are listed one by one below
                hallazgos.append(_hallazgo(SEVERIDAD_DE_AVISO_DE_LOTE.get(aviso, "media"), lote["codigo"], aviso, ruta))
        for renglon in lote["items"]:
            for aviso in renglon["avisos"]:
                if aviso != AVISO_SIN_FECHA:  # already said once for the whole lot
                    hallazgos.append(_hallazgo(
                        SEVERIDAD_DE_AVISO_DE_LOTE.get(aviso, "media"), renglon["codigo"], f"{aviso} (lote {lote['codigo']})", ruta))
    return hallazgos


def _hallazgos_de_talleres_de_ejemplo(session: Session) -> list[dict]:
    return [
        _hallazgo("media", t["codigo"], f"Taller de ejemplo en uso: {t['nombre']} tiene {t['lotes']} lote(s) cargado(s)",
                  f"/talleres/{t['codigo']}")
        for t in listar_talleres(session) if t["ejemplo"] and t["lotes"] > 0
    ]


def _hallazgos_de_gastos(session: Session) -> list[dict]:
    hallazgos = []
    for gasto in session.scalars(select(GastoPeriodo).order_by(GastoPeriodo.periodo.desc(), GastoPeriodo.id)):
        ruta = f"/costos-fijos?periodo={gasto.periodo}"
        if gasto.monto_ars_del_mes is None:
            hallazgos.append(_hallazgo("media", gasto.codigo, f"Gasto sin monto: {gasto.concepto} ({gasto.periodo})", ruta))
        if gasto.ficticio:
            hallazgos.append(_hallazgo(
                "baja", gasto.codigo, f"Monto ficticio: {gasto.concepto} ({gasto.periodo}); reemplazalo por el real", ruta))
    return hallazgos


def _hallazgos_de_parametros(session: Session) -> list[dict]:
    hallazgos = []
    for p in session.scalars(select(Parametro).order_by(Parametro.id)):
        estado = estado_de_parametro(p.fuente_estado)
        if estado:
            hallazgos.append(_hallazgo(estado[0], p.codigo, f"{p.constante}: {estado[1]}", "/admin/parametros"))
    return hallazgos


def calidad_de_datos(session: Session, hoy: date | None = None) -> dict:
    """Findings grouped by topic, each with a severity, the entity code, a Spanish message and where to fix it."""
    hoy = hoy or date.today()
    productos, recotizar = _hallazgos_de_productos(session)
    modelos_sin_validar, modelos = _hallazgos_de_modelos(session)
    grupos = [
        ("productos", "Productos con avisos", productos),
        ("recotizar", "Productos que conviene recotizar", recotizar),
        ("modelos_sin_validar", "Modelos sin validar", modelos_sin_validar),
        ("modelos", "Modelos con datos faltantes", modelos),
        ("materiales", "Materiales sin precio vigente", _hallazgos_de_materiales(session, hoy)),
        ("precios", "Precios para revisar", hallazgos_de_precios(listar_precios(session, a_fecha=hoy))),
        ("lotes", "Lotes con problemas", _hallazgos_de_lotes(session)),
        ("talleres", "Talleres de ejemplo en uso", _hallazgos_de_talleres_de_ejemplo(session)),
        ("gastos_fijos", "Gastos fijos pendientes o ficticios", _hallazgos_de_gastos(session)),
        ("parametros", "Parámetros sin confirmar", _hallazgos_de_parametros(session)),
    ]
    todos = [h for _, _, hallazgos in grupos for h in hallazgos]
    resumen = {severidad: sum(1 for h in todos if h["severidad"] == severidad) for severidad in SEVERIDADES}
    return {
        "resumen": {**resumen, "total": len(todos)},
        "grupos": [{"clave": clave, "titulo": titulo, "total": len(hallazgos), "hallazgos": hallazgos}
                   for clave, titulo, hallazgos in grupos],
    }


# --- Loaders for the Google Sheet display copy (T6) ------------------------------------------------------------
# Read only. They reuse the loaders and the engine above; nothing is calculated again here.

def productos_costeados(session: Session) -> list[dict]:
    """Every product with its cost today, its latest INICIAL / FINAL quotes and the RECOTIZAR flag (Catalogo, Costos_Variables)."""
    base = cargar_productos(session)
    catalogo = expandir_kits(session, base)
    ctx = cargar_contexto(session)
    guardadas: dict[int, list[tuple]] = {}
    for producto_id, tipo, fecha, total, dolar in session.execute(
        select(Cotizacion.producto_id, Cotizacion.tipo, Cotizacion.fecha, Cotizacion.total_ars, Cotizacion.dolar)
        .order_by(Cotizacion.fecha.desc(), Cotizacion.id.desc())
    ):
        guardadas.setdefault(producto_id, []).append((tipo, fecha, total, dolar))  # newest first
    filas = []
    for datos in base:
        resultado, avisos = _costo_hoy_seguro(datos, ctx, catalogo)
        costo = _desglose_a_dict(resultado)
        propias = guardadas.get(datos.id, [])
        ultima = propias[0] if propias else None
        por_tipo = {}
        for tipo, _, total, _ in reversed(propias):  # oldest first, so the newest of each type wins
            por_tipo[tipo] = total
        filas.append({
            "codigo": datos.codigo, "nombre": datos.nombre, "categoria": datos.categoria,
            "estado_del_ciclo": datos.estado_del_ciclo, "quien_lo_confecciona": datos.quien, "es_kit": datos.es_kit,
            "fecha_de_alta": datos.fecha_de_alta, "costo": costo, "avisos": avisos,
            "recotizar": marca_recotizar(
                resultado.cotizado.desglose if costo and resultado else None,
                ultima[2] if ultima else None, ultima[3] if ultima else None, ctx.parametros),
            "inicial_ars": por_tipo.get("INICIAL"), "final_ars": por_tipo.get("FINAL"),
            "ultima_ars": ultima[2] if ultima else None, "ultima_fecha": ultima[1] if ultima else None,
        })
    return filas


def cotizaciones_guardadas(session: Session, nombres: dict[str, str] | None = None) -> list[dict]:
    """Every stored quote, by product code and date. `nombres` maps product code -> name (empty when not given)."""
    nombres = nombres or {}
    filas = session.execute(
        select(Cotizacion, Producto.codigo).join(Producto, Producto.id == Cotizacion.producto_id)
        .order_by(Producto.codigo, Cotizacion.fecha, Cotizacion.id)
    ).all()
    return [{**_cotizacion_a_dict(c, codigo), "producto_nombre": nombres.get(codigo, "")} for c, codigo in filas]


def productos_para_exportar(session: Session) -> list[dict]:
    """The load columns of Productos plus the computed name and category."""
    propios = dict(session.execute(select(Producto.codigo, Producto.nombre_propio)).all())
    return [{
        "codigo": d.codigo, "modelo": d.modelo_codigo, "cuero": d.cuero, "color": d.color,
        "quien_lo_confecciona": d.quien, "estado_del_ciclo": d.estado_del_ciclo, "fecha_de_alta": d.fecha_de_alta,
        "fecha_de_recotizacion": d.fecha_de_recotizacion, "fecha_de_cierre": d.fecha_de_cierre,
        "nombre_propio": propios.get(d.codigo), "es_kit": d.es_kit, "nota": d.nota, "nombre": d.nombre,
        "categoria": d.categoria,
    } for d in cargar_productos(session)]


def modelos_para_exportar(session: Session) -> list[dict]:
    """All models in sheet order, with the fields `listar_modelos` leaves out and the number of products that use each."""
    forro = aliased(Material)
    usados = dict(session.execute(select(Producto.modelo_id, func.count(Producto.id)).group_by(Producto.modelo_id)).all())
    filas = session.execute(
        select(Modelo, Categoria.nombre, forro.codigo)
        .outerjoin(Categoria, Categoria.id == Modelo.categoria_id)
        .outerjoin(forro, forro.id == Modelo.forro_id).order_by(Modelo.id)
    ).all()
    return [{
        **_modelo_a_dict(m, categoria, forro_codigo), "horas_de_confeccion": m.horas_de_confeccion, "nota": m.nota,
        "modelo_excel_viejo": m.modelo_excel_viejo, "fila_excel_viejo": m.fila_excel_viejo,
        "productos": usados.get(m.id, 0),
    } for m, categoria, forro_codigo in filas]


def costos_fijos_de_todos_los_periodos(session: Session) -> list[dict]:
    """`costos_fijos` of every period that has rows (newest first), each with its factory / store totals."""
    return [costos_fijos(session, periodo) for periodo in periodos_de_costos_fijos(session)["periodos"]]
