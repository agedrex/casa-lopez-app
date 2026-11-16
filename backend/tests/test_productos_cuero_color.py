"""Productos list: "Cuero" and "Color" columns. Mocked tests (no database).

Rules: each list row carries the short name of the leather (the code when it has no short name) and the color name;
a product without them gets `None`, never a made-up text; the API exposes both as optional fields; the old keys stay.
"""

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from backend import servicios
from backend.api import ProductoResumen
from backend.main import app


@pytest.fixture(autouse=True)
def limpiar(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    yield
    app.dependency_overrides.clear()


def _producto(n):
    return SimpleNamespace(
        id=n, codigo=f"PRD-000{n}", nombre_propio=None, quien_lo_confecciona="INTERNA", estado_del_ciclo="ACTIVO",
        es_kit=False, nota=None, fecha_de_alta=None, fecha_de_recotizacion=None, fecha_de_cierre=None,
        created_at=datetime(2026, 11, 16, tzinfo=timezone.utc), creado_por=None,
    )


def _cargar(*filas):
    session = MagicMock()
    session.execute.return_value.all.return_value = list(filas)
    return servicios.cargar_productos(session)


def test_the_loaded_product_carries_the_short_name_of_the_leather_and_the_color():
    [datos] = _cargar((_producto(1), None, None, "MAT-CU01", "Estándar", None, "Negro"))
    assert (datos.cuero_nombre, datos.color, datos.cuero) == ("Estándar", "Negro", "MAT-CU01")


def test_a_leather_without_short_name_shows_its_code():
    [datos] = _cargar((_producto(1), None, None, "MAT-CU02", None, None, None))
    assert (datos.cuero_nombre, datos.color) == ("MAT-CU02", None)


def test_a_product_without_leather_and_color_has_none():
    [datos] = _cargar((_producto(1), None, None, None, None, None, None))
    assert (datos.cuero_nombre, datos.color) == (None, None)


def _datos(**extra):
    base = dict(id=1, codigo="PRD-0001", nombre="x", categoria=None, estado_del_ciclo="ACTIVO", es_kit=False, nota=None,
                modelo_codigo="MOD-0001", creado_en=None, creado_por=None)
    return SimpleNamespace(**{**base, **extra})


def _lista(monkeypatch, *filas):
    monkeypatch.setattr(servicios, "cargar_productos", lambda *a, **k: list(filas))
    monkeypatch.setattr(servicios, "expandir_kits", lambda s, b: {})
    monkeypatch.setattr(servicios, "cargar_contexto", lambda s: None)
    monkeypatch.setattr(servicios, "_costo_hoy_seguro", lambda datos, ctx, catalogo: (None, []))
    monkeypatch.setattr(servicios, "_ultimos_precios_de_venta_completos", lambda s, ids: {})
    return servicios.listar_productos(MagicMock())


def test_the_list_rows_have_cuero_and_color(monkeypatch):
    filas = _lista(monkeypatch, _datos(cuero_nombre="Estándar", color="Negro"), _datos(id=2, codigo="PRD-0002"))
    assert [(f["cuero"], f["color"]) for f in filas] == [("Estándar", "Negro"), (None, None)]


def test_the_old_keys_stay_in_the_list_rows(monkeypatch):
    fila = _lista(monkeypatch, _datos())[0]
    assert {"codigo", "nombre", "categoria", "modelo", "estado_del_ciclo", "es_kit", "costo_hoy_ars", "avisos", "revisar",
            "creado_en", "creado_por"} <= set(fila)


def test_the_api_model_exposes_cuero_and_color_as_optional_fields(monkeypatch):
    [fila] = _lista(monkeypatch, _datos(cuero_nombre="Estándar", color="Negro"))
    salida = ProductoResumen.model_validate(fila)
    assert (salida.cuero, salida.color) == ("Estándar", "Negro")
    sin = ProductoResumen.model_validate({k: v for k, v in fila.items() if k not in ("cuero", "color")})
    assert (sin.cuero, sin.color) == (None, None)
