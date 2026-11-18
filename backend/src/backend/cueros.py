"""Leather stock is derived from append-only movements in the DER v3 tables."""

from collections import defaultdict
from datetime import date
from decimal import Decimal

from sqlalchemy import func, or_, select, true
from sqlalchemy.orm import Session

from backend.models import (
    Color, Etapa, Material, Modelo, MovimientoCuero, OrdenFabricacion, OrdenItem, Parametro,
    Persona, PiezaCuero, PrecioMaterial, Producto, TipoCambio, renglon_quitado,
)
from backend.servicios import (
    Conflicto, DatosInvalidos, NoEncontrado, _info_productos, _insertar, _rango_del_mes, _siguiente_numero, costos_fijos, mes_de,
)


ZERO = Decimal("0")
CIEN = Decimal("100")
ORDEN_ESTADOS = {"RETAZO": 0, "EN_USO": 1, "ENTERA": 2}


def calcular_pieza(pieza: PiezaCuero, movimientos: list[MovimientoCuero]) -> dict:
    """Stock formula: the whole piece is what was bought; only a decided remainder is a loss."""
    cortado = abs(sum((m.m2 for m in movimientos if m.tipo == "CORTE"), ZERO))
    return {
        "disponible": pieza.m2_iniciales + sum((m.m2 for m in movimientos), ZERO),
        "irrecuperable": abs(sum((m.m2 for m in movimientos if m.tipo == "DESPERDICIO"), ZERO)),
        "cortado": cortado,
        "porcentaje_usado": cortado / pieza.m2_iniciales * CIEN if pieza.m2_iniciales > ZERO else ZERO,
    }


def _pieza(session: Session, codigo: str, *, bloquear: bool = False) -> PiezaCuero:
    consulta = select(PiezaCuero).where(PiezaCuero.codigo == codigo)
    fila = session.scalar(consulta.with_for_update() if bloquear else consulta)
    if fila is None:
        raise NoEncontrado(f"No existe la pieza de cuero {codigo}.")
    return fila


def _movimientos(session: Session, ids: list[int]) -> dict[int, list[MovimientoCuero]]:
    if not ids:
        return {}
    filas = session.scalars(select(MovimientoCuero).where(MovimientoCuero.pieza_cuero_id.in_(ids))
                            .order_by(MovimientoCuero.fecha, MovimientoCuero.id)).all()
    por_pieza: dict[int, list[MovimientoCuero]] = defaultdict(list)
    for fila in filas:
        por_pieza[fila.pieza_cuero_id].append(fila)
    return por_pieza


def _filas(session: Session, material: str | None = None, color: str | None = None):
    consulta = (select(PiezaCuero, Material, Color.nombre)
                .join(Material, Material.id == PiezaCuero.material_id)
                .outerjoin(Color, Color.id == PiezaCuero.color_id)
                .order_by(Material.codigo, Color.nombre, PiezaCuero.codigo))
    if material:
        consulta = consulta.where(Material.codigo == material)
    if color:
        consulta = consulta.where(Color.nombre == color)
    return session.execute(consulta).all()


def _resumen_pieza(pieza: PiezaCuero, material: str, color: str | None, movimientos: list[MovimientoCuero]) -> dict:
    return {
        "codigo": pieza.codigo, "material": material, "color": color,
        "fecha_de_compra": pieza.fecha_de_compra, "proveedor": pieza.proveedor,
        "m2_iniciales": pieza.m2_iniciales, "precio_pagado_por_m2": pieza.precio_pagado_por_m2,
        "moneda": pieza.moneda, "estado": pieza.estado,
        **calcular_pieza(pieza, movimientos),
    }


