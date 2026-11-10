"""Product list filters `sin_cuero`, `sin_color` and `estado`: query shape and the API parameters."""

from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import aliased

from backend import servicios
from backend.auth import Usuario, get_verifier
from backend.database import get_session
from backend.main import app
from backend.models import Material, Producto

ESTADOS = ["EN_DEFINICION", "COTIZADO", "EN_PRODUCCION", "PRODUCIDO"]


@pytest.fixture(autouse=True)
def limpiar(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    yield
    app.dependency_overrides.clear()


def _cliente(role="gerente"):
    app.dependency_overrides[get_session] = lambda: MagicMock()
    app.dependency_overrides[get_verifier] = lambda: (lambda request: Usuario(id="u", role=role))
    return TestClient(app)


def _sql(**filtros):
    cuero = aliased(Material)
    consulta = servicios._filtrar_productos(select(Producto.id).select_from(Producto), cuero, **filtros)
    compilada = consulta.compile(dialect=postgresql.dialect())
    return str(compilada), compilada.params


# --- Query filter -------------------------------------------------------------------------------------------------

def test_the_leather_filter_keeps_the_products_without_a_leather():
    sql, params = _sql(q=None, categoria=None, sin_cuero=True)
    assert "producto.cuero_id IS NULL" in sql and "color_id" not in sql and "estado_del_ciclo" not in sql
    assert params == {}


def test_the_color_filter_keeps_the_products_without_a_color():
    sql, params = _sql(q=None, categoria=None, sin_color=True)
    assert "producto.color_id IS NULL" in sql and "cuero_id" not in sql and "estado_del_ciclo" not in sql
    assert params == {}


@pytest.mark.parametrize("estado", ESTADOS)
def test_the_state_filter_compares_the_lifecycle_state_with_a_bound_value(estado):
    sql, params = _sql(q=None, categoria=None, estado=estado)
    assert "producto.estado_del_ciclo =" in sql and "IS NULL" not in sql
    assert list(params.values()) == [estado]


def test_without_the_new_filters_the_query_does_not_change():
    base = _sql(q="cartera negra", categoria="Carteras", revisar=True)
    assert _sql(q="cartera negra", categoria="Carteras", revisar=True, sin_cuero=False, sin_color=False, estado=None) == base
    assert _sql(q=None, categoria=None) == _sql(q=None, categoria=None, sin_cuero=False, sin_color=False, estado=None)
    sin_filtros = _sql(q=None, categoria=None)[0]
    assert "cuero_id" not in sin_filtros and "color_id" not in sin_filtros and "estado_del_ciclo" not in sin_filtros


def test_the_new_filters_add_up_with_the_search_the_category_and_the_review_mark():
    sql, params = _sql(q="cartera", categoria="Carteras", revisar=True, sin_cuero=True, sin_color=True, estado="COTIZADO")
    for trozo in ("producto.nota ~", "producto.cuero_id IS NULL", "producto.color_id IS NULL", "producto.estado_del_ciclo ="):
        assert trozo in sql
    valores = list(params.values())
    assert "%cartera%" in valores and "Carteras" in valores and "COTIZADO" in valores and servicios.PATRON_REVISAR_SQL in valores


# --- API parameters -----------------------------------------------------------------------------------------------

def _espiar(monkeypatch):
    vistos = {"lista": [], "conteo": []}
    monkeypatch.setattr(servicios, "listar_productos", lambda session, limit, offset, q=None, categoria=None, revisar=False, **mas:
                        vistos["lista"].append(mas) or [])
    monkeypatch.setattr(servicios, "contar_productos", lambda session, q=None, categoria=None, revisar=False, **mas:
                        vistos["conteo"].append(mas) or 3)
    return vistos


def test_the_new_parameters_reach_the_list_and_the_count_the_same_way(monkeypatch):
    vistos = _espiar(monkeypatch)
    client = _cliente()
    params = {"sin_cuero": "true", "sin_color": "true", "estado": "COTIZADO"}
    assert client.get("/productos", params=params).status_code == 200
    assert client.get("/productos/conteo", params=params).json() == {"total": 3}
    esperado = {"sin_cuero": True, "sin_color": True, "estado": "COTIZADO"}
    assert vistos == {"lista": [esperado], "conteo": [esperado]}


@pytest.mark.parametrize("params, esperado", [
    ({"sin_cuero": "true"}, {"sin_cuero": True}),
    ({"sin_color": "true"}, {"sin_color": True}),
    ({"estado": "PRODUCIDO"}, {"estado": "PRODUCIDO"}),
    ({"sin_cuero": "false", "sin_color": "false"}, {}),
])
def test_each_parameter_travels_alone(monkeypatch, params, esperado):
    vistos = _espiar(monkeypatch)
    client = _cliente()
    client.get("/productos", params=params)
    client.get("/productos/conteo", params=params)
    assert vistos == {"lista": [esperado], "conteo": [esperado]}


def test_without_the_new_parameters_the_service_is_called_as_before(monkeypatch):
    vistos = _espiar(monkeypatch)
    client = _cliente()
    assert client.get("/productos").status_code == 200
    assert client.get("/productos/conteo").status_code == 200
    assert vistos == {"lista": [{}], "conteo": [{}]}


@pytest.mark.parametrize("ruta", ["/productos", "/productos/conteo"])
@pytest.mark.parametrize("params", [{"estado": "ACTIVO"}, {"estado": "cotizado"}, {"estado": ""}, {"sin_cuero": "quizás"}, {"sin_color": "2x"}])
def test_an_invalid_value_is_a_validation_error(ruta, params):
    assert _cliente().get(ruta, params=params).status_code == 422


@pytest.mark.parametrize("estado", ESTADOS)
def test_the_four_valid_states_are_accepted_by_the_list_and_the_count(monkeypatch, estado):
    _espiar(monkeypatch)
    client = _cliente()
    assert client.get("/productos", params={"estado": estado}).status_code == 200
    assert client.get("/productos/conteo", params={"estado": estado}).status_code == 200


def test_taller_keeps_reading_the_list_and_the_count_with_the_new_filters(monkeypatch):
    _espiar(monkeypatch)
    client = _cliente("taller")
    assert client.get("/productos", params={"sin_color": "true", "estado": "EN_PRODUCCION"}).status_code == 200
    assert client.get("/productos/conteo", params={"sin_cuero": "true"}).status_code == 200
