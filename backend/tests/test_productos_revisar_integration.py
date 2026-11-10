"""REVISAR filter against disposable PostgreSQL; skipped without TEST_DATABASE_URL."""

import pytest
from sqlalchemy.orm import Session

from backend import servicios

NOTA_REVISAR = "IMPORTADO-EXCEL fila 7 | REVISAR: sin tipo de cuero | B=Fabián"
NOTA_SANA = "IMPORTADO-EXCEL fila 8 | B=Lucio | E=2026-08-25"


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


def _producto(session, nota, **cambios):
    datos = {"modelo": "MOD-0001", "cuero": "MAT-CU01", "color": None, "quien_lo_confecciona": "INTERNA",
             "fecha_de_alta": None, "nombre_propio": None, "es_kit": False, "nota": nota, **cambios}
    return servicios.crear_producto(session, **datos)["codigo"]


def test_the_review_filter_lists_and_counts_only_marked_products(session):
    marcado = _producto(session, NOTA_REVISAR)
    sano = _producto(session, NOTA_SANA)
    sin_nota = _producto(session, None)
    # A comment that only mentions the word without the colon is not a mark.
    palabra = _producto(session, "IMPORTADO-EXCEL fila 9 | Comentario AE1: para revisar el precio")

    con_marca = servicios.listar_productos(session, revisar=True)
    assert [f["codigo"] for f in con_marca] == [marcado]
    assert (con_marca[0]["revisar"], con_marca[0]["motivos_revisar"], con_marca[0]["modelo"]) == (
        True, ["sin tipo de cuero"], "MOD-0001")
    assert servicios.contar_productos(session, revisar=True) == 1

    todos = servicios.listar_productos(session)
    assert [f["codigo"] for f in todos if f["codigo"] in {marcado, sano, sin_nota, palabra}] == [marcado, sano, sin_nota, palabra]
    banderas = {f["codigo"]: f["revisar"] for f in todos}
    assert [banderas[c] for c in (marcado, sano, sin_nota, palabra)] == [True, False, False, False]
    assert servicios.contar_productos(session) == len(todos)


def test_without_the_review_filter_the_search_and_the_count_behave_as_before(session):
    marcado = _producto(session, NOTA_REVISAR, nombre_propio="Cartera Roja")
    _producto(session, NOTA_SANA, nombre_propio="Cartera Azul")
    assert servicios.contar_productos(session, q="cartera") == 2
    assert [f["codigo"] for f in servicios.listar_productos(session, q="cartera", revisar=True)] == [marcado]
    assert servicios.contar_productos(session, q="cartera", revisar=True) == 1
    assert servicios.contar_productos(session, q="roja", revisar=True) == 1
    assert servicios.contar_productos(session, q="azul", revisar=True) == 0


NOTAS_QUE_NO_SON_MARCA = [
    "revisar: consultar a Gerardo", "Revisar: precio", "Comentario AE9: hay que REVISAR: el precio", "REVISAR:",
    "IMPORTADO-EXCEL fila 3 | REVISAR:  ",
]


def test_the_filter_and_the_marks_of_the_rows_agree(session):
    valida = _producto(session, "IMPORTADO-EXCEL fila 3 | REVISAR: modelo repetido")
    for nota in NOTAS_QUE_NO_SON_MARCA:
        _producto(session, nota)

    filas = servicios.listar_productos(session, revisar=True)
    assert [f["codigo"] for f in filas] == [valida]
    assert all(f["revisar"] for f in filas)
    todas = servicios.listar_productos(session)
    assert servicios.contar_productos(session, revisar=True) == len([f for f in todas if f["revisar"]]) == 1
