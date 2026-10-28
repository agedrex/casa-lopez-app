"""Service layer: loads rows, delegates every rule to the pure modules, persists snapshots.

Routers only call this module. Cost rules live in costeo.py and receta.py and are not
re-implemented here: this file loads plain data, calls them and stores the result.
Money is Decimal end to end; the API layer serializes it as strings.
"""

from dataclasses import dataclass, field, replace
from datetime import date
from decimal import Decimal

from sqlalchemy import Integer, cast, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, aliased

from backend.costeo import (
    Desglose, ItemLote, PrecioVigente, Precios, ZERO, confeccion_externa, costo_kit, necesita_recotizar,
)
from backend.models import (
    Categoria, Color, Cotizacion, Etapa, GastoPeriodo, Impuesto, KitComponente, Material, Modelo,
    OrdenFabricacion, OrdenItem, Parametro, Persona, PrecioMaterial, Producto, RecetaLinea, Taller, TipoCambio,
)
from backend.receta import (
    Cotizado, Extra, ModeloReceta, ProductoReceta, Receta, cotizar_producto, generar_receta,
)

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


def cargar_productos(
    session: Session, codigos: list[str] | None = None, limit: int | None = None, offset: int = 0,
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
            componentes=componentes.get(producto.id, []),
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


def listar_productos(session: Session, limit: int = 100, offset: int = 0) -> list[dict]:
    base = cargar_productos(session, limit=limit, offset=offset)
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


def listar_modelos(session: Session, limit: int = 500, offset: int = 0) -> list[dict]:
    forro = aliased(Material)
    filas = session.execute(
        select(Modelo, Categoria.nombre, forro.codigo)
        .outerjoin(Categoria, Categoria.id == Modelo.categoria_id)
        .outerjoin(forro, forro.id == Modelo.forro_id)
        .order_by(Modelo.id).limit(limit).offset(offset)
    ).all()
    return [{
        "codigo": m.codigo, "nombre_del_modelo": m.nombre_del_modelo, "categoria": categoria, "tamano": m.tamano,
        "cuero_m2_por_unidad": m.cuero_m2_por_unidad, "forro": forro_codigo,
        "forro_m2_por_unidad": m.forro_m2_por_unidad, "flex_m2_por_unidad": m.flex_m2_por_unidad,
        "goma_eva_m2_por_unidad": m.goma_eva_m2_por_unidad, "herrajes_usd_por_unidad": m.herrajes_usd_por_unidad,
        "hilo_y_cemento": m.hilo_y_cemento, "confeccion_estimada_ars": m.confeccion_estimada_ars,
        "origen_de_los_consumos": m.origen_de_los_consumos, "validado": m.validado,
    } for m, categoria, forro_codigo in filas]


def listar_materiales(session: Session) -> list[dict]:
    filas = session.execute(
        select(Material, Etapa.codigo).join(Etapa, Etapa.id == Material.etapa_id).order_by(Material.id)).all()
    return [{
        "codigo": m.codigo, "nombre": m.nombre, "nombre_corto": m.nombre_corto, "etapa": etapa,
        "unidad_de_consumo": m.unidad_de_consumo, "cotizable": m.cotizable,
        "controla_inventario": m.controla_inventario, "desperdicio_manual": m.desperdicio_manual,
    } for m, etapa in filas]


def listar_precios(session: Session, material: str | None = None, a_fecha: date | None = None) -> list[dict]:
    """Price history, newest first; `vigente` marks the row in force at `a_fecha` per material and color."""
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
    return [{
        "codigo": p.codigo, "material": codigo, "color": color, "proveedor": p.proveedor, "precio": p.precio,
        "moneda": p.moneda, "unidad_del_precio": p.unidad_del_precio, "iva_incluido": p.iva_incluido,
        "vigente_desde": p.vigente_desde, "nota_fuente": p.nota_fuente,
        "vigente": vigentes.get((p.material_id, p.color_id)) == p.id,
    } for p, codigo, color in filas]


def listar_dolar(session: Session) -> list[dict]:
    return [
        {"fecha": t.fecha, "ars_por_usd": t.ars_por_usd, "fuente": t.fuente, "tipo": t.tipo, "nota": t.nota}
        for t in session.scalars(select(TipoCambio).order_by(TipoCambio.fecha.desc(), TipoCambio.id.desc()))
    ]


def listar_parametros(session: Session) -> list[dict]:
    return [{
        "codigo": p.codigo, "constante": p.constante, "valor": p.valor, "valor_texto": p.valor_texto,
        "unidad": p.unidad, "que_es": p.que_es, "fuente_estado": p.fuente_estado,
    } for p in session.scalars(select(Parametro).order_by(Parametro.id))]


def listar_talleres(session: Session) -> list[dict]:
    return [{
        "codigo": t.codigo, "nombre": t.nombre, "cuit": t.cuit, "telefono": t.telefono, "direccion": t.direccion,
        "contacto": t.contacto, "activo": t.activo, "nota": t.nota,
    } for t in session.scalars(select(Taller).order_by(Taller.id))]


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
    """A lot with its items. The v3 tables hold no unit-cost rule for lots, so none is applied here."""
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