def crear_pieza(
    session: Session, *, origen: str, material: str, color: str | None, m2_iniciales: Decimal,
    fecha_de_compra: date | None, precio_pagado_por_m2: Decimal | None, moneda: str | None,
    proveedor: str | None, commit: bool = True,
) -> dict:
    """Create a piece. `commit=False` lets a caller (a supplier order) keep it inside its own transaction."""
    if (origen == "COMPRA") != (fecha_de_compra is not None):
        raise DatosInvalidos("COMPRA requiere fecha_de_compra; SOBRANTE_EXISTENTE debe dejarla vacía.")
    if (precio_pagado_por_m2 is None) != (moneda is None):
        raise DatosInvalidos("El precio pagado por m² y su moneda deben informarse juntos.")
    fila_material = session.execute(select(Material, Etapa.codigo).join(Etapa, Etapa.id == Material.etapa_id)
                                     .where(Material.codigo == material)).one_or_none()
    if fila_material is None:
        raise DatosInvalidos(f"No existe el material {material}.")
    material_fila, etapa = fila_material
    if etapa != "CUERO":
        raise DatosInvalidos(f"El material {material} no pertenece a la etapa CUERO.")
    color_fila = session.scalar(select(Color).where(Color.nombre == color)) if color else None
    if color and color_fila is None:
        raise DatosInvalidos(f"No existe el color {color}.")
    pieza = PiezaCuero(
        codigo=f"PZC-{_siguiente_numero(session, PiezaCuero.codigo, 'PZC'):04d}",
        material_id=material_fila.id, color_id=color_fila.id if color_fila else None,
        fecha_de_compra=fecha_de_compra, proveedor=proveedor, m2_iniciales=m2_iniciales,
        precio_pagado_por_m2=precio_pagado_por_m2, moneda=moneda,
        estado="ENTERA" if origen == "COMPRA" else "RETAZO",
    )
    _insertar(session, pieza, "No se pudo asignar el código de la pieza; intentá de nuevo.")
    if commit:
        session.commit()
    return detalle_pieza(session, pieza.codigo)


def detalle_pieza(session: Session, codigo: str) -> dict:
    pieza = _pieza(session, codigo)
    material = session.scalar(select(Material.codigo).where(Material.id == pieza.material_id))
    color = session.scalar(select(Color.nombre).where(Color.id == pieza.color_id)) if pieza.color_id else None
    movimientos = _movimientos(session, [pieza.id]).get(pieza.id, [])
    return {
        **_resumen_pieza(pieza, material, color, movimientos),
        "movimientos": [{
            "id": m.id, "fecha": m.fecha, "tipo": m.tipo, "m2": m.m2,
            "orden_item_id": m.orden_item_id, "registro_id": m.registro_id, "unidades": m.unidades,
        } for m in movimientos],
    }


def cortar(
    session: Session, codigo: str, *, m2: Decimal, orden_item: str, fecha: date,
    registro_id: int | None, unidades: Decimal | None,
) -> dict:
    pieza = _pieza(session, codigo, bloquear=True)
    if pieza.estado == "CERRADA":
        raise Conflicto(f"La pieza {codigo} está cerrada y no se puede cortar.")
    item = session.scalar(select(OrdenItem).where(OrdenItem.codigo == orden_item))
    if item is None:
        raise DatosInvalidos(f"No existe el renglón de lote {orden_item}.")
    if session.scalar(select(renglon_quitado()).where(OrdenItem.id == item.id)):
        raise DatosInvalidos(f"El renglón {orden_item} fue quitado del lote: no se puede cortar cuero para él.")
    producto = session.get(Producto, item.producto_id)
    if producto is None or (producto.cuero_id, producto.color_id) != (pieza.material_id, pieza.color_id):
        raise DatosInvalidos("El cuero y color de la pieza no coinciden con el producto del lote.")
    if registro_id is not None and session.get(Persona, registro_id) is None:
        raise DatosInvalidos(f"No existe la persona {registro_id}.")
    disponible = calcular_pieza(pieza, _movimientos(session, [pieza.id]).get(pieza.id, []))["disponible"]
    if m2 > disponible:
        raise DatosInvalidos(f"La pieza {codigo} tiene {disponible} m² disponibles; no alcanza para {m2} m².")
    _insertar(session, MovimientoCuero(
        fecha=fecha, pieza_cuero_id=pieza.id, tipo="CORTE", m2=-m2,
        orden_item_id=item.id, registro_id=registro_id, unidades=unidades,
    ), "No se pudo registrar el corte.")
    if pieza.estado == "ENTERA":
        pieza.estado = "EN_USO"
    session.commit()
    return detalle_pieza(session, codigo)


