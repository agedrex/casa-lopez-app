"""S5 (odd/tasks/mejoras-qa-staging.md): the same model + leather + colour cannot be created twice.

Integration tests against disposable PostgreSQL (skipped without TEST_DATABASE_URL); each one runs inside a transaction that is
rolled back. A kit (no model) is outside the rule.
"""

from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend import servicios
from backend.auth import Usuario, get_verifier
from backend.database import get_session
from backend.main import app
from backend.models import Producto


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


@pytest.fixture
def api(session, monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    app.dependency_overrides[get_session] = lambda: session
    app.dependency_overrides[get_verifier] = lambda: (lambda request: Usuario(id="admin-1", role="admin"))
    try:
        with TestClient(app) as client:
            yield client
    finally:
        app.dependency_overrides.clear()


def crear(session, *, modelo="MOD-0001", cuero="MAT-CU01", color=None, es_kit=False, nombre_propio=None):
    return servicios.crear_producto(
        session, modelo=modelo, cuero=cuero, color=color, quien_lo_confecciona=None, fecha_de_alta=date(2026, 11, 17),
        nombre_propio=nombre_propio, es_kit=es_kit)


def cuantos(session):
    return session.scalar(select(func.count()).select_from(Producto))


def test_the_same_model_leather_and_colour_is_a_conflict_naming_the_existing_product(session):
    primero = crear(session)
    antes = cuantos(session)
    with pytest.raises(servicios.Conflicto) as error:
        crear(session)
    assert str(error.value) == (
        f"Ya existe el producto {primero['codigo']} con ese modelo, cuero y color: abrilo en lugar de crear otro.")
    assert cuantos(session) == antes  # nothing was created


def test_the_api_answers_409_with_the_same_message(api, session):
    cuerpo = {"modelo": "MOD-0001", "cuero": "MAT-CU01"}
    creado = api.post("/productos", json=cuerpo)
    assert creado.status_code == 201, creado.text
    repetido = api.post("/productos", json=cuerpo)
    assert repetido.status_code == 409
    assert repetido.json() == {
        "detail": f"Ya existe el producto {creado.json()['codigo']} con ese modelo, cuero y color: abrilo en lugar de crear otro."}


def test_another_colour_another_leather_or_another_model_is_not_a_duplicate(session):
    servicios.crear_color(session, nombre="Zz Verde", nota=None)
    base = crear(session)
    otros = [crear(session, color="Zz Verde"), crear(session, cuero="MAT-CU02"), crear(session, modelo="MOD-0002")]
    assert len({base["codigo"], *(p["codigo"] for p in otros)}) == 4


def test_a_product_without_leather_or_colour_counts_as_the_same_when_repeated(session):
    primero = crear(session, cuero=None)
    with pytest.raises(servicios.Conflicto, match=primero["codigo"]):
        crear(session, cuero=None)
    crear(session)  # with leather it is another product


def test_kits_without_model_are_outside_the_rule(session):
    uno = crear(session, modelo=None, cuero=None, es_kit=True, nombre_propio="Kit A")
    dos = crear(session, modelo=None, cuero=None, es_kit=True, nombre_propio="Kit A")
    assert uno["codigo"] != dos["codigo"]
