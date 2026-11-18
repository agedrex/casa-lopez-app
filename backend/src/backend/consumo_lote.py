"""Consumption of a lot: what each product uses of each supply, and the total per supply of the whole lot.

Quantities only, never money (the taller role reads it). The per-unit lines come from the recipe the engine itself
uses (`receta.generar_receta`), so the quantities always match what the cost is made of. A kit counts through its
components. SUPUESTO: validar. Waste (`desperdicio`) is not added: it is 0 today and the leather summary of a lot
(`cueros.resumen_de_lote`) does not add it either.
"""

from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.costeo import ZERO
from backend.models import Material, OrdenFabricacion, OrdenItem, Producto
from backend.receta import generar_receta
from backend.servicios import DatosProducto, NoEncontrado, cargar_productos, expandir_kits

# A line in USD is a money amount (herrajes), not a quantity to buy or cut: it is left out of the consumption.
UNIDAD_DE_DINERO = "USD"
# Same order as the stages of the cost: leather, lining, flex, EVA, hardware, thread, ...
ORDEN_DE_ETAPAS = ("CUERO", "FORRO", "FLEX", "GOMA_EVA", "HERRAJES", "HILO_CEMENTO")

Clave = tuple[str, str | None]  # (material code, color)


def consumo_por_unidad(
    datos: DatosProducto, catalogo: dict[str, DatosProducto], _ruta: tuple[str, ...] = (),
) -> dict[Clave, tuple[str, Decimal]]:
    """Consumption of ONE unit of a product by (material, color): (stage, quantity). Kit components are expanded.

    A kit that loops back on itself stops there (the cost already reports it as a broken kit).
    """
    resultado: dict[Clave, tuple[str, Decimal]] = {}

    def sumar(clave: Clave, etapa: str, cantidad: Decimal) -> None:
        anterior = resultado.get(clave, (etapa, ZERO))[1]
        resultado[clave] = (etapa, anterior + cantidad)

    receta = generar_receta(datos.modelo, datos.producto, datos.extras)
    for linea in receta.lineas:
        sumar((linea.material, linea.color), linea.etapa, linea.consumo)
    for codigo, cantidad in datos.componentes:
        if codigo in _ruta or codigo == datos.codigo or codigo not in catalogo:
            continue
        for clave, (etapa, por_unidad) in consumo_por_unidad(catalogo[codigo], catalogo, (*_ruta, datos.codigo)).items():
            sumar(clave, etapa, por_unidad * cantidad)
    return resultado


def consumo_de_lote(session: Session, codigo: str) -> dict:
    """Per product of the lot (one row per item, in order) the consumption of each supply, then the total per supply."""
    orden = session.scalar(select(OrdenFabricacion).where(OrdenFabricacion.codigo == codigo))
    if orden is None:
        raise NoEncontrado(f"No existe el lote {codigo}.")
    items = session.execute(
        select(OrdenItem, Producto.codigo).join(Producto, Producto.id == OrdenItem.producto_id)
        .where(OrdenItem.orden_fabricacion_id == orden.id).order_by(OrdenItem.id)
    ).all()
    base = cargar_productos(session, sorted({producto for _, producto in items}))
    catalogo = expandir_kits(session, base)
    por_codigo = {datos.codigo: datos for datos in base}
    por_unidad = {datos.codigo: consumo_por_unidad(datos, catalogo) for datos in base}
    materiales = {m.codigo: m for m in session.scalars(select(Material).where(
        Material.codigo.in_({material for lineas in por_unidad.values() for material, _ in lineas})))}

    productos = []
    totales: dict[Clave, dict] = {}
    sin_consumo: list[dict] = []
    for item, producto in items:
        datos = por_codigo[producto]
        insumos = []
        for (material, color), (etapa, cantidad) in por_unidad[producto].items():
            fila = materiales[material]
            if cantidad <= ZERO or fila.unidad_de_consumo == UNIDAD_DE_DINERO:
                continue
            total = cantidad * item.cantidad
            insumos.append({
                "material": material, "material_nombre": fila.nombre_corto or fila.nombre, "color": color,
                "unidad": fila.unidad_de_consumo, "por_unidad": cantidad, "total": total, "_etapa": etapa,
            })
            acumulado = totales.setdefault((material, color), {
                "material": material, "material_nombre": fila.nombre_corto or fila.nombre, "color": color,
                "unidad": fila.unidad_de_consumo, "total": ZERO, "productos": [], "_etapa": etapa,
            })
            acumulado["total"] += total
            if producto not in acumulado["productos"]:
                acumulado["productos"].append(producto)
        insumos.sort(key=lambda i: _orden(i["_etapa"]))
        if not insumos and not any(p["producto"] == producto for p in sin_consumo):
            sin_consumo.append({"producto": producto, "producto_nombre": datos.nombre})
        productos.append({
            "item": item.codigo, "producto": producto, "producto_nombre": datos.nombre, "cantidad": item.cantidad,
            "insumos": [{k: v for k, v in i.items() if k != "_etapa"} for i in insumos],
        })
    resumen = sorted(totales.values(), key=lambda t: (_orden(t["_etapa"]), t["material_nombre"], t["color"] or ""))
    return {
        "lote": orden.codigo, "estado": orden.estado, "productos": productos,
        "totales": [{k: v for k, v in t.items() if k != "_etapa"} for t in resumen], "sin_consumo": sin_consumo,
    }


def _orden(etapa: str) -> int:
    return ORDEN_DE_ETAPAS.index(etapa) if etapa in ORDEN_DE_ETAPAS else len(ORDEN_DE_ETAPAS)