def decidir_sobrante(session: Session, codigo: str, *, decision: str, fecha: date) -> dict:
    pieza = _pieza(session, codigo, bloquear=True)
    if pieza.estado == "CERRADA":
        raise Conflicto(f"La pieza {codigo} ya está cerrada.")
    disponible = calcular_pieza(pieza, _movimientos(session, [pieza.id]).get(pieza.id, []))["disponible"]
    if decision == "REUTILIZABLE":
        pieza.estado = "RETAZO"
    else:
        if disponible > ZERO:
            _insertar(session, MovimientoCuero(
                fecha=fecha, pieza_cuero_id=pieza.id, tipo="DESPERDICIO", m2=-disponible,
            ), "No se pudo registrar el sobrante irrecuperable.")
        pieza.estado = "CERRADA"
    session.commit()
    return detalle_pieza(session, codigo)


def _precio_ars(session: Session, pieza: PiezaCuero, dolar: Decimal | None, hoy: date) -> Decimal | None:
    precio, moneda = pieza.precio_pagado_por_m2, pieza.moneda
    if precio is None or moneda is None:
        vigente = session.scalar(
            select(PrecioMaterial).where(
                PrecioMaterial.material_id == pieza.material_id,
                or_(PrecioMaterial.color_id == pieza.color_id, PrecioMaterial.color_id.is_(None))
                if pieza.color_id else PrecioMaterial.color_id.is_(None),
                PrecioMaterial.unidad_del_precio == "m2", PrecioMaterial.vigente_desde <= hoy,
            ).order_by(PrecioMaterial.color_id.desc().nulls_last(),
                       PrecioMaterial.vigente_desde.desc(), PrecioMaterial.id.desc())
        )
        if vigente is None:
            return None
        precio, moneda = vigente.precio, vigente.moneda
    return precio * dolar if moneda == "USD" and dolar is not None else precio if moneda == "ARS" else None


def listar_cueros(session: Session, material: str | None = None, color: str | None = None) -> list[dict]:
    filas = _filas(session, material, color)
    movimientos = _movimientos(session, [pieza.id for pieza, _, _ in filas])
    hoy = date.today()
    dolar = session.scalar(select(TipoCambio.ars_por_usd).where(TipoCambio.fecha <= hoy)
                           .order_by(TipoCambio.fecha.desc(), TipoCambio.id.desc()))
    umbral = session.scalar(select(Parametro.valor).where(Parametro.codigo == "UMBRAL_RETAZO_M2"))
    grupos: dict[tuple[int, int | None], dict] = {}
    casos: dict[tuple[int, int | None], list[tuple[Decimal, Decimal | None]]] = defaultdict(list)
    for pieza, mat, nombre_color in filas:
        clave = (pieza.material_id, pieza.color_id)
        grupo = grupos.setdefault(clave, {
            "material": mat.codigo, "color": nombre_color, "comprado": ZERO, "cortado": ZERO, "irrecuperable": ZERO, "disponible": ZERO,
            "costo_desperdicio_ars": ZERO, "porcentaje_desperdicio_neto": None,
            "piezas": [], "umbral_medido": None, "umbral_retazo_m2": umbral, "avisos": [],
        })
        calculo = calcular_pieza(pieza, movimientos.get(pieza.id, []))
        grupo["piezas"].append(_resumen_pieza(pieza, mat.codigo, nombre_color, movimientos.get(pieza.id, [])))
        if pieza.fecha_de_compra:
            grupo["comprado"] += pieza.m2_iniciales
        grupo["cortado"] += calculo["cortado"]
        grupo["irrecuperable"] += calculo["irrecuperable"]
        if pieza.estado != "CERRADA":
            grupo["disponible"] += calculo["disponible"]
        desperdiciado = calculo["irrecuperable"]
        if desperdiciado:
            precio = _precio_ars(session, pieza, dolar, hoy)
            if precio is None:
                grupo["costo_desperdicio_ars"] = None
                grupo["avisos"].append(f"Sin precio por m² o dólar vigente para {pieza.codigo}.")
            elif grupo["costo_desperdicio_ars"] is not None:
                grupo["costo_desperdicio_ars"] += desperdiciado * precio
        if pieza.estado == "CERRADA" and calculo["irrecuperable"] > ZERO:
            porcentaje = calculo["irrecuperable"] / pieza.m2_iniciales * CIEN if pieza.fecha_de_compra else None
            casos[clave].append((calculo["irrecuperable"], porcentaje))
    for clave, grupo in grupos.items():
        if grupo["comprado"] > ZERO:
            grupo["porcentaje_desperdicio_neto"] = grupo["irrecuperable"] / grupo["comprado"] * CIEN
        medidos = casos[clave]
        if medidos:
            porcentajes = [pct for _, pct in medidos if pct is not None]
            grupo["umbral_medido"] = {
                "casos": len(medidos),
                "promedio_m2": sum((m2 for m2, _ in medidos), ZERO) / len(medidos),
                "promedio_pct_comprado": sum(porcentajes, ZERO) / len(porcentajes) if porcentajes else None,
            }
    return list(grupos.values())


