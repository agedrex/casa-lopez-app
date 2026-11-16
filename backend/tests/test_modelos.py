"""The model list carries the state of each model's newest consumption sheet (`hoja_codigo` / `hoja_estado`).

Integration tests: they need TEST_DATABASE_URL (disposable local PostgreSQL) and are skipped without it.
"""

import pytest

from backend.auth import Usuario, get_verifier
from backend.main import app
from backend.models import FormularioConsumo, Modelo
from sqlalchemy import select

from test_costos_fijos_correccion_integration import api  # noqa: F401  (fixture; its client also carries `.session`)


def como(role, usuario="admin-1"):
    app.dependency_overrides[get_verifier] = lambda: (lambda request: Usuario(id=usuario, role=role))


def modelo_de_lista(api, codigo):
    como("admin")
    return next(m for m in api.get("/modelos", params={"limit": 1000}).json() if m["codigo"] == codigo)


def test_pg_a_model_without_sheet_has_null_hoja_fields(api):
    primero = api.get("/modelos", params={"limit": 1}).json()[0]
    assert primero["hoja_codigo"] is None and primero["hoja_estado"] is None


def test_pg_a_new_model_lists_its_sent_sheet(api):
    como("admin")
    datos = api.post("/productos/nuevo", json={"nombre": "Zz Modelo con hoja", "categoria": "Billeteras"}).json()
    fila = modelo_de_lista(api, datos["modelo"])
    assert (fila["hoja_codigo"], fila["hoja_estado"]) == (datos["formulario"], "ENVIADO")


def test_pg_the_newest_sheet_wins_and_other_models_keep_their_own(api):
    como("admin")
    uno = api.post("/productos/nuevo", json={"nombre": "Zz Modelo uno", "categoria": "Billeteras"}).json()
    otro = api.post("/productos/nuevo", json={"nombre": "Zz Modelo otro", "categoria": "Billeteras"}).json()
    modelo_id = api.session.scalar(select(Modelo.id).where(Modelo.codigo == uno["modelo"]))
    nueva = FormularioConsumo(
        codigo="FCO-9001", articulo="ZZ MODELO UNO", estado="COMPLETADO", creado_por="admin-1", modelo_id=modelo_id)
    api.session.add(nueva)
    api.session.flush()
    assert (modelo_de_lista(api, uno["modelo"])["hoja_codigo"], modelo_de_lista(api, uno["modelo"])["hoja_estado"]) == (
        "FCO-9001", "COMPLETADO")
    assert modelo_de_lista(api, otro["modelo"])["hoja_codigo"] == otro["formulario"]


def test_pg_the_detail_may_leave_the_hoja_fields_empty(api):
    como("admin")
    datos = api.post("/productos/nuevo", json={"nombre": "Zz Modelo detalle", "categoria": "Billeteras"}).json()
    detalle = api.get(f"/modelos/{datos['modelo']}").json()
    assert detalle.get("hoja_codigo") is None and detalle.get("hoja_estado") is None


@pytest.mark.parametrize("role", ["gerente", "taller"])
def test_pg_every_role_that_reads_the_list_gets_the_fields(api, role):
    como("admin")
    datos = api.post("/productos/nuevo", json={"nombre": f"Zz Modelo {role}", "categoria": "Billeteras"}).json()
    como(role)
    fila = next(m for m in api.get("/modelos", params={"limit": 1000}).json() if m["codigo"] == datos["modelo"])
    assert fila["hoja_codigo"] == datos["formulario"]
