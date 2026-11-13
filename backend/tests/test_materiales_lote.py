"""Materials grid batch: the HTTP contract without a database. The rules are in test_materiales_lote_integration.py."""

from decimal import Decimal as D
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from backend import materiales
from backend.auth import Usuario, get_verifier
from backend.database import get_session
from backend.main import app

SIN_PERMISO = {"detail": "No tenés permiso para esta acción."}
PRECIO = {
    "codigo": "PRE-0010", "material": "MAT-CU01", "color": None, "proveedor": "Rouez", "precio": D("26"), "moneda": "USD",
    "unidad_del_precio": "m2", "iva_incluido": False, "vigente_desde": "2026-11-13", "nota_fuente": "x", "vigente": True,
    "variacion_pct": D("8.33"), "salto_grande": False,
}


@pytest.fixture(autouse=True)
def limpiar(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    yield
    app.dependency_overrides.clear()


def cliente(role, monkeypatch, salida=None):
    session = MagicMock()
    llamadas = []
    app.dependency_overrides[get_session] = lambda: session
    app.dependency_overrides[get_verifier] = lambda: (lambda request: Usuario(id="u1", role=role))
    monkeypatch.setattr(materiales, "guardar_en_lote", lambda s, cambios, nuevos: (
        llamadas.append((cambios, nuevos)) or salida or {"precios": [], "materiales_nuevos": []}))
    return TestClient(app), llamadas


def test_the_admin_saves_changes_and_new_materials_and_gets_the_new_prices(monkeypatch):
    c, llamadas = cliente("admin", monkeypatch, {"precios": [PRECIO], "materiales_nuevos": ["MAT-0001"]})
    respuesta = c.post("/materiales/lote", json={
        "cambios": [{"codigo": "MAT-CU01", "precio": "26", "moneda": "USD", "proveedor": "Rouez"}],
        "nuevos": [{"nombre": "Cierre", "etapa": "HERRAJES", "unidad_de_consumo": "unidad", "precio": "1500.50", "moneda": "ARS"}]})
    assert respuesta.status_code == 200
    assert respuesta.json()["materiales_nuevos"] == ["MAT-0001"] and respuesta.json()["precios"][0]["codigo"] == "PRE-0010"
    cambios, nuevos = llamadas[0]
    assert cambios == [{"codigo": "MAT-CU01", "precio": D("26"), "moneda": "USD", "proveedor": "Rouez"}]  # only what was sent
    assert nuevos[0]["precio"] == D("1500.50") and nuevos[0]["proveedor"] is None


@pytest.mark.parametrize("role", ["gerente", "taller", "otro", None])
def test_only_the_admin_saves_the_grid(monkeypatch, role):
    c, llamadas = cliente(role, monkeypatch)
    respuesta = c.post("/materiales/lote", json={"cambios": [{"codigo": "MAT-CU01", "precio": "26", "moneda": "USD"}]})
    assert respuesta.status_code == 403 and respuesta.json() == SIN_PERMISO and llamadas == []


@pytest.mark.parametrize("cuerpo", [
    {"cambios": [{"codigo": "MAT-CU01", "precio": "0"}]},  # a price is above zero
    {"cambios": [{"codigo": "MAT-CU01", "precio": "-5"}]},
    {"cambios": [{"codigo": "MAT-CU01", "moneda": "EUR"}]},
    {"cambios": [{"codigo": "MAT-CU01", "precio": "26", "vigente_desde": "2026-01-01"}]},  # the date is today's, not the client's
    {"cambios": [{"codigo": "MAT-CU01", "cotizable": False}]},  # nothing else of the material is editable here
    {"nuevos": [{"nombre": "", "etapa": "CUERO", "unidad_de_consumo": "m2"}]},
    {"nuevos": [{"nombre": "X", "etapa": "CUERO", "unidad_de_consumo": "litros"}]},
    {"nuevos": [{"nombre": "X", "etapa": "CUERO", "unidad_de_consumo": "m2", "codigo": "MAT-0099"}]},  # the code is ours
])
def test_a_body_with_unknown_or_invalid_fields_is_rejected_before_the_service(monkeypatch, cuerpo):
    c, llamadas = cliente("admin", monkeypatch)
    assert c.post("/materiales/lote", json=cuerpo).status_code == 422 and llamadas == []
