"""Pure part of the example-data loader (scripts/cargar_ejemplo.py): refusals, the plan and its markers.

No database here: the plan is a function of (last month, today, people, workshops).
"""

import importlib.util
from collections import Counter
from datetime import date
from decimal import Decimal as D
from pathlib import Path

import pytest

RUTA = Path(__file__).parents[1] / "scripts" / "cargar_ejemplo.py"
_spec = importlib.util.spec_from_file_location("cargar_ejemplo", RUTA)
ce = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ce)

HOY = date(2026, 11, 4)
PERSONAS = [
    {"codigo": "PER-0001", "nombre": "Mariano", "rol": "CONSUMO_MOLDES", "activo": True},
    {"codigo": "PER-0002", "nombre": "Alderete", "rol": "CORTE", "activo": True},
    {"codigo": "PER-0003", "nombre": "Hugo", "rol": "CONFECCION", "activo": True},
    {"codigo": "PER-0004", "nombre": "Vendedora de caja 1", "rol": "VENTAS", "activo": True},
    {"codigo": "PER-0005", "nombre": "Vendedora de caja 2", "rol": "VENTAS", "activo": True},
    {"codigo": "PER-0007", "nombre": "Gerardo", "rol": "ENCARGADO", "activo": True},
]
TALLERES = ["TAL-0001", "TAL-0002", "TAL-0003"]


def plan(hasta="2026-11", hoy=HOY, personas=PERSONAS, talleres=TALLERES):
    return ce.planificar(hasta, hoy, personas, talleres)


# --- Refusals (exit code 2, Spanish message, nothing touched) -----------------------------------------------

@pytest.fixture
def sin_base(monkeypatch):
    """Any attempt to open the database fails the test: a refusal must happen before."""
    def prohibido(*_, **__):
        raise AssertionError("se intentó abrir la base de datos")
    monkeypatch.setattr(ce, "create_database_engine", prohibido)
    monkeypatch.delenv("RAILWAY_ENVIRONMENT_NAME", raising=False)


@pytest.mark.parametrize("argumentos", [
    [], ["--confirmar"], ["--entorno", "staging"], ["--entorno", "produccion", "--confirmar"],
    ["--entorno", "local", "--confirmar"], ["--solo-mostrar"],
])
def test_it_refuses_without_both_flags(argumentos, sin_base, capsys):
    assert ce.main(argumentos, hoy=HOY) == 2
    salida = capsys.readouterr()
    assert "staging" in salida.err and "--confirmar" in salida.err
    assert salida.out == ""


def test_it_refuses_a_railway_environment_that_is_not_staging(sin_base, monkeypatch, capsys):
    monkeypatch.setenv("RAILWAY_ENVIRONMENT_NAME", "production")
    assert ce.main(["--entorno", "staging", "--confirmar"], hoy=HOY) == 2
    assert "production" not in capsys.readouterr().err  # arbitrary environment text is never echoed


@pytest.mark.parametrize("hasta", ["2026-13", "2026-1", "noviembre", "2026-00"])
def test_it_refuses_a_bad_month(hasta, sin_base, capsys):
    assert ce.main(["--entorno", "staging", "--confirmar", "--hasta", hasta], hoy=HOY) == 2
    assert "AAAA-MM" in capsys.readouterr().err


def test_the_database_is_described_without_the_password():
    texto = ce.describir_base("postgresql://usuario:secreto@db.ejemplo.test:5432/costos")
    assert texto == "db.ejemplo.test:5432/costos"
    assert "secreto" not in texto and "usuario" not in texto


# --- The plan ----------------------------------------------------------------------------------------------

def test_the_plan_is_deterministic_and_covers_six_months():
    primero, segundo = plan(), plan()
    assert primero == segundo
    assert primero.meses == ["2026-06", "2026-07", "2026-08", "2026-09", "2026-10", "2026-11"]
    assert plan("2027-02").meses[0] == "2026-09" and plan("2027-02").meses[-1] == "2027-02"


def test_every_planned_row_carries_the_marker_and_keys_are_unique():
    filas = list(plan().filas())
    assert len(filas) > 60
    assert all("EJEMPLO" in fila.marca for fila in filas)
    claves = [(type(f).__name__, f.clave) for f in filas]
    assert len(claves) == len(set(claves))


def test_one_dollar_per_month_rising_two_to_four_percent():
    dolares = plan().dolares
    assert [d.periodo for d in dolares] == plan().meses
    for anterior, actual in zip(dolares, dolares[1:]):
        subida = (actual.valor - anterior.valor) / anterior.valor * 100
        assert D("1.5") <= subida <= D("4.5"), (anterior, actual)
    assert all(d.fecha <= HOY and d.fecha.strftime("%Y-%m") == d.periodo for d in dolares)


