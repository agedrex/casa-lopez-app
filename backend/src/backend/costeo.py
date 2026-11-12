"""Pure costing engine for plantilla v4.1: no database, no clock, no network.

Rules come from the plantilla's LEEME section 6. All money is Decimal.
"""

from dataclasses import dataclass
from datetime import date
from decimal import ROUND_CEILING, ROUND_HALF_UP, Decimal

ZERO = Decimal(0)
CUATRO_DECIMALES = Decimal("0.0001")  # the money scale (NUMERIC(14,4))

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


@dataclass(frozen=True)
class CostoPorUnidad:
    variable_por_unidad: Decimal
    fijo_por_unidad: Decimal | None
    total_por_unidad: Decimal | None


def costo_por_unidad(fijos: Decimal, unidades: Decimal, variable_por_unidad: Decimal) -> CostoPorUnidad:
    """Spread the month's fixed costs over the units produced. SUPUESTO: validar (volume is produced, not sold)."""
    if unidades <= 0:
        return CostoPorUnidad(variable_por_unidad, None, None)
    fijo = fijos / unidades
    return CostoPorUnidad(variable_por_unidad, fijo, variable_por_unidad + fijo)


@dataclass(frozen=True)
class Equilibrio:
    margen_por_unidad: Decimal | None
    unidades: Decimal | None
    motivo: str | None


def punto_de_equilibrio(fijos: Decimal, variable_por_unidad: Decimal, precio: Decimal | None) -> Equilibrio:
    """Units needed to cover the fixed costs at a price typed by the user; no number unless price > variable cost."""
    if precio is None:
        return Equilibrio(None, None, "SIN_PRECIO")
    margen = precio - variable_por_unidad
    if margen <= 0:
        return Equilibrio(margen, None, "PRECIO_NO_CUBRE_COSTO_VARIABLE")
    return Equilibrio(margen, (fijos / margen).to_integral_value(rounding=ROUND_CEILING), None)


@dataclass(frozen=True)
class ResultadoCvu:
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


def resultado_cvu(
    fijos: Decimal, unidades: Decimal, variable_por_unidad: Decimal, precio: Decimal,
) -> ResultadoCvu | None:
    """Cost-volume-profit for one month at a typed price; None unless the price is above the variable cost and there is volume.

    SUPUESTO: validar con Gerardo. The volume is what was produced in lots, not what was sold.
    """
    margen_unidad = precio - variable_por_unidad
    if unidades <= 0 or margen_unidad <= 0:
        return None
    ingresos = precio * unidades
    variable_total = variable_por_unidad * unidades
    contribucion = ingresos - variable_total
    equilibrio = (fijos / margen_unidad).to_integral_value(rounding=ROUND_CEILING)
    return ResultadoCvu(
        ingresos=ingresos, costo_variable_total=variable_total, margen_contribucion=contribucion,
        margen_contribucion_unidad=margen_unidad, margen_contribucion_pct=contribucion / ingresos * 100,
        costos_fijos=fijos, utilidad=contribucion - fijos, equilibrio_unidades=equilibrio,
        equilibrio_ingresos=equilibrio * precio, margen_seguridad_pct=(unidades - equilibrio) / unidades * 100,
    )


@dataclass(frozen=True)
class MargenContribucion:
    margen_unidad: Decimal
    margen_pct: Decimal | None
    markup_pct: Decimal | None
    veredicto: str


def importe_sobre_precio(precio_neto: Decimal, fraccion: Decimal) -> Decimal:
    """An amount that is a fraction of the net price (0.03 = 3 %), rounded to the money scale like the price taxes.

    A fraction of 0 gives a bare 0, so adding it to a margin leaves the number exactly as it was."""
    if not fraccion:
        return ZERO
    return (precio_neto * fraccion).quantize(CUATRO_DECIMALES, ROUND_HALF_UP)