def _opciones_disponibles(session: Session) -> dict[tuple[int, int | None], list[dict]]:
    """Pieces with leather left, by (material id, color id), scraps first. The single source of stock for `alcanza` and the lot summary."""
    filas = _filas(session)
    movimientos = _movimientos(session, [pieza.id for pieza, _, _ in filas])
    opciones: dict[tuple[int, int | None], list[dict]] = defaultdict(list)
    for pieza, mat, nombre_color in filas:
        if pieza.estado == "CERRADA":
            continue
        disponible = calcular_pieza(pieza, movimientos.get(pieza.id, []))["disponible"]
        if disponible > ZERO:
            opciones[(pieza.material_id, pieza.color_id)].append({
                "codigo": pieza.codigo, "material": mat.codigo, "color": nombre_color,
                "estado": pieza.estado, "disponible": disponible,
            })
    for piezas in opciones.values():
        piezas.sort(key=lambda p: (ORDEN_ESTADOS[p["estado"]], p["codigo"]))
    return opciones


def alcanza(session: Session, producto: str, cantidad: Decimal) -> dict:
    fila = session.scalar(select(Producto).where(Producto.codigo == producto))
    if fila is None:
        raise NoEncontrado(f"No existe el producto {producto}.")
    modelo = session.get(Modelo, fila.modelo_id) if fila.modelo_id else None
    base = {"producto": producto, "cantidad": cantidad, "necesario": None, "disponible": ZERO,
            "alcanza": False, "faltante": None, "piezas": [], "alternativas": [], "mensaje": None}
    if modelo is None or modelo.cuero_m2_por_unidad is None or modelo.cuero_m2_por_unidad <= ZERO or fila.cuero_id is None:
        base["mensaje"] = "El producto no tiene modelo o consumo de cuero cargado."
        return base
    necesario = modelo.cuero_m2_por_unidad * cantidad
    opciones = _opciones_disponibles(session)
    elegidas = opciones[(fila.cuero_id, fila.color_id)]
    disponible = sum((p["disponible"] for p in elegidas), ZERO)
    base.update(necesario=necesario, disponible=disponible, alcanza=disponible >= necesario,
                faltante=max(necesario - disponible, ZERO), piezas=elegidas)
    if disponible >= necesario:
        return base
    cotizables = set(session.scalars(select(Material.id).join(Etapa, Etapa.id == Material.etapa_id)
                                     .where(Etapa.codigo == "CUERO", Material.cotizable.is_(True))).all())
    for (material_id, color_id), piezas in opciones.items():
        if (material_id, color_id) == (fila.cuero_id, fila.color_id):
            continue
        total = sum((p["disponible"] for p in piezas), ZERO)
        if total >= necesario and (material_id == fila.cuero_id or material_id in cotizables):
            base["alternativas"].append({
                "material": piezas[0]["material"], "color": piezas[0]["color"], "disponible": total,
            })
    material_codigo = session.scalar(select(Material.codigo).where(Material.id == fila.cuero_id))
    base["alternativas"].sort(key=lambda p: (p["material"] != material_codigo, p["material"], p["color"] or ""))
    return base


