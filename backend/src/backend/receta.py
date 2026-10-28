"""Recipe generation and dated quotes, done in the app (the sheet only displays).

Pure functions over plain data: the caller loads rows, this module decides.
"""

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

from backend.costeo import Desglose, Linea, Precios, ZERO, costear

# Fixed material codes of the plantilla's recipe: flex, goma EVA, herrajes and thread/cement
# always use the same material (Receta sheet, column D).
FLEX = "MAT-FL01"
GOMA_EVA = "MAT-GE01"
HERRAJES = "MAT-HE00"
HILO_CEMENTO = "MAT-HC01"


@dataclass(frozen=True)
class ModeloReceta:
    cuero_m2: Decimal | None
    forro_codigo: str | None
    forro_m2: Decimal | None
    flex_m2: Decimal | None
    goma_eva_m2: Decimal | None
    herrajes_usd: Decimal | None
    hilo_cemento: Decimal | None
    confeccion_estimada: Decimal | None


@dataclass(frozen=True)
class ProductoReceta:
    cuero_codigo: str | None
    color: str | None
    quien: str | None  # "EXTERNA" | "INTERNA"
    es_kit: bool


@dataclass(frozen=True)
class Extra:
    material: str
    etapa: str
    color: str | None
    consumo: Decimal


@dataclass(frozen=True)
class LineaReceta:
    etapa: str
    material: str
    color: str | None
    consumo: Decimal


@dataclass(frozen=True)
class Receta:
    lineas: list[LineaReceta]
    avisos: list[str]
    quien: str | None
    confeccion_estimada: Decimal


def _positive(value: Decimal | None) -> bool:
    return value is not None and value > 0


def generar_receta(modelo: ModeloReceta, producto: ProductoReceta, extras: list[Extra]) -> Receta:
    """Model lines first, then the product's extra lines. Zero or missing consumption means "no lleva"."""
    lineas: list[LineaReceta] = []
    avisos: list[str] = []

    if _positive(modelo.cuero_m2):
        if producto.cuero_codigo:
            lineas.append(LineaReceta("CUERO", producto.cuero_codigo, producto.color, modelo.cuero_m2))
        else:
            avisos.append("Falta elegir el cuero")
    elif not producto.es_kit:
        avisos.append("Falta cuero")

    if _positive(modelo.forro_m2) and modelo.forro_codigo:
        lineas.append(LineaReceta("FORRO", modelo.forro_codigo, producto.color, modelo.forro_m2))
    for etapa, material, consumo in (
        ("FLEX", FLEX, modelo.flex_m2),
        ("GOMA_EVA", GOMA_EVA, modelo.goma_eva_m2),
        ("HERRAJES", HERRAJES, modelo.herrajes_usd),
        ("HILO_CEMENTO", HILO_CEMENTO, modelo.hilo_cemento),
    ):
        if _positive(consumo):
            lineas.append(LineaReceta(etapa, material, None, consumo))
    if not _positive(modelo.hilo_cemento) and not producto.es_kit:
        avisos.append("Falta hilo y cemento")

    lineas.extend(LineaReceta(e.etapa, e.material, e.color, e.consumo) for e in extras)
    return Receta(lineas, avisos, producto.quien, modelo.confeccion_estimada or ZERO)


def dolar_a_la_fecha(dolares: list[tuple[date, Decimal]], fecha: date) -> Decimal | None:
    """Newest rate not after `fecha`; None when there is none (never guess)."""
    validos = [(f, v) for f, v in dolares if f <= fecha]
    return max(validos, key=lambda fv: fv[0])[1] if validos else None


@dataclass(frozen=True)
class Cotizado:
    desglose: Desglose | None
    avisos: list[str] = field(default_factory=list)
    completa: bool = True


def cotizar_producto(
    receta: Receta,
    precios: Precios,
    etapa_de_material: dict[str, str],
    dolares: list[tuple[date, Decimal]],
    fecha: date,
    *,
    confeccion: Decimal,
    desperdicio_por_material: dict[str, Decimal] | None = None,
    desperdicio_default: Decimal = ZERO,
    componentes_kit: Decimal = ZERO,
    iva_es_costo: bool = False,
    iva_pct: Decimal = ZERO,
    arreglos_pct: Decimal = ZERO,
) -> Cotizado:
    """Quote a recipe with the prices and dollar valid at `fecha`.

    `confeccion` is the external per-unit price (see costeo.confeccion_externa); it is ignored
    for in-house products, whose sewing is a fixed salary.
    """
    avisos = list(receta.avisos)
    desperdicios = desperdicio_por_material or {}
    dolar = dolar_a_la_fecha(dolares, fecha)
    if dolar is None:
        avisos.append("Falta el dólar para esa fecha")
    if receta.quien not in ("EXTERNA", "INTERNA"):
        avisos.append("Falta elegir quién lo confecciona")

    lineas: list[Linea] = []
    for item in receta.lineas:
        precio = precios.buscar(item.material, item.color, fecha)
        if precio is None:
            avisos.append(f"Sin precio para {item.material} a esa fecha")
            continue
        etapa = etapa_de_material.get(item.material, item.etapa)
        lineas.append(Linea(etapa, item.consumo, desperdicios.get(item.material, desperdicio_default),
                            precio.precio, precio.moneda))

    if dolar is None:
        return Cotizado(None, avisos, False)
    desglose = costear(
        lineas, dolar,
        confeccion=confeccion if receta.quien == "EXTERNA" else ZERO,
        componentes_kit=componentes_kit, iva_es_costo=iva_es_costo, iva_pct=iva_pct, arreglos_pct=arreglos_pct,
    )
    blocking = [a for a in avisos if a.startswith(("Sin precio", "Falta elegir", "Falta el dólar"))]
    return Cotizado(desglose, avisos, not blocking)
