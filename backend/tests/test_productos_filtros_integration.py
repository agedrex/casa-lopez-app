"""Leather, color and state filters of the product list against disposable PostgreSQL; skipped without TEST_DATABASE_URL."""

import pytest
from sqlalchemy import update
from sqlalchemy.orm import Session

from backend import servicios
from backend.models import Color, Producto


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


def _producto(session, *, cuero="MAT-CU01", color=None, estado=None, nota=None, nombre_propio=None):
    codigo = servicios.crear_producto(
        session, modelo="MOD-0001", cuero=cuero, color=color, quien_lo_confecciona="INTERNA", fecha_de_alta=None,
        nombre_propio=nombre_propio, es_kit=False, nota=nota,
    )["codigo"]
    if estado:
        session.execute(update(Producto).where(Producto.codigo == codigo).values(estado_del_ciclo=estado))
        session.commit()
    return codigo


def _codigos(session, **filtros):
    """Codes from the list and from the count, which must agree."""
    codigos = [f["codigo"] for f in servicios.listar_productos(session, limit=500, **filtros)]
    assert servicios.contar_productos(session, **filtros) == len(codigos)
    return codigos


@pytest.fixture
def catalogo(session):
    session.add(Color(codigo="COL-TEST", nombre="Negro de prueba"))
    session.commit()
    completo = _producto(session, color="Negro de prueba", estado="COTIZADO", nombre_propio="Completo")
    sin_cuero = _producto(session, cuero=None, color="Negro de prueba", nombre_propio="SinCuero")
    sin_color = _producto(session, estado="COTIZADO", nombre_propio="SinColor")
    sin_nada = _producto(session, cuero=None, estado="EN_PRODUCCION", nombre_propio="SinNada")
    return {"completo": completo, "sin_cuero": sin_cuero, "sin_color": sin_color, "sin_nada": sin_nada}


def test_the_leather_filter_lists_and_counts_only_products_without_leather(session, catalogo):
    assert _codigos(session, sin_cuero=True) == [catalogo["sin_cuero"], catalogo["sin_nada"]]


def test_the_color_filter_lists_and_counts_only_products_without_color(session, catalogo):
    assert _codigos(session, sin_color=True) == [catalogo["sin_color"], catalogo["sin_nada"]]


def test_the_state_filter_lists_and_counts_only_that_state(session, catalogo):
    assert _codigos(session, estado="COTIZADO") == [catalogo["completo"], catalogo["sin_color"]]
    assert _codigos(session, estado="EN_PRODUCCION") == [catalogo["sin_nada"]]
    assert _codigos(session, estado="EN_DEFINICION") == [catalogo["sin_cuero"]]
    assert _codigos(session, estado="PRODUCIDO") == []


def test_the_filters_are_additive(session, catalogo):
    assert _codigos(session, sin_cuero=True, sin_color=True) == [catalogo["sin_nada"]]
    assert _codigos(session, sin_color=True, estado="COTIZADO") == [catalogo["sin_color"]]
    assert _codigos(session, sin_cuero=True, estado="COTIZADO") == []
    assert _codigos(session, q="sincolor", sin_color=True) == [catalogo["sin_color"]]
    assert _codigos(session, q="sincuero", sin_color=True) == []


def test_the_new_filters_combine_with_the_review_mark(session, catalogo):
    marcado = _producto(session, cuero=None, nota="IMPORTADO-EXCEL fila 7 | REVISAR: sin tipo de cuero")
    assert _codigos(session, sin_cuero=True, revisar=True) == [marcado]
    assert _codigos(session, estado="EN_DEFINICION", revisar=True) == [marcado]
    assert _codigos(session, estado="COTIZADO", revisar=True) == []


def test_without_the_new_filters_every_product_is_listed(session, catalogo):
    todos = _codigos(session)
    assert set(catalogo.values()) <= set(todos)
    assert _codigos(session, sin_cuero=False, sin_color=False, estado=None) == todos


def test_the_pages_of_a_filtered_list_add_up_to_the_count(session, catalogo):
    primera = servicios.listar_productos(session, limit=1, offset=0, sin_cuero=True)
    segunda = servicios.listar_productos(session, limit=1, offset=1, sin_cuero=True)
    assert [f["codigo"] for f in primera + segunda] == [catalogo["sin_cuero"], catalogo["sin_nada"]]
    assert servicios.contar_productos(session, sin_cuero=True) == 2
