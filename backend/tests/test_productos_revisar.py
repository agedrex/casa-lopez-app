"""REVISAR marks of the product list: note parser, row shape, query filter and the API parameter.

The note format is the one written by the Excel importer: `IMPORTADO-EXCEL fila N | REVISAR: <reason> | B=... | E=...`.
"""

import re
from types import SimpleNamespace
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


@pytest.fixture(autouse=True)
def limpiar(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    yield
    app.dependency_overrides.clear()


def _cliente(role="gerente"):
    app.dependency_overrides[get_session] = lambda: MagicMock()
    app.dependency_overrides[get_verifier] = lambda: (lambda request: Usuario(id="u", role=role))
    return TestClient(app)


# --- Parser -----------------------------------------------------------------------------------------------------

def test_the_parser_returns_every_reason_in_order():
    nota = (
        "IMPORTADO-EXCEL fila 22 | REVISAR: sin tipo de cuero | REVISAR: modelo repetido | B=Fabián | E=2026-08-25"
        " | Comentario AE53: Sanchez 1,000 pidió, pagamos 750"
    )
    assert servicios.motivos_de_revision(nota) == ["sin tipo de cuero", "modelo repetido"]


def test_the_parser_keeps_the_parentheses_of_a_reason():
    nota = "IMPORTADO-EXCEL fila 9 | REVISAR: cuero Lagarto no cotizable (pendiente Gerardo) | REVISAR: error en origen (X42, #REF!)"
    assert servicios.motivos_de_revision(nota) == [
        "cuero Lagarto no cotizable (pendiente Gerardo)", "error en origen (X42, #REF!)",
    ]


@pytest.mark.parametrize("nota", [None, "", "   ", "IMPORTADO-EXCEL fila 3 | B=Lucio | E=2026-01-05", "texto libre sin formato",
                                  "REVISAR sin dos puntos", "revisar: en minúsculas", "||", " | | "])
def test_the_parser_tolerates_empty_notes_and_text_without_the_format(nota):
    assert servicios.motivos_de_revision(nota) == []


def test_the_parser_ignores_a_mark_that_is_not_an_item_of_the_note():
    # A comment that merely mentions REVISAR: is not a mark: only an item that STARTS with it is.
    nota = "IMPORTADO-EXCEL fila 5 | Comentario AE9: hay que REVISAR: el precio | REVISAR: sin nombre"
    assert servicios.motivos_de_revision(nota) == ["sin nombre"]


def test_the_parser_skips_a_mark_without_a_reason_and_trims_spaces():
    assert servicios.motivos_de_revision("REVISAR: |   REVISAR:   modelo repetido  ") == ["modelo repetido"]


NOTAS_QUE_NO_SON_MARCA = [
    "revisar: consultar a Gerardo", "Revisar: precio", "Comentario AE9: hay que REVISAR: el precio", "REVISAR:",
    "IMPORTADO-EXCEL fila 3 | REVISAR:  ", "IMPORTADO-EXCEL fila 3 | REVISAR: | B=Lucio", "REVISAR:| x", "REVISAR: |",
]
NOTAS_CON_MARCA = {
    "IMPORTADO-EXCEL fila 3 | REVISAR: modelo repetido": ["modelo repetido"],
    "REVISAR: sin nombre": ["sin nombre"],
    "  REVISAR:\tcon tabulación  ": ["con tabulación"],
    "REVISAR: error en origen (a|b) | REVISAR: otro": ["error en origen (a|b)", "otro"],
}


@pytest.mark.parametrize("nota", NOTAS_QUE_NO_SON_MARCA)
def test_text_that_only_resembles_a_mark_gives_no_reason(nota):
    assert servicios.motivos_de_revision(nota) == []


@pytest.mark.parametrize("nota, motivos", NOTAS_CON_MARCA.items())
def test_the_parser_reads_the_reasons_of_valid_marks(nota, motivos):
    assert servicios.motivos_de_revision(nota) == motivos


@pytest.mark.parametrize("nota", [*NOTAS_QUE_NO_SON_MARCA, *NOTAS_CON_MARCA, None, ""])
def test_the_filter_pattern_and_the_parser_accept_the_same_notes(nota):
    # The SQL filter uses the start of the very pattern the parser extends: they cannot disagree.
    assert bool(re.search(servicios.PATRON_REVISAR_SQL, nota or "")) == bool(servicios.motivos_de_revision(nota))


# --- Row of the list ----------------------------------------------------------------------------------------------

def _datos(codigo, nota, modelo_codigo="MOD-0001"):
    return SimpleNamespace(id=int(codigo[-4:]), codigo=codigo, nombre=f"Producto {codigo}", categoria="Carteras", estado_del_ciclo="ACTIVO",
                           es_kit=False, nota=nota, modelo_codigo=modelo_codigo)


def test_the_list_row_carries_the_model_and_the_review_marks(monkeypatch):
    base = [_datos("PRD-0001", "IMPORTADO-EXCEL fila 1 | REVISAR: sin nombre | REVISAR: modelo repetido"),
            _datos("PRD-0002", "IMPORTADO-EXCEL fila 2", modelo_codigo=None), _datos("PRD-0003", None)]
    monkeypatch.setattr(servicios, "cargar_productos", lambda *a, **k: base)
    monkeypatch.setattr(servicios, "expandir_kits", lambda session, b: {})
    monkeypatch.setattr(servicios, "cargar_contexto", lambda session: None)
    monkeypatch.setattr(servicios, "_costo_hoy_seguro", lambda datos, ctx, catalogo: (None, ["Falta el dólar"]))
    filas = servicios.listar_productos(MagicMock())
    assert [(f["codigo"], f["modelo"], f["revisar"], f["motivos_revisar"]) for f in filas] == [
        ("PRD-0001", "MOD-0001", True, ["sin nombre", "modelo repetido"]),
        ("PRD-0002", None, False, []),
        ("PRD-0003", "MOD-0001", False, []),
    ]
    assert filas[0]["avisos"] == ["Falta el dólar"] and filas[0]["costo_hoy_ars"] is None  # the old keys stay


def test_the_summary_model_exposes_the_new_fields(monkeypatch):
    fila = {"codigo": "PRD-0001", "nombre": "x", "categoria": None, "estado_del_ciclo": "ACTIVO", "es_kit": False,
            "costo_hoy_ars": None, "costo_hoy_usd": None, "avisos": [], "modelo": "MOD-0001", "revisar": True,
            "motivos_revisar": ["sin nombre"], "precio_venta_ars": None, "margen_pct": None, "precio_final_ars": None}
    monkeypatch.setattr(servicios, "listar_productos", lambda *a, **k: [fila])
    cuerpo = _cliente().get("/productos").json()
    nuevos = {"modelo_codigo": None, "modelo_nombre": None, "cotizacion_fecha": None, "cotizacion_dolar": None,
              "costo_cotizado_ars": None, "costo_cotizado_usd": None}
    assert cuerpo == [{**fila, **nuevos}]


# --- Query filter -------------------------------------------------------------------------------------------------

def _sql(**filtros):
    cuero = aliased(Material)
    consulta = servicios._filtrar_productos(select(Producto.id).select_from(Producto), cuero, **filtros)
    compilada = consulta.compile(dialect=postgresql.dialect())
    return str(compilada), compilada.params


def test_the_review_filter_uses_the_case_sensitive_regex_of_the_parser_not_ilike():
    sql, params = _sql(q=None, categoria=None, revisar=True)
    assert "producto.nota ~" in sql and "ILIKE" not in sql
    assert list(params.values()) == [servicios.PATRON_REVISAR_SQL]


def test_without_the_review_filter_the_query_does_not_change():
    antes = _sql(q="cartera negra", categoria="Carteras")
    assert _sql(q="cartera negra", categoria="Carteras", revisar=False) == antes
    assert "nota" not in antes[0]


def test_the_review_filter_combines_with_the_search():
    sql, params = _sql(q="cartera", categoria="Carteras", revisar=True)
    assert "producto.nota ~" in sql and "%cartera%" in params.values() and servicios.PATRON_REVISAR_SQL in params.values()


# --- API parameter ------------------------------------------------------------------------------------------------

def test_the_review_parameter_reaches_the_list_and_the_count(monkeypatch):
    vistos = {}
    monkeypatch.setattr(servicios, "listar_productos", lambda session, limit, offset, q=None, categoria=None, revisar=False:
                        vistos.setdefault("lista", []).append(revisar) or [])
    monkeypatch.setattr(servicios, "contar_productos", lambda session, q=None, categoria=None, revisar=False:
                        vistos.setdefault("conteo", []).append(revisar) or 3)
    client = _cliente()
    assert client.get("/productos").status_code == 200
    assert client.get("/productos", params={"revisar": "true"}).status_code == 200
    assert client.get("/productos/conteo").json() == {"total": 3}
    assert client.get("/productos/conteo", params={"revisar": "true"}).json() == {"total": 3}
    assert vistos == {"lista": [False, True], "conteo": [False, True]}


def test_an_invalid_review_value_is_a_validation_error():
    assert _cliente().get("/productos", params={"revisar": "quizás"}).status_code == 422
    assert _cliente().get("/productos/conteo", params={"revisar": "quizás"}).status_code == 422
