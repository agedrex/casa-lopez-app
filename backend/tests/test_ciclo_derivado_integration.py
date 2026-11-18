"""S8 (flujo-modelos-lotes-precio): the lifecycle label derived from price and lots, on list, filter, count and ficha.

Against disposable PostgreSQL; skipped without TEST_DATABASE_URL."""

from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend import servicios
from backend.models import OrdenFabricacion, OrdenItem, PrecioVenta, Producto


@pytest.fixture
def session(local_postgres):
    connection = local_postgres.connect()
    outer = connection.begin()
    session = Session(bind=connection, join_transaction_mode="create_savepoint")
    try:
        yield session
    finally:
        session.close()
        outer.rollback()
        connection.close()


_modelos = iter(range(10, 300))


def _producto(session, nombre):
    """Each product gets its own model: the same model + leather + color cannot be created twice."""
    return servicios.crear_producto(
        session, modelo=f"MOD-{next(_modelos):04d}", cuero="MAT-CU01", color=None, quien_lo_confecciona="INTERNA", fecha_de_alta=None,
        nombre_propio=nombre, es_kit=False, nota=None,
    )["codigo"]


def _id(session, codigo):
    return session.scalar(select(Producto.id).where(Producto.codigo == codigo))


def _precio(session, codigo):
    session.add(PrecioVenta(producto_id=_id(session, codigo), precio_ars=Decimal("1000"), vigente_desde=date(2026, 11, 1)))
    session.flush()


_n = iter(range(1, 10_000))


def _lote(session, codigo, estado, *, cantidad="2", nota=None):
    n = next(_n)
    lote = OrdenFabricacion(codigo=f"LOT-S8{n:04d}", donde_se_hace="INTERNA", estado=estado)
    session.add(lote)
    session.flush()
    session.add(OrdenItem(codigo=f"LIT-S8{n:04d}", orden_fabricacion_id=lote.id, producto_id=_id(session, codigo),
                          cantidad=Decimal(cantidad), nota=nota))
    session.flush()


def _estado_en_lista(session, codigo, **filtros):
    return {f["codigo"]: f["estado_del_ciclo"] for f in servicios.listar_productos(session, limit=500, **filtros)}[codigo]


def _codigos(session, estado):
    codigos = [f["codigo"] for f in servicios.listar_productos(session, limit=500, estado=estado)]
    assert servicios.contar_productos(session, estado=estado) == len(codigos)
    return set(codigos)


def _todos_coinciden(session, codigo, esperado):
    """List, ficha and filter must all say the same."""
    assert _estado_en_lista(session, codigo) == esperado
    assert servicios.ficha_producto(session, codigo)["estado_del_ciclo"] == esperado
    for estado in ("EN_DEFINICION", "COTIZADO", "EN_PRODUCCION", "PRODUCIDO"):
        assert (codigo in _codigos(session, estado)) == (estado == esperado), estado


def test_a_new_product_without_facts_is_in_definition(session):
    codigo = _producto(session, "S8 solo")
    _todos_coinciden(session, codigo, "EN_DEFINICION")


def test_a_saved_sale_price_makes_it_quoted(session):
    codigo = _producto(session, "S8 cotizado")
    _precio(session, codigo)
    _todos_coinciden(session, codigo, "COTIZADO")


@pytest.mark.parametrize("estado", ["PLANIFICADA", "EN_CORTE", "CORTADA", "EN_CONFECCION"])
def test_a_line_in_an_open_lot_makes_it_in_production(session, estado):
    codigo = _producto(session, f"S8 abierto {estado}")
    _precio(session, codigo)
    _lote(session, codigo, estado)
    _todos_coinciden(session, codigo, "EN_PRODUCCION")


@pytest.mark.parametrize("estado", ["LISTA", "CERRADA"])
def test_a_line_in_a_finished_lot_makes_it_produced(session, estado):
    codigo = _producto(session, f"S8 terminado {estado}")
    _lote(session, codigo, estado)
    _todos_coinciden(session, codigo, "PRODUCIDO")


def test_a_finished_lot_wins_over_an_open_one(session):
    codigo = _producto(session, "S8 ambos")
    _lote(session, codigo, "EN_CORTE")
    _lote(session, codigo, "CERRADA")
    _todos_coinciden(session, codigo, "PRODUCIDO")


def test_a_removed_line_does_not_count(session):
    codigo = _producto(session, "S8 quitado")
    _lote(session, codigo, "CERRADA", cantidad="0", nota="[QUITADO] por error")
    _todos_coinciden(session, codigo, "EN_DEFINICION")


def test_the_stored_value_wins_when_it_is_higher(session):
    codigo = _producto(session, "S8 guardado")
    session.get(Producto, _id(session, codigo)).estado_del_ciclo = "PRODUCIDO"
    session.flush()
    _precio(session, codigo)
    _todos_coinciden(session, codigo, "PRODUCIDO")


def test_reading_never_writes_the_stored_column(session):
    codigo = _producto(session, "S8 sin escribir")
    _precio(session, codigo)
    _lote(session, codigo, "CERRADA")
    _todos_coinciden(session, codigo, "PRODUCIDO")
    session.expire_all()
    assert session.get(Producto, _id(session, codigo)).estado_del_ciclo == "EN_DEFINICION"


def test_the_filter_and_the_count_agree_across_pages(session):
    a, b = _producto(session, "S8 pag a"), _producto(session, "S8 pag b")
    _lote(session, a, "LISTA")
    _lote(session, b, "CERRADA")
    pagina = servicios.listar_productos(session, limit=1, offset=1, estado="PRODUCIDO")
    assert len(pagina) == 1 and servicios.contar_productos(session, estado="PRODUCIDO") == 2


def test_the_missing_closing_date_control_reads_the_stored_state_not_the_derived_one(session):
    """"Falta la fecha de cierre" is a data-quality finding about the STORED PRODUCIDO; a derived one must not trigger it."""
    derivado = _producto(session, "S8 aviso derivado")
    _lote(session, derivado, "CERRADA")
    guardado = _producto(session, "S8 aviso guardado")
    session.get(Producto, _id(session, guardado)).estado_del_ciclo = "PRODUCIDO"
    session.flush()
    por_codigo = {d.codigo: d for d in servicios.cargar_productos(session, [derivado, guardado])}
    assert por_codigo[derivado].estado_del_ciclo == "PRODUCIDO"
    assert "Falta la fecha de cierre" not in servicios.controles_de_producto(por_codigo[derivado], False)
    assert "Falta la fecha de cierre" in servicios.controles_de_producto(por_codigo[guardado], False)