def retazos_del_mes(session: Session, periodo: str | None = None) -> dict:
    """Leather remainders written off in the month, as a cost of the business (the factory).

    Each `DESPERDICIO` movement of the month is valued at the price paid per m2 of its piece (or the price of the material
    on the purchase date when the piece has none), in ARS with the dollar of the purchase date. A movement that cannot be
    valued counts in `sin_precio` and is never turned into 0. Nothing is written to `gasto_periodo`: this is
    calculated, so the number can never disagree with the stock movements. Confirmed by the user (2026-11-17): the loss
    belongs to the month in which the remainder was written off.
    """
    periodo = periodo or mes_de(date.today())
    desde, hasta = _rango_del_mes(periodo)
    filas = session.execute(
        select(MovimientoCuero, PiezaCuero, Material.codigo, Color.nombre)
        .join(PiezaCuero, PiezaCuero.id == MovimientoCuero.pieza_cuero_id)
        .join(Material, Material.id == PiezaCuero.material_id)
        .outerjoin(Color, Color.id == PiezaCuero.color_id)
        .where(MovimientoCuero.tipo == "DESPERDICIO", MovimientoCuero.fecha >= desde, MovimientoCuero.fecha < hasta)
        .order_by(MovimientoCuero.fecha.desc(), MovimientoCuero.id.desc())).all()
    retazos = []
    for movimiento, pieza, material, color in filas:
        # What was paid is sunk at the purchase: a price in USD is valued with the dollar of that day, not of the
        # write-off. A piece that was not bought (existing remainder) falls back to the write-off date.
        fecha_de_precio = pieza.fecha_de_compra or movimiento.fecha
        dolar = session.scalar(select(TipoCambio.ars_por_usd).where(TipoCambio.fecha <= fecha_de_precio)
                               .order_by(TipoCambio.fecha.desc(), TipoCambio.id.desc()))
        precio = _precio_ars(session, pieza, dolar, fecha_de_precio)
        m2 = -movimiento.m2
        retazos.append({
            "pieza": pieza.codigo, "material": material, "color": color, "fecha": movimiento.fecha, "m2": m2,
            "precio_por_m2_ars": precio, "total_ars": m2 * precio if precio is not None else None,
        })
    total = sum((r["total_ars"] for r in retazos if r["total_ars"] is not None), ZERO)
    gastos = costos_fijos(session, periodo)["total_fabrica"]
    return {
        "periodo": periodo, "total_retazos": total, "sin_precio": sum(r["total_ars"] is None for r in retazos),
        "total_gastos_fabrica": gastos, "total_fabrica": gastos + total, "retazos": retazos,
    }


def _m2_texto(valor: Decimal) -> str:
    """Square meters for a message: no trailing zeros, decimal comma."""
    texto = format(valor.normalize(), "f")
    return (texto.rstrip("0").rstrip(".") if "." in texto else texto).replace(".", ",")


def _reservado_por_otros(session: Session, lote_id: int | None) -> dict[tuple[int, int | None], dict[str, Decimal]]:
    """Leather still to cut for the OTHER open lots, by (material id, color id) and lot code (a derived reservation).

    Same criteria as the summary of the lot: live lines only, no waste, a line needs `consumption x quantity`. What was already
    cut against a line has left the stock through its CORTE movements, so it is taken out here (per line, never below 0).
    Closed lots (CERRADA) reserve nothing. SUPUESTO: validar con Robert: it reserves from the creation of the lot, and it only informs.
    With `lote_id=None` (a lot that is still being created) every open lot reserves.
    """
    filas = session.execute(
        select(OrdenItem, OrdenFabricacion.codigo, Producto, Modelo.cuero_m2_por_unidad)
        .join(OrdenFabricacion, OrdenFabricacion.id == OrdenItem.orden_fabricacion_id)
        .join(Producto, Producto.id == OrdenItem.producto_id)
        .join(Modelo, Modelo.id == Producto.modelo_id)
        .where(OrdenFabricacion.id != lote_id if lote_id is not None else true(),
               OrdenFabricacion.estado != "CERRADA", ~renglon_quitado(),
               Producto.cuero_id.is_not(None), Modelo.cuero_m2_por_unidad > ZERO)
        .order_by(OrdenFabricacion.id, OrdenItem.id)).all()
    cortado = dict(session.execute(
        select(MovimientoCuero.orden_item_id, -func.sum(MovimientoCuero.m2))
        .where(MovimientoCuero.tipo == "CORTE", MovimientoCuero.orden_item_id.in_([i.id for i, _, _, _ in filas]))
        .group_by(MovimientoCuero.orden_item_id)).all()) if filas else {}
    reservado: dict[tuple[int, int | None], dict[str, Decimal]] = defaultdict(dict)
    for item, lote, producto, consumo in filas:
        pendiente = max(consumo * item.cantidad - cortado.get(item.id, ZERO), ZERO)
        if pendiente > ZERO:
            por_lote = reservado[(producto.cuero_id, producto.color_id)]
            por_lote[lote] = por_lote.get(lote, ZERO) + pendiente
    return reservado


