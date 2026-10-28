"""Pure costing engine for plantilla v4.1: no database, no clock, no network.

Rules come from the plantilla's LEEME section 6. All money is Decimal.
"""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

ZERO = Decimal(0)

MATERIAL_STAGES = ("CUERO", "FORRO", "FLEX", "GOMA_EVA", "HERRAJES", "HILO_CEMENTO")
# CORTE is always 0: Alderete's salary is a fixed cost (Costos_Fijos).
STAGES = (*MATERIAL_STAGES, "CORTE", "CONFECCION")
CURRENCIES = ("ARS", "USD")


@dataclass(frozen=True)
class Linea:
    """One recipe line: net consumption x (1 + waste) x unit price."""

    etapa: str
    consumo: Decimal
    desperdicio: Decimal
    precio: Decimal
    moneda: str


@dataclass(frozen=True)
class Desglose:
    etapas: dict[str, Decimal]
    subtotal: Decimal
    componentes_kit: Decimal
    iva_compras: Decimal
    arreglos: Decimal
    total_ars: Decimal
    total_usd: Decimal
    dolar: Decimal


def costear(
    lineas: list[Linea],
    dolar: Decimal,
    *,
    confeccion: Decimal = ZERO,
    componentes_kit: Decimal = ZERO,
    iva_es_costo: bool = False,
    iva_pct: Decimal = ZERO,
    arreglos_pct: Decimal = ZERO,
) -> Desglose:
    if dolar <= 0:
        raise ValueError("dolar must be positive")
    etapas = {stage: ZERO for stage in STAGES}
    for line in lineas:
        if line.etapa not in MATERIAL_STAGES:
            raise ValueError(f"stage not allowed in a recipe line: {line.etapa}")
        if line.moneda not in CURRENCIES:
            raise ValueError(f"unknown currency: {line.moneda}")
        if line.consumo < 0 or line.desperdicio < 0 or line.precio < 0:
            raise ValueError("consumo, desperdicio and precio cannot be negative")
        unit_ars = line.precio * dolar if line.moneda == "USD" else line.precio
        etapas[line.etapa] += line.consumo * (1 + line.desperdicio) * unit_ars
    if confeccion < 0:
        raise ValueError("confeccion cannot be negative")
    etapas["CONFECCION"] = confeccion
    subtotal = sum(etapas.values(), ZERO)
    base = subtotal + componentes_kit
    iva = iva_pct * base if iva_es_costo else ZERO
    arreglos = arreglos_pct * base
    total = base + iva + arreglos
    return Desglose(etapas, subtotal, componentes_kit, iva, arreglos, total, total / dolar, dolar)


@dataclass(frozen=True)
class PrecioVigente:
    material: str
    color: str | None
    precio: Decimal
    moneda: str
    vigente_desde: date


class Precios:
    """Append-only price history; lookups never see prices from the future."""

    def __init__(self, filas: list[PrecioVigente]):
        self._filas = list(filas)

    def buscar(self, material: str, color: str | None, fecha: date) -> PrecioVigente | None:
        candidatas = [f for f in self._filas if f.material == material and f.vigente_desde <= fecha]
        for wanted in ((color,) if color else ()) + (None,):
            same = [f for f in candidatas if f.color == wanted]
            if same:
                return max(same, key=lambda f: f.vigente_desde)
        return None


def precio_a_la_fecha(precios: Precios, material: str, color: str | None, fecha: date) -> PrecioVigente | None:
    """Colour-specific price first, then the generic one, newest not after `fecha`."""
    return precios.buscar(material, color, fecha)


@dataclass(frozen=True)
class ItemLote:
    fecha: date
    cotizado: Decimal | None
    pagado: Decimal | None


def confeccion_externa(items: list[ItemLote], estimado: Decimal, hasta: date | None = None) -> Decimal:
    """Per-unit external sewing: average of the newest lot's price (paid, else quoted), else the estimate."""
    priced = []
    for it in items:
        if hasta is not None and it.fecha > hasta:
            continue
        price = it.pagado if it.pagado and it.pagado > 0 else it.cotizado
        if price and price > 0:
            priced.append((it.fecha, price))
    if not priced:
        return estimado
    newest = max(f for f, _ in priced)
    same = [p for f, p in priced if f == newest]
    return sum(same, ZERO) / len(same)


def costo_kit(componentes: list[tuple[Decimal, Decimal]]) -> Decimal:
    """Kit components cost: sum of quantity x component total."""
    return sum((qty * total for qty, total in componentes), ZERO)


def necesita_recotizar(
    costo_hoy: Decimal,
    costo_ultima: Decimal,
    dolar_ultima: Decimal,
    dolar_hoy: Decimal,
    *,
    desvio_tol: Decimal,
    dolar_tol: Decimal,
) -> bool:
    """Flag RECOTIZAR when cost or dollar moved beyond the tolerances (fractions, 0.05 = 5 %)."""
    if costo_ultima > 0 and abs(costo_hoy - costo_ultima) / costo_ultima > desvio_tol:
        return True
    return dolar_ultima > 0 and abs(dolar_hoy - dolar_ultima) / dolar_ultima > dolar_tol
