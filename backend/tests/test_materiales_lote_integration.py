"""Materials grid batch against disposable PostgreSQL (skipped without TEST_DATABASE_URL)."""

from datetime import date
from decimal import Decimal as D

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend import materiales, servicios
from backend.models import Material, PrecioMaterial

HOY = date(2026, 11, 13)
CUERO = "MAT-CU01"  # seed: 24 USD / m2 since 2026-09-01, no supplier
LAGARTO = "MAT-CU03"  # seed: not quotable (price per cm)


@pytest.fixture
def session(local_postgres):
    conexion = local_postgres.connect()
    externa = conexion.begin()
    sesion = Session(bind=conexion, join_transaction_mode="create_savepoint")
    yield sesion
    sesion.close()
    externa.rollback()
    conexion.close()


def _precios(session, codigo):
    return list(session.scalars(
        select(PrecioMaterial).join(Material, Material.id == PrecioMaterial.material_id)
        .where(Material.codigo == codigo).order_by(PrecioMaterial.vigente_desde, PrecioMaterial.id)))


def _lote(session, cambios=(), nuevos=()):
    return materiales.guardar_en_lote(session, list(cambios), list(nuevos), hoy=HOY)


def test_a_price_change_adds_a_dated_row_and_keeps_the_old_one(session):
    antes = _precios(session, CUERO)
    salida = _lote(session, [{"codigo": CUERO, "precio": D("26"), "moneda": "USD", "proveedor": "Rouez"}])
    despues = _precios(session, CUERO)
    assert len(despues) == len(antes) + 1 and despues[:len(antes)] == antes  # nothing was updated
    nuevo = despues[-1]
    assert (nuevo.precio, nuevo.moneda, nuevo.proveedor, nuevo.vigente_desde, nuevo.color_id) == (D("26"), "USD", "Rouez", HOY, None)
    assert nuevo.unidad_del_precio == "m2" and nuevo.nota_fuente  # the unit is the consumption unit; the origin is noted
    assert [p["codigo"] for p in salida["precios"]] == [nuevo.codigo]
    assert salida["precios"][0]["vigente"] is True and salida["precios"][0]["variacion_pct"] == D("8.33")


def test_a_change_that_repeats_the_current_price_adds_nothing(session):
    antes = len(_precios(session, CUERO))
    salida = _lote(session, [{"codigo": CUERO, "precio": D("24.0000"), "moneda": "USD"}])
    assert len(_precios(session, CUERO)) == antes and salida["precios"] == []


def test_only_the_supplier_changed_keeps_price_and_currency_of_the_current_one(session):
    _lote(session, [{"codigo": CUERO, "proveedor": "Acropol"}])
    nuevo = _precios(session, CUERO)[-1]
    assert (nuevo.precio, nuevo.moneda, nuevo.proveedor) == (D("24"), "USD", "Acropol")


def test_an_empty_supplier_clears_it(session):
    _lote(session, [{"codigo": CUERO, "precio": D("25"), "proveedor": "Rouez"}])
    session.expire_all()
    # same-day second price is a conflict, so clear it on a later day
    materiales.guardar_en_lote(session, [{"codigo": CUERO, "precio": D("26"), "proveedor": ""}], [], hoy=date(2026, 11, 14))
    assert _precios(session, CUERO)[-1].proveedor is None


def test_a_second_price_for_the_same_day_is_a_conflict_and_saves_nothing(session):
    _lote(session, [{"codigo": CUERO, "precio": D("26")}])
    antes = len(_precios(session, CUERO))
    with pytest.raises(servicios.Conflicto, match=CUERO):
        _lote(session, [{"codigo": CUERO, "precio": D("27")}],
              [{"nombre": "Cuero del conflicto", "etapa": "CUERO", "unidad_de_consumo": "m2"}])
    assert len(_precios(session, CUERO)) == antes
    assert session.scalar(select(Material.id).where(Material.nombre == "Cuero del conflicto")) is None


def test_a_color_price_is_never_touched_and_the_new_price_is_for_all_colors(session):
    servicios.crear_color(session, nombre="Negro grilla", nota=None)
    servicios.crear_precio(
        session, material=CUERO, color="Negro grilla", proveedor=None, precio=D("30"), moneda="USD", unidad_del_precio="m2",
        iva_incluido=False, vigente_desde=date(2026, 10, 1))
    _lote(session, [{"codigo": CUERO, "precio": D("26")}])
    precios = _precios(session, CUERO)
    assert [p.precio for p in precios if p.color_id is not None] == [D("30")]
    assert precios[-1].color_id is None and precios[-1].precio == D("26")


