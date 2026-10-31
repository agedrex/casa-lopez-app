"""Leather stock is derived from append-only movements in the DER v3 tables."""

from collections import defaultdict
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from backend.models import (
    Color, Etapa, Material, Modelo, MovimientoCuero, OrdenItem, Parametro,
    Persona, PiezaCuero, PrecioMaterial, Producto, TipoCambio,
)
from backend.servicios import Conflicto, DatosInvalidos, NoEncontrado, _insertar, _siguiente_numero


# SUPUESTO: regla de Robert; TODO pasar a parametro
DESPERDICIO_NATURAL = Decimal("0.10")
ZERO = Decimal("0")
CIEN = Decimal("100")
PRECISION_M2 = Decimal("0.000001")
ORDEN_ESTADOS = {"RETAZO": 0, "EN_USO": 1, "ENTERA": 2}


def calcular_pieza(pieza: PiezaCuero, movimientos: list[MovimientoCuero]) -> dict:
    """The DER stock formula, with natural and later waste kept separate."""
    inicial = pieza.m2_iniciales
    natural = (inicial * DESPERDICIO_NATURAL).quantize(PRECISION_M2, ROUND_HALF_UP) if pieza.fecha_de_compra else ZERO
    desperdicio = abs(sum((m.m2 for m in movimientos if m.tipo == "DESPERDICIO"), ZERO))
    return {
        "disponible": inicial + sum((m.m2 for m in movimientos), ZERO),
        "natural": natural,
        "irrecuperable": max(desperdicio - natural, ZERO),
        "cortado": abs(sum((m.m2 for m in movimientos if m.tipo == "CORTE"), ZERO)),
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
    proveedor: str | None,
) -> dict:
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
    if origen == "COMPRA":
        _insertar(session, MovimientoCuero(
            fecha=fecha_de_compra, pieza_cuero_id=pieza.id, tipo="DESPERDICIO",
            m2=-(m2_iniciales * DESPERDICIO_NATURAL).quantize(PRECISION_M2, ROUND_HALF_UP),
        ), "No se pudo registrar el desperdicio natural.")
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
            "material": mat.codigo, "color": nombre_color, "comprado": ZERO, "natural": ZERO,
            "cuero_total_real": ZERO, "cortado": ZERO, "irrecuperable": ZERO, "disponible": ZERO,
            "costo_desperdicio_ars": ZERO, "porcentaje_desperdicio_neto": None,
            "piezas": [], "umbral_medido": None, "umbral_retazo_m2": umbral, "avisos": [],
        })
        calculo = calcular_pieza(pieza, movimientos.get(pieza.id, []))
        grupo["piezas"].append(_resumen_pieza(pieza, mat.codigo, nombre_color, movimientos.get(pieza.id, [])))
        if pieza.fecha_de_compra:
            grupo["comprado"] += pieza.m2_iniciales
        grupo["natural"] += calculo["natural"]
        grupo["cuero_total_real"] += pieza.m2_iniciales - calculo["natural"]
        grupo["cortado"] += calculo["cortado"]
        grupo["irrecuperable"] += calculo["irrecuperable"]
        if pieza.estado != "CERRADA":
            grupo["disponible"] += calculo["disponible"]
        desperdiciado = calculo["natural"] + calculo["irrecuperable"]
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
            grupo["porcentaje_desperdicio_neto"] = (grupo["natural"] + grupo["irrecuperable"]) / grupo["comprado"] * CIEN
        medidos = casos[clave]
        if medidos:
            porcentajes = [pct for _, pct in medidos if pct is not None]
            grupo["umbral_medido"] = {
                "casos": len(medidos),
                "promedio_m2": sum((m2 for m2, _ in medidos), ZERO) / len(medidos),
                "promedio_pct_comprado": sum(porcentajes, ZERO) / len(porcentajes) if porcentajes else None,
            }
    return list(grupos.values())


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