def _mensaje_de_faltante(nombre: str, faltante: Decimal, disponible: Decimal, reservado: dict[str, Decimal]) -> str:
    texto = f"No alcanza: faltan {_m2_texto(faltante)} m² de {nombre}. Hay {_m2_texto(disponible)} m² en stock"
    if not reservado:
        return texto + "."
    lotes = ", ".join(f"{codigo} ({_m2_texto(m2)} m²)" for codigo, m2 in reservado.items()) \
        if len(reservado) > 1 else next(iter(reservado))
    total = sum(reservado.values(), ZERO)
    verbo = "tienen" if len(reservado) > 1 else "tiene"
    return texto + f" y {lotes} {verbo} reservados {_m2_texto(total)} m²."


def resumen_de_lote(session: Session, codigo: str) -> dict:
    """Leather a lot needs, by leather (material + color), against the stock of that same leather.

    Stock comes from `_opciones_disponibles`, the same source as `alcanza`, so a leather shared by several products
    of the lot is added up once instead of answering "enough" to each product on its own. Square meters already cut
    against an item of the lot are no longer in the stock, so they are taken out of what is still to cut (per item,
    never more than the item needs). Products without a model, a leather or a consumption go to `sin_consumo`.
    The leather that the OTHER open lots still have to cut is reserved (derived, informative: it blocks nothing):
    `alcanza` compares what is left to cut against `libre` = stock - reserved, and `mensaje` explains a shortage.
    No money here: the taller role reads this.
    """
    orden = session.scalar(select(OrdenFabricacion).where(OrdenFabricacion.codigo == codigo))
    if orden is None:
        raise NoEncontrado(f"No existe el lote {codigo}.")
    items = session.execute(
        select(OrdenItem, Producto, Modelo.cuero_m2_por_unidad)
        .join(Producto, Producto.id == OrdenItem.producto_id)
        .outerjoin(Modelo, Modelo.id == Producto.modelo_id)
        .where(OrdenItem.orden_fabricacion_id == orden.id, ~renglon_quitado()).order_by(OrdenItem.id)).all()
    cortado = dict(session.execute(
        select(MovimientoCuero.orden_item_id, -func.sum(MovimientoCuero.m2))
        .where(MovimientoCuero.tipo == "CORTE", MovimientoCuero.orden_item_id.in_([i.id for i, _, _ in items]))
        .group_by(MovimientoCuero.orden_item_id)).all()) if items else {}
    grupos: dict[tuple[int, int | None], dict] = {}
    sin_consumo: list[str] = []
    for item, producto, consumo in items:
        _sumar_necesidad(grupos, sin_consumo, producto, consumo, item.cantidad, cortado.get(item.id, ZERO))
    return {
        "lote": orden.codigo, "estado": orden.estado,
        **_cueros_contra_el_stock(session, grupos, sin_consumo, _reservado_por_otros(session, orden.id)),
    }


def _sumar_necesidad(
    grupos: dict[tuple[int, int | None], dict], sin_consumo: list[str], producto: Producto, consumo: Decimal | None,
    cantidad: Decimal, ya_cortado: Decimal,
) -> None:
    """Add one line to its leather group (`consumption x quantity`, less what was already cut, never below 0)."""
    if consumo is None or consumo <= ZERO or producto.cuero_id is None:
        if producto.codigo not in sin_consumo:
            sin_consumo.append(producto.codigo)
        return
    necesario = consumo * cantidad
    grupo = grupos.setdefault((producto.cuero_id, producto.color_id), {"necesario": ZERO, "ya_cortado": ZERO, "productos": []})
    grupo["necesario"] += necesario
    grupo["ya_cortado"] += min(ya_cortado, necesario)
    if producto.codigo not in grupo["productos"]:
        grupo["productos"].append(producto.codigo)