def test_a_blocked_material_cannot_get_a_price(session):
    antes = len(_precios(session, LAGARTO))
    with pytest.raises(servicios.DatosInvalidos, match=LAGARTO):
        _lote(session, [{"codigo": LAGARTO, "precio": D("26"), "moneda": "USD"}])
    assert len(_precios(session, LAGARTO)) == antes


def test_a_price_needs_a_currency_when_the_material_has_no_price_yet(session):
    nuevo = _lote(session, nuevos=[{"nombre": "Hilo grilla", "etapa": "HILO_CEMENTO", "unidad_de_consumo": "juego"}])
    codigo = nuevo["materiales_nuevos"][0]
    with pytest.raises(servicios.DatosInvalidos, match="moneda"):
        _lote(session, [{"codigo": codigo, "precio": D("100")}])
    assert _precios(session, codigo) == []


def test_unknown_and_repeated_codes_are_rejected(session):
    with pytest.raises(servicios.NoEncontrado):
        _lote(session, [{"codigo": "MAT-9999", "precio": D("1"), "moneda": "ARS"}])
    with pytest.raises(servicios.DatosInvalidos, match="repetido"):
        _lote(session, [{"codigo": CUERO, "precio": D("26")}, {"codigo": CUERO, "precio": D("27")}])


def test_an_empty_batch_is_rejected(session):
    with pytest.raises(servicios.DatosInvalidos):
        _lote(session)


def test_a_new_material_gets_a_sequential_mat_code_and_its_first_price(session):
    salida = _lote(session, nuevos=[
        {"nombre": "  Cierre 30 cm  ", "etapa": "HERRAJES", "unidad_de_consumo": "unidad", "precio": D("1500"),
         "moneda": "ARS", "proveedor": "Mercería Sur"},
        {"nombre": "Cartón fibra", "etapa": "FLEX", "unidad_de_consumo": "m2"}])
    assert salida["materiales_nuevos"] == ["MAT-0001", "MAT-0002"]
    cierre = session.scalar(select(Material).where(Material.codigo == "MAT-0001"))
    assert (cierre.nombre, cierre.unidad_de_consumo, cierre.cotizable, cierre.controla_inventario) == ("Cierre 30 cm", "unidad", True, False)
    [precio] = _precios(session, "MAT-0001")
    assert (precio.precio, precio.moneda, precio.proveedor, precio.unidad_del_precio, precio.vigente_desde) == (
        D("1500"), "ARS", "Mercería Sur", "unidad", HOY)
    assert _precios(session, "MAT-0002") == []  # a material without a price is allowed
    siguiente = _lote(session, nuevos=[{"nombre": "Tercero", "etapa": "FLEX", "unidad_de_consumo": "m2"}])
    assert siguiente["materiales_nuevos"] == ["MAT-0003"]
    assert {m["codigo"] for m in servicios.listar_materiales(session)} >= {"MAT-CU01", "MAT-0001", "MAT-0003"}


@pytest.mark.parametrize("nuevo, mensaje", [
    ({"nombre": "   ", "etapa": "CUERO", "unidad_de_consumo": "m2"}, "nombre"),
    ({"nombre": "Algo", "etapa": "NOEXISTE", "unidad_de_consumo": "m2"}, "etapa"),
    ({"nombre": "Algo", "etapa": "CORTE", "unidad_de_consumo": "unidad"}, "etapa"),  # a task, not a material
    ({"nombre": "Algo", "etapa": "CUERO", "unidad_de_consumo": "m2", "precio": D("5")}, "moneda"),
])
def test_an_invalid_new_material_saves_nothing(session, nuevo, mensaje):
    antes = len(servicios.listar_materiales(session))
    with pytest.raises(servicios.DatosInvalidos, match=mensaje):
        _lote(session, nuevos=[nuevo])
    assert len(servicios.listar_materiales(session)) == antes


def test_a_taken_name_is_a_conflict_whatever_the_case(session):
    with pytest.raises(servicios.Conflicto):
        _lote(session, nuevos=[{"nombre": "carpincho", "etapa": "CUERO", "unidad_de_consumo": "m2"}])
    with pytest.raises(servicios.Conflicto):  # twice in the same batch
        _lote(session, nuevos=[{"nombre": "Repetido", "etapa": "FLEX", "unidad_de_consumo": "m2"},
                               {"nombre": "REPETIDO", "etapa": "FLEX", "unidad_de_consumo": "m2"}])
