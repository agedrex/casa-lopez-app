"""Mercadería grid batch against disposable PostgreSQL (skipped without TEST_DATABASE_URL)."""

from decimal import Decimal as D

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend import reventa, servicios
from backend.models import Categoria, CompraReventa


@pytest.fixture
def session(local_postgres):
    conexion = local_postgres.connect()
    externa = conexion.begin()
    sesion = Session(bind=conexion, join_transaction_mode="create_savepoint")
    yield sesion
    sesion.close()
    externa.rollback()
    conexion.close()


def _dos_productos(session):
    nuevos = [{"nombre": "Billetera X", "costo": D("600"), "precio_venta": D("1000"), "unidades": D("10")},
              {"nombre": "Cinto X"}]
    return [fila["codigo"] for fila in reventa.guardar_en_lote(session, [], nuevos)][-2:]


@pytest.mark.parametrize("extra", ["nada", "categoria", "costo"])
def test_renaming_to_a_taken_name_is_a_conflict_whatever_else_changes(session, extra):
    _, cinto = _dos_productos(session)
    cambio = {"codigo": cinto, "nombre": "billetera x"}
    if extra == "categoria":
        cambio["categoria"] = session.scalars(select(Categoria.nombre)).first()
    if extra == "costo":
        cambio["costo"] = D("350")
    with pytest.raises(servicios.Conflicto):
        reventa.guardar_en_lote(session, [cambio], [])


def test_a_price_change_adds_a_history_row_without_units_and_a_no_op_adds_none(session):
    billetera, _ = _dos_productos(session)
    filas = lambda: session.scalars(select(CompraReventa)).all()
    antes = len(filas())
    reventa.guardar_en_lote(session, [{"codigo": billetera, "costo": D("600"), "precio_venta": D("1000")}], [])
    assert len(filas()) == antes
    productos = reventa.guardar_en_lote(session, [{"codigo": billetera, "precio_venta": D("1200")}], [])
    nuevo = max(filas(), key=lambda fila: fila.id)
    assert nuevo.unidades is None and nuevo.costo_unitario_ars == D("600")
    producto = next(p for p in productos if p["codigo"] == billetera)
    assert producto["precio_venta_unitario_ars"] == D("1200") and producto["compras"] == 1


def test_a_failing_row_rolls_back_the_whole_batch(session):
    billetera, _ = _dos_productos(session)
    antes = len(session.scalars(select(CompraReventa)).all())
    with pytest.raises(servicios.NoEncontrado):
        reventa.guardar_en_lote(session, [{"codigo": billetera, "costo": D("700")}, {"codigo": "MER-9999"}], [])
    assert len(session.scalars(select(CompraReventa)).all()) == antes


def test_a_price_change_wins_even_when_the_latest_purchase_is_dated_in_the_future(session):
    from datetime import date, timedelta
    billetera, _ = _dos_productos(session)
    futura = date.today() + timedelta(days=30)
    reventa.registrar_compra(session, billetera, unidades=D("5"), costo_unitario_ars=D("650"), fecha=futura)
    productos = reventa.guardar_en_lote(session, [{"codigo": billetera, "costo": D("900")}], [])
    producto = next(p for p in productos if p["codigo"] == billetera)
    assert producto["costo_unitario_ars"] == D("900")
