"""Ficha de producto: nombre del material (no el código), horas de confección y cambio de color. Tests con mocks (sin base).

Reglas: cada línea de la receta trae el nombre del material además de su código (el código no se quita: el motor y otros
tests lo usan); la ficha trae el nombre del cuero y del modelo y las horas de confección del modelo (informativas, nunca
entran al costo); un material sin nombre conocido muestra su código, nunca un texto inventado; cambiar el color de un
producto es solo del admin, el color tiene que existir y vaciarlo lo deja sin color.
"""

from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from backend import servicios
from backend.api import FichaOut
from backend.auth import Usuario, get_verifier
from backend.database import get_session
from backend.main import app
from backend.receta import ModeloReceta
from backend.servicios import DatosProducto, DatosInvalidos, NoEncontrado

D = Decimal


@pytest.fixture(autouse=True)
def limpiar(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    yield
    app.dependency_overrides.clear()


def _datos(**extra):
    modelo = ModeloReceta(D("0.25"), "MAT-FO01", D("0.2"), None, None, None, D("1"), D("12000"))
    base = dict(
        id=1, codigo="PRD-0001", nombre="Portafolio Estándar", categoria="Portafolios", modelo_codigo="MOD-0001",
        cuero="MAT-CU01", color=None, quien="EXTERNA", estado_del_ciclo="EN_DEFINICION", es_kit=False, nota=None,
        fecha_de_alta=None, fecha_de_recotizacion=None, fecha_de_cierre=None, modelo=modelo,
        modelo_nombre="Portafolio Simple Ch.", cuero_nombre="Estándar", horas_de_confeccion=D("2.5"),
    )
    return DatosProducto(**{**base, **extra})


NOMBRES = {"MAT-CU01": "Estándar", "MAT-FO01": "Tela forrería", "MAT-HC01": "Hilo y cemento"}


def _ficha(monkeypatch, datos=None):
    datos = datos or _datos()
    monkeypatch.setattr(servicios, "_cargar_uno", lambda session, codigo: (datos, {}))
    monkeypatch.setattr(servicios, "cargar_contexto", lambda session: SimpleNamespace(parametros={}))
    monkeypatch.setattr(servicios, "_costo_hoy_seguro", lambda d, ctx, catalogo: (None, []))
    monkeypatch.setattr(servicios, "marca_recotizar", lambda *a, **k: None)
    monkeypatch.setattr(servicios, "_nombres_de_materiales", lambda session, codigos: {c: NOMBRES[c] for c in codigos if c in NOMBRES})
    session = MagicMock()
    session.scalars.return_value.all.return_value = []
    return servicios.ficha_producto(session, "PRD-0001")


def test_every_recipe_line_carries_the_name_of_its_material_and_keeps_the_code(monkeypatch):
    ficha = _ficha(monkeypatch)
    assert [(l["etapa"], l["material"], l["material_nombre"]) for l in ficha["receta"]] == [
        ("CUERO", "MAT-CU01", "Estándar"), ("FORRO", "MAT-FO01", "Tela forrería"), ("HILO_CEMENTO", "MAT-HC01", "Hilo y cemento"),
    ]


def test_a_material_without_a_known_name_shows_its_code(monkeypatch):
    monkeypatch.setitem(NOMBRES, "MAT-CU01", "")
    ficha = _ficha(monkeypatch)
    assert ficha["receta"][0]["material_nombre"] == "MAT-CU01"


def test_the_ficha_carries_the_leather_name_the_model_name_and_the_hours(monkeypatch):
    ficha = _ficha(monkeypatch)
    assert (ficha["cuero_nombre"], ficha["modelo_nombre"], ficha["horas_de_confeccion"]) == ("Estándar", "Portafolio Simple Ch.", D("2.5"))
    assert (ficha["cuero"], ficha["modelo"]) == ("MAT-CU01", "MOD-0001")  # the old keys stay


def test_a_product_without_model_has_no_hours(monkeypatch):
    ficha = _ficha(monkeypatch, _datos(horas_de_confeccion=None, modelo_nombre=None, cuero_nombre=None))
    assert (ficha["horas_de_confeccion"], ficha["modelo_nombre"], ficha["cuero_nombre"]) == (None, None, None)


def test_the_hours_never_enter_the_cost(monkeypatch):
    # The engine receives the same recipe whatever the hours are: they are not an input of the model the engine reads.
    assert "horas" not in ModeloReceta.__dataclass_fields__ and "horas_de_confeccion" not in ModeloReceta.__dataclass_fields__


def test_the_api_model_exposes_the_new_fields_as_optional(monkeypatch):
    ficha = _ficha(monkeypatch)
    salida = FichaOut.model_validate(ficha)
    assert salida.horas_de_confeccion == D("2.5") and salida.receta[0].material_nombre == "Estándar"
    viejo = {k: v for k, v in ficha.items() if k not in ("horas_de_confeccion", "cuero_nombre", "modelo_nombre")}
    viejo["receta"] = [{k: v for k, v in l.items() if k != "material_nombre"} for l in ficha["receta"]]
    sin = FichaOut.model_validate(viejo)
    assert (sin.horas_de_confeccion, sin.cuero_nombre, sin.receta[0].material_nombre) == (None, None, None)


# --- Cambiar el color ---------------------------------------------------------------------------------------------

def _sesion_con_producto(producto):
    session = MagicMock()
    session.scalar.return_value = producto
    return session


def test_the_service_sets_the_color_by_name_and_answers_the_ficha(monkeypatch):
    producto = SimpleNamespace(color_id=None)
    monkeypatch.setattr(servicios, "_color_id", lambda session, nombre: 7)
    monkeypatch.setattr(servicios, "ficha_producto", lambda session, codigo: {"codigo": codigo})
    session = _sesion_con_producto(producto)
    assert servicios.cambiar_color_de_producto(session, "PRD-0001", "  Negro ") == {"codigo": "PRD-0001"}
    assert producto.color_id == 7
    session.commit.assert_called_once()


def test_an_empty_color_clears_it(monkeypatch):
    producto = SimpleNamespace(color_id=7)
    monkeypatch.setattr(servicios, "ficha_producto", lambda session, codigo: {})
    servicios.cambiar_color_de_producto(_sesion_con_producto(producto), "PRD-0001", "   ")
    assert producto.color_id is None


def test_an_unknown_product_is_not_found():
    with pytest.raises(NoEncontrado):
        servicios.cambiar_color_de_producto(_sesion_con_producto(None), "PRD-9999", "Negro")


def test_an_unknown_color_changes_nothing(monkeypatch):
    producto = SimpleNamespace(color_id=3)
    session = _sesion_con_producto(producto)
    # The real `_color_id` runs against a session that finds no such color.
    session.scalar.side_effect = [producto, None]
    with pytest.raises(DatosInvalidos, match="No existe el color Fucsia"):
        servicios.cambiar_color_de_producto(session, "PRD-0001", "Fucsia")
    assert producto.color_id == 3
    session.commit.assert_not_called()


def _cliente(role):
    app.dependency_overrides[get_session] = lambda: MagicMock()
    app.dependency_overrides[get_verifier] = lambda: (lambda request: Usuario(id="u-1", role=role))
    return TestClient(app, raise_server_exceptions=False)


def test_only_the_admin_can_change_the_color(monkeypatch):
    llamadas = []
    monkeypatch.setattr(servicios, "cambiar_color_de_producto", lambda session, codigo, color: llamadas.append((codigo, color)) or {})
    for role in ("gerente", "taller"):
        assert _cliente(role).put("/productos/PRD-0001/color", json={"color": "Negro"}).status_code == 403
    assert llamadas == []
    _cliente("admin").put("/productos/PRD-0001/color", json={"color": "Negro"})
    assert llamadas == [("PRD-0001", "Negro")]
