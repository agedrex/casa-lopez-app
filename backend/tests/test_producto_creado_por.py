"""Productos list: "Creado" column (creation date and user). Mocked tests (no database).

Rules: the service returns `creado_en` and `creado_por` (a display name); creating through the API stores the user id; an
unknown user or an unreadable `public."user"` table falls back to the raw id and never fails the list; the old keys stay.
"""

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import ProgrammingError

from backend import servicios
from backend.auth import Usuario, get_verifier
from backend.database import get_session
from backend.main import app
from backend.models import Producto

CREADO = datetime(2026, 11, 16, 14, 30, tzinfo=timezone.utc)


@pytest.fixture(autouse=True)
def limpiar(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    yield
    app.dependency_overrides.clear()


def _datos(n, creado_por=None):
    return SimpleNamespace(id=n, codigo=f"PRD-000{n}", nombre="x", categoria=None, estado_del_ciclo="ACTIVO", es_kit=False,
                           nota=None, modelo_codigo="MOD-0001", creado_en=CREADO if creado_por else None, creado_por=creado_por)


def _lista(monkeypatch, session, *filas):
    monkeypatch.setattr(servicios, "cargar_productos", lambda *a, **k: list(filas))
    monkeypatch.setattr(servicios, "expandir_kits", lambda s, b: {})
    monkeypatch.setattr(servicios, "cargar_contexto", lambda s: None)
    monkeypatch.setattr(servicios, "_costo_hoy_seguro", lambda datos, ctx, catalogo: (None, []))
    monkeypatch.setattr(servicios, "_ultimos_precios_de_venta_completos", lambda s, ids: {})
    return servicios.listar_productos(session)


def _sesion_con_usuarios(*filas):
    session = MagicMock()
    session.execute.return_value.all.return_value = list(filas)
    return session


def test_the_list_returns_the_creation_date_and_the_name_of_the_user(monkeypatch):
    session = _sesion_con_usuarios(("u-1", "Agustín", "agustin@casa.test"), ("u-2", "", "taller@casa.test"))
    filas = _lista(monkeypatch, session, _datos(1, "u-1"), _datos(2, "u-2"))
    assert [(f["creado_en"], f["creado_por"]) for f in filas] == [(CREADO, "Agustín"), (CREADO, "taller@casa.test")]


def test_the_names_of_the_page_are_read_in_one_query(monkeypatch):
    session = _sesion_con_usuarios(("u-1", "Agustín", None))
    _lista(monkeypatch, session, _datos(1, "u-1"), _datos(2, "u-1"), _datos(3, None))
    assert session.execute.call_count == 1
    assert session.execute.call_args.args[1] == {"ids": ["u-1"]}


def test_an_unknown_user_shows_the_raw_id(monkeypatch):
    filas = _lista(monkeypatch, _sesion_con_usuarios(), _datos(1, "u-borrado"))
    assert (filas[0]["creado_en"], filas[0]["creado_por"]) == (CREADO, "u-borrado")


def test_an_unreadable_user_table_never_fails_the_list(monkeypatch):
    session = MagicMock()
    session.execute.side_effect = ProgrammingError("select", {}, Exception('relation "public.user" does not exist'))
    filas = _lista(monkeypatch, session, _datos(1, "u-1"))
    assert filas[0]["creado_por"] == "u-1" and filas[0]["codigo"] == "PRD-0001"
    session.begin_nested.assert_called_once()  # savepoint: a failed read cannot poison the page's transaction


def test_a_product_created_before_the_column_has_no_creator_and_reads_no_users(monkeypatch):
    session = _sesion_con_usuarios()
    filas = _lista(monkeypatch, session, _datos(1))
    assert (filas[0]["creado_en"], filas[0]["creado_por"]) == (None, None)
    session.execute.assert_not_called()


def test_the_old_keys_stay_in_the_list_rows(monkeypatch):
    fila = _lista(monkeypatch, _sesion_con_usuarios(), _datos(1))[0]
    assert {"codigo", "nombre", "categoria", "modelo", "modelo_codigo", "modelo_nombre", "estado_del_ciclo", "es_kit",
            "costo_hoy_ars", "costo_hoy_usd", "cotizacion_fecha", "costo_cotizado_ars", "avisos", "revisar",
            "motivos_revisar", "precio_venta_ars", "margen_pct", "precio_final_ars"} <= set(fila)
    assert fila["codigo"] == "PRD-0001" and fila["modelo"] == "MOD-0001"


# --- Creating ----------------------------------------------------------------------------------------------------

def test_the_service_stores_the_user_id_in_the_new_product(monkeypatch):
    guardados = []
    monkeypatch.setattr(servicios, "_por_codigo", lambda session, modelo, codigo, que: SimpleNamespace(id=1))
    monkeypatch.setattr(servicios, "_material_de_receta", lambda *a, **k: SimpleNamespace(id=2))
    monkeypatch.setattr(servicios, "_siguiente_numero", lambda *a, **k: 7)
    monkeypatch.setattr(servicios, "_color_id", lambda *a, **k: None)
    monkeypatch.setattr(servicios, "_comprobar_producto_repetido", lambda *a, **k: None)  # the rule has its own tests
    monkeypatch.setattr(servicios, "_insertar", lambda session, fila, conflicto: guardados.append(fila))
    monkeypatch.setattr(servicios, "ficha_producto", lambda session, codigo: {"codigo": codigo})
    datos = dict(modelo="MOD-0001", cuero="MAT-CU01", color=None, quien_lo_confecciona="INTERNA", fecha_de_alta=None,
                 nombre_propio=None, es_kit=False)
    servicios.crear_producto(MagicMock(), **datos, quien="u-1")
    servicios.crear_producto(MagicMock(), **datos)  # scripts keep the old signature and leave it empty
    assert [(p.codigo, p.creado_por) for p in guardados] == [("PRD-0007", "u-1"), ("PRD-0007", None)]
    assert all(isinstance(p, Producto) for p in guardados)


def test_creating_through_the_api_passes_the_id_of_the_signed_in_user(monkeypatch):
    visto = {}
    monkeypatch.setattr(servicios, "crear_producto", lambda session, **k: visto.update(k) or {"codigo": "PRD-0001"})
    app.dependency_overrides[get_session] = lambda: MagicMock()
    app.dependency_overrides[get_verifier] = lambda: (lambda request: Usuario(id="user-42", role="admin"))
    # The service is mocked, so the response model may reject the stub: the call itself is what matters here.
    TestClient(app, raise_server_exceptions=False).post("/productos", json={"modelo": "MOD-0001", "cuero": "MAT-CU01"})
    assert visto["quien"] == "user-42" and visto["modelo"] == "MOD-0001"