def _cueros_contra_el_stock(
    session: Session, grupos: dict[tuple[int, int | None], dict], sin_consumo: list[str],
    reservas: dict[tuple[int, int | None], dict[str, Decimal]],
) -> dict:
    """The leathers of a lot (existing or being created) against the stock and what the other open lots reserve.

    The one place that decides `libre`, `alcanza`, `faltante` and `mensaje`: the lot detail (`resumen_de_lote`) and the
    check while creating a lot (`alcanza_de_lineas`) both end here, so they cannot disagree.
    """
    opciones = _opciones_disponibles(session)
    nombres_de_materiales = {m.id: m for m in session.scalars(
        select(Material).where(Material.id.in_([cuero for cuero, _ in grupos])))}
    nombres_de_colores = {c.id: c.nombre for c in session.scalars(
        select(Color).where(Color.id.in_([color for _, color in grupos if color is not None])))}
    resultado = []
    for (cuero_id, color_id), grupo in grupos.items():
        material = nombres_de_materiales[cuero_id]
        por_cortar = grupo["necesario"] - grupo["ya_cortado"]
        disponible = sum((p["disponible"] for p in opciones.get((cuero_id, color_id), [])), ZERO)
        reservado = reservas.get((cuero_id, color_id), {})
        reservado_total = sum(reservado.values(), ZERO)
        libre = max(disponible - reservado_total, ZERO)
        nombre = material.nombre_corto or material.nombre
        color = nombres_de_colores.get(color_id) if color_id is not None else None
        faltante = max(por_cortar - libre, ZERO)
        resultado.append({
            "material": material.codigo, "material_nombre": material.nombre_corto or material.nombre,
            "color": nombres_de_colores.get(color_id) if color_id is not None else None,
            "necesario": grupo["necesario"], "ya_cortado": grupo["ya_cortado"], "por_cortar": por_cortar,
            "disponible": disponible, "reservado_por_otros": reservado_total, "reservado_por": list(reservado),
            "libre": libre, "alcanza": libre >= por_cortar,
            "faltante": faltante, "sobrante": max(libre - por_cortar, ZERO),
            "mensaje": _mensaje_de_faltante(f"{nombre} {color}" if color else nombre, faltante, disponible, reservado)
            if faltante > ZERO else None,
            "productos": grupo["productos"],
        })
    nombres = _info_productos(session, set(sin_consumo), con_costo=False)
    resultado.sort(key=lambda g: (g["material_nombre"], g["color"] or "", g["material"]))
    return {
        "cueros": resultado,
        "sin_consumo": [{"producto": c, "producto_nombre": nombres[c].nombre if c in nombres else c} for c in sin_consumo],
    }


def alcanza_de_lineas(session: Session, lineas: list[tuple[str, Decimal]]) -> dict:
    """The leather check of a lot that is still being created: (product code, units) lines, nothing is saved.

    S6 of flujo-modelos-lotes-precio. It ends in the same `_cueros_contra_el_stock` as the detail of a created lot: lines
    sharing a leather are added up and the stock is discounted by what EVERY open lot still has to cut (the lot does not
    exist yet, so none is excluded). So "Sí, alcanza" here means the same as the detail the lot will show. Informative only.
    """
    codigos = sorted({codigo for codigo, _ in lineas})
    filas = {producto.codigo: (producto, consumo) for producto, consumo in session.execute(
        select(Producto, Modelo.cuero_m2_por_unidad).outerjoin(Modelo, Modelo.id == Producto.modelo_id)
        .where(Producto.codigo.in_(codigos))).all()}
    for codigo in codigos:
        if codigo not in filas:
            raise NoEncontrado(f"No existe el producto {codigo}.")
    grupos: dict[tuple[int, int | None], dict] = {}
    sin_consumo: list[str] = []
    for codigo, cantidad in lineas:
        producto, consumo = filas[codigo]
        _sumar_necesidad(grupos, sin_consumo, producto, consumo, cantidad, ZERO)
    return _cueros_contra_el_stock(session, grupos, sin_consumo, _reservado_por_otros(session, None))