def test_price_updates_rise_between_three_and_twelve_percent_and_one_stays_old():
    precios = plan().precios
    por_serie = {}
    for p in sorted(precios, key=lambda p: p.fecha):
        por_serie.setdefault((p.material, p.color), []).append(p)
    assert len(por_serie) >= 3
    cuero = por_serie[("MAT-CU01", None)]
    assert len(cuero) >= 4
    for anterior, actual in zip(cuero, cuero[1:]):
        assert D(3) <= (actual.precio - anterior.precio) / anterior.precio * 100 <= D(12)
    rojo = por_serie[("MAT-CU02", "Rojo (ejemplo)")]  # the only price of its (material, color): it ages untouched
    assert len(rojo) == 1 and (HOY - rojo[0].fecha).days > 90
    assert all(p.fecha <= HOY for p in precios)


def test_products_only_use_quotable_leather_and_colors_that_the_plan_creates():
    p = plan()
    assert 6 <= len(p.productos) <= 10
    assert {x.cuero for x in p.productos} <= {"MAT-CU01", "MAT-CU02"}  # lagarto and yacaré are blocked
    colores = {c.nombre for c in p.colores}
    assert all(x.color in colores for x in p.productos if x.color)
    assert all(x.nombre.endswith("(ejemplo)") for x in p.productos)
    assert all(c.nombre.endswith("(ejemplo)") for c in p.colores)


def test_each_month_has_two_to_four_lots_in_house_and_at_workshops():
    p = plan()
    for mes in p.meses:
        lotes = [lote for lote in p.lotes if lote.periodo == mes]
        assert 2 <= len(lotes) <= 4, mes
        assert {lote.donde for lote in lotes} == {"INTERNA", "EXTERNA"}, mes
        for lote in lotes:
            assert 1 <= len(lote.renglones) <= 3
            assert len({r.producto for r in lote.renglones}) == len(lote.renglones)
            assert all(5 <= r.cantidad <= 40 for r in lote.renglones)
            assert lote.envio.strftime("%Y-%m") == mes and lote.envio <= HOY
            assert (lote.taller in TALLERES) == (lote.donde == "EXTERNA")


def test_lot_states_follow_the_calendar():
    p = plan()
    for lote in p.lotes:
        fechas = [fecha for _, fecha in lote.pasos]
        assert fechas == sorted(fechas) and all(lote.envio <= f <= HOY for f in fechas)
        final = lote.pasos[-1][0] if lote.pasos else "PLANIFICADA"
        if lote.periodo < "2026-11":
            assert final == "CERRADA" and lote.entrega == lote.pasos[-1][1]
            assert lote.entrega.strftime("%Y-%m") == lote.periodo
        else:
            assert final != "CERRADA" and lote.entrega is None
    en_curso = [lote for lote in p.lotes if lote.periodo == "2026-11"]
    assert len(en_curso) >= 2 and any(lote.pasos for lote in en_curso)


def test_workshop_lots_have_asked_and_paid_prices_but_house_lots_have_none():
    for lote in plan().lotes:
        for r in lote.renglones:
            if lote.donde == "INTERNA":
                assert r.cotizado is None and r.pagado is None
            else:
                assert r.cotizado > 0
                if lote.pasos and lote.pasos[-1][0] == "CERRADA":
                    assert 0 < r.pagado < r.cotizado
                else:
                    assert r.pagado is None


def test_fixed_costs_cover_factory_and_store_with_the_people_of_the_seed():
    gastos = plan().gastos
    for mes in plan().meses:
        del_mes = [g for g in gastos if g.periodo == mes]
        assert {g.lado for g in del_mes} == {"FABRICA", "TIENDA"}
        assert {g.categoria for g in del_mes} >= {"SUELDOS", "ALQUILER", "SERVICIOS", "OTROS"}
        sueldos = {g.persona for g in del_mes if g.categoria == "SUELDOS"}
        assert sueldos == {"PER-0001", "PER-0002", "PER-0003", "PER-0007", "PER-0004"}  # first seller only
    assert all(g.monto is None or g.monto > 0 for g in gastos)


def test_one_past_correction_and_two_pending_amounts_in_the_last_month():
    p = plan()
    assert len(p.correcciones) == 1
    correccion = p.correcciones[0]
    assert correccion.periodo < "2026-11"
    original = next(g for g in p.gastos if g.clave == correccion.clave_gasto)
    assert original.categoria == "SUELDOS" and correccion.monto != original.monto
    pendientes = [g for g in p.gastos if g.monto is None]
    assert len(pendientes) == 2 and {g.periodo for g in pendientes} == {"2026-11"}


def test_the_shared_months_of_two_windows_plan_the_same_rows():
    a = {f.clave: f for f in plan("2026-11").filas() if getattr(f, "periodo", None) in {"2026-09", "2026-10"}
         and type(f).__name__ in {"LotePlan", "DolarPlan"}}
    b = {f.clave: f for f in plan("2026-12", hoy=date(2026, 12, 10)).filas()
         if getattr(f, "periodo", None) in {"2026-09", "2026-10"} and type(f).__name__ in {"LotePlan", "DolarPlan"}}
    assert a and a == b


def test_without_workshops_or_people_the_plan_still_builds_without_inventing_them():
    p = plan(personas=[], talleres=[])
    assert all(lote.donde == "INTERNA" for lote in p.lotes)
    assert all(g.persona is None for g in p.gastos) and p.correcciones == []
    assert Counter(g.categoria for g in p.gastos)["SUELDOS"] == 0