def margen_por_hora(margen_unidad: Decimal, horas: Decimal | None) -> Decimal | None:
    """Contribution of one unit per workshop hour; None unless the hours are known and above 0 (nothing is invented)."""
    if horas is None or horas <= 0:
        return None
    return (margen_unidad / horas).quantize(CUATRO_DECIMALES, ROUND_HALF_UP)


def margen_de_contribucion(
    precio: Decimal, variable_por_unidad: Decimal, umbral_pct: Decimal | None = None,
    *, gasto_venta: Decimal = ZERO, iibb: Decimal = ZERO,
) -> MargenContribucion:
    """What one unit sold leaves to pay the fixed costs; fixed costs are deliberately not part of this verdict.

    Contribution = net price - variable cost - variable selling expense - IIBB (per unit). The last two default to 0, so
    callers that do not pass them (profitability, resale) get exactly what they always got.
    SUPUESTO: validar con Gerardo/Alejandro. The low-margin threshold is optional and has no default value.
    """
    margen = precio - variable_por_unidad - gasto_venta - iibb
    margen_pct = margen / precio * 100 if precio > 0 else None
    markup_pct = margen / variable_por_unidad * 100 if variable_por_unidad > 0 else None
    if margen <= 0:
        veredicto = "NO_CUBRE_VARIABLE"
    elif umbral_pct is not None and margen_pct is not None and margen_pct < umbral_pct:
        veredicto = "MC_BAJO"
    else:
        veredicto = "SALUDABLE"
    return MargenContribucion(margen, margen_pct, markup_pct, veredicto)


@dataclass(frozen=True)
class ProductoEnMezcla:
    precio: Decimal
    variable_por_unidad: Decimal
    unidades: Decimal
    gasto_venta_por_unidad: Decimal = ZERO
    iibb_por_unidad: Decimal = ZERO


@dataclass(frozen=True)
class EquilibrioGlobal:
    ingresos: Decimal | None
    margen_contribucion: Decimal | None
    margen_contribucion_pct: Decimal | None
    costos_fijos: Decimal | None
    utilidad: Decimal | None
    equilibrio_ingresos: Decimal | None
    equilibrio_unidades: Decimal | None
    margen_seguridad_pct: Decimal | None
    motivo: str | None


def equilibrio_con_mezcla(fijos: Decimal, mezcla: list[ProductoEnMezcla]) -> EquilibrioGlobal:
    """Break-even of the whole business for a sales mix; the fixed costs are global and never spread over products.

    No number unless there are sales and the mix leaves a positive contribution margin (then `motivo` says why).
    SUPUESTO: validar con Gerardo. The volume is a scenario typed by the owner, not units sold.
    """
    def sin_numeros(motivo: str) -> EquilibrioGlobal:
        return EquilibrioGlobal(None, None, None, None, None, None, None, None, motivo)

    ingresos = sum((p.precio * p.unidades for p in mezcla), ZERO)
    if ingresos <= 0:
        return sin_numeros("SIN_VENTAS")
    contribucion = sum(
        ((p.precio - p.variable_por_unidad - p.gasto_venta_por_unidad - p.iibb_por_unidad) * p.unidades for p in mezcla),
        ZERO)
    if contribucion <= 0:
        return sin_numeros("MC_NO_POSITIVO")
    unidades = sum((p.unidades for p in mezcla), ZERO)
    # fijos / (MC % / 100) and unidades x equilibrio_ingresos / ingresos, written with a single division each so exact
    # cases (like 50.000 units) do not pick up a spurious extra unit from the 28-digit Decimal context.
    equilibrio_ingresos = fijos * ingresos / contribucion
    return EquilibrioGlobal(
        ingresos=ingresos, margen_contribucion=contribucion, margen_contribucion_pct=contribucion / ingresos * 100,
        costos_fijos=fijos, utilidad=contribucion - fijos, equilibrio_ingresos=equilibrio_ingresos,
        equilibrio_unidades=(unidades * fijos / contribucion).to_integral_value(rounding=ROUND_CEILING),
        margen_seguridad_pct=(ingresos - equilibrio_ingresos) / ingresos * 100, motivo=None,
    )
