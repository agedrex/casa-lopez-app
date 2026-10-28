"""Sheet sync endpoints (T6): `POST /sync/sheets`, `GET /sync/sheets/estado`, `GET /sync/sheets/vista/{tab}`.

No database and no Google: the data source and the Sheets client are replaced through dependency overrides.
"""

import threading

import pytest
from fastapi.testclient import TestClient

from backend import api as api_module
from backend.auth import Usuario, get_verifier
from backend.main import app
from backend.sheets_client import ErrorDeSheets
from backend.sheets_export import NOMBRES_DE_PESTANAS
from sheets_datos import FuenteEnMemoria, producto_costeado

ID = "1AbCdEfGhIjKlMnOpQrStUvWxYz_0123456789-abc"
CREDENCIAL = '{"private_key": "SECRETO-NO-DEBE-SALIR", "client_email": "sync@p.iam.gserviceaccount.com"}'
VARIABLES = ("GOOGLE_SHEETS_SPREADSHEET_ID", "GOOGLE_SERVICE_ACCOUNT_JSON")


class ClienteFalso:
    def __init__(self, error: Exception | None = None, esperar: threading.Event | None = None):
        self.llamadas: list[list] = []
        self.error = error
        self.esperar = esperar
        self.entro = threading.Event()

    def reemplazar_pestanas(self, tabs):
        self.entro.set()
        if self.esperar is not None:
            assert self.esperar.wait(5)
        if self.error is not None:
            raise self.error
        self.llamadas.append(list(tabs))


@pytest.fixture
def entorno(monkeypatch):
    for nombre in VARIABLES:
        monkeypatch.delenv(nombre, raising=False)
    monkeypatch.setattr(api_module, "_ESTADO_SYNC", api_module.EstadoDeSincronizacion())

    def configurar():
        monkeypatch.setenv(VARIABLES[0], ID)
        monkeypatch.setenv(VARIABLES[1], CREDENCIAL)

    return configurar


def cliente_http(rol="admin", fuente=None, cliente_sheets=None):
    app.dependency_overrides[get_verifier] = lambda: (lambda request: Usuario(id="u1", role=rol))
    app.dependency_overrides[api_module.get_fuente_sheets] = lambda: fuente or FuenteEnMemoria()
    app.dependency_overrides[api_module.get_cliente_sheets] = lambda: cliente_sheets
    return TestClient(app)


@pytest.fixture(autouse=True)
def limpiar():
    yield
    app.dependency_overrides.clear()


# --- Access -----------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("metodo, ruta", [
    ("post", "/sync/sheets"), ("get", "/sync/sheets/estado"), ("get", "/sync/sheets/vista/Dolar"),
])
def test_everything_needs_a_session(metodo, ruta, entorno):
    app.dependency_overrides[get_verifier] = lambda: (lambda request: None)
    with TestClient(app) as http:
        assert getattr(http, metodo)(ruta).status_code == 401


@pytest.mark.parametrize("rol", ["consulta", "cotizador", "consulta,cotizador"])
def test_running_and_previewing_are_admin_only(rol, entorno):
    entorno()
    cliente = ClienteFalso()
    with cliente_http(rol, cliente_sheets=cliente) as http:
        assert http.post("/sync/sheets", json={"simular": False}).status_code == 403
        assert http.post("/sync/sheets", json={"simular": True}).status_code == 403
        assert http.get("/sync/sheets/vista/Dolar").status_code == 403
    assert cliente.llamadas == []


@pytest.mark.parametrize("rol", ["consulta", "cotizador", "admin"])
def test_any_signed_in_user_can_read_the_status(rol, entorno):
    with cliente_http(rol) as http:
        assert http.get("/sync/sheets/estado").status_code == 200


# --- Dry run and real run ---------------------------------------------------------------------------------------

def test_unconfigured_defaults_to_a_dry_run_that_returns_the_counts(entorno):
    cliente = ClienteFalso()
    with cliente_http(cliente_sheets=None) as http:
        for cuerpo in ({}, {"simular": None}, None):
            respuesta = http.post("/sync/sheets", json=cuerpo) if cuerpo is not None else http.post("/sync/sheets")
            assert respuesta.status_code == 200, respuesta.text
            datos = respuesta.json()
            assert datos["simulacion"] is True and datos["configurado"] is False
            assert [p["nombre"] for p in datos["pestanas"]] == list(NOMBRES_DE_PESTANAS)
            assert {p["nombre"]: p["filas"] for p in datos["pestanas"]}["Catalogo"] == 1
            assert datos["total_filas"] == sum(p["filas"] for p in datos["pestanas"])
            assert datos["duracion_ms"] >= 0 and datos["iniciado"] <= datos["finalizado"]
    assert cliente.llamadas == []


def test_an_explicit_dry_run_never_calls_the_client_even_when_configured(entorno):
    entorno()
    cliente = ClienteFalso()
    with cliente_http(cliente_sheets=cliente) as http:
        datos = http.post("/sync/sheets", json={"simular": True}).json()
    assert datos["simulacion"] is True and datos["configurado"] is True
    assert cliente.llamadas == []


def test_unconfigured_and_not_a_dry_run_is_refused_with_a_clear_reason(entorno):
    cliente = ClienteFalso()
    with cliente_http(cliente_sheets=cliente) as http:
        respuesta = http.post("/sync/sheets", json={"simular": False})
    assert respuesta.status_code == 422
    detalle = respuesta.json()["detail"]
    assert "GOOGLE_SHEETS_SPREADSHEET_ID" in detalle and "GOOGLE_SERVICE_ACCOUNT_JSON" in detalle
    assert cliente.llamadas == []


def test_a_real_run_pushes_every_tab_once_and_reports_the_counts(entorno):
    entorno()
    cliente = ClienteFalso()
    with cliente_http(cliente_sheets=cliente) as http:
        respuesta = http.post("/sync/sheets", json={"simular": False})
    assert respuesta.status_code == 200, respuesta.text
    datos = respuesta.json()
    assert datos["simulacion"] is False and datos["configurado"] is True
    (enviadas,) = cliente.llamadas
    assert [t.name for t in enviadas] == list(NOMBRES_DE_PESTANAS)
    assert {p["nombre"]: p["filas"] for p in datos["pestanas"]} == {t.name: len(t.rows) for t in enviadas}


def test_configured_without_a_body_pushes_because_the_default_is_dry_run_only_when_unconfigured(entorno):
    entorno()
    cliente = ClienteFalso()
    with cliente_http(cliente_sheets=cliente) as http:
        datos = http.post("/sync/sheets", json={}).json()
    assert datos["simulacion"] is False and len(cliente.llamadas) == 1


def test_unknown_fields_in_the_body_are_refused(entorno):
    with cliente_http() as http:
        assert http.post("/sync/sheets", json={"simular": True, "hoja": "Otra"}).status_code == 422


# --- Concurrency and errors ---------------------------------------------------------------------------------------

def test_a_second_run_while_one_is_in_progress_gets_409(entorno):
    entorno()
    liberar = threading.Event()
    lento = ClienteFalso(esperar=liberar)
    resultados = {}

    def primera():
        with cliente_http(cliente_sheets=lento) as http:
            resultados["primera"] = http.post("/sync/sheets", json={"simular": False})

    hilo = threading.Thread(target=primera)
    hilo.start()
    try:
        assert lento.entro.wait(5)
        with TestClient(app) as segundo:
            respuesta = segundo.post("/sync/sheets", json={"simular": True})
            assert respuesta.status_code == 409
            assert "en curso" in respuesta.json()["detail"]
            assert segundo.get("/sync/sheets/estado").json()["en_curso"] is True
    finally:
        liberar.set()
        hilo.join(5)
    assert resultados["primera"].status_code == 200
    with cliente_http(cliente_sheets=ClienteFalso()) as http:
        assert http.post("/sync/sheets", json={"simular": False}).status_code == 200  # the lock was released
        assert http.get("/sync/sheets/estado").json()["en_curso"] is False


def test_a_google_error_is_a_502_with_the_safe_message_and_the_lock_is_released(entorno):
    entorno()
    roto = ClienteFalso(error=ErrorDeSheets("Google rechazó el acceso: compartí el Sheet.", estado=403))
    with cliente_http(cliente_sheets=roto) as http:
        respuesta = http.post("/sync/sheets", json={"simular": False})
        assert respuesta.status_code == 502
        assert respuesta.json() == {"detail": "Google rechazó el acceso: compartí el Sheet."}
        app.dependency_overrides[api_module.get_cliente_sheets] = lambda: ClienteFalso()
        assert http.post("/sync/sheets", json={"simular": False}).status_code == 200


def test_an_unexpected_failure_while_pushing_is_a_generic_502_that_leaks_nothing(entorno):
    entorno()
    roto = ClienteFalso(error=RuntimeError("traza con SECRETO-NO-DEBE-SALIR"))
    with cliente_http(cliente_sheets=roto) as http:
        respuesta = http.post("/sync/sheets", json={"simular": False})
    assert respuesta.status_code == 502
    assert "SECRETO" not in respuesta.text and "traza" not in respuesta.text
    assert respuesta.json()["detail"] == "No se pudo sincronizar con Google Sheets."


def test_a_bad_credential_is_a_502_with_its_safe_message(entorno):
    entorno()
    with cliente_http(cliente_sheets=ClienteFalso(error=ErrorDeSheets("GOOGLE_SERVICE_ACCOUNT_JSON no es válido."))) as http:
        assert http.post("/sync/sheets", json={"simular": False}).status_code == 502


# --- Status -------------------------------------------------------------------------------------------------------

def test_status_unconfigured_names_the_missing_variables_and_never_their_values(entorno):
    with cliente_http("consulta") as http:
        datos = http.get("/sync/sheets/estado").json()
    assert datos["configurado"] is False
    assert datos["variables"] == list(VARIABLES) and datos["faltantes"] == list(VARIABLES)
    assert datos["pestanas"] == list(NOMBRES_DE_PESTANAS)
    assert datos["ultima"] is None and datos["en_curso"] is False


def test_status_configured_reports_yes_and_only_that(entorno):
    entorno()
    with cliente_http("consulta") as http:
        respuesta = http.get("/sync/sheets/estado")
    datos = respuesta.json()
    assert datos["configurado"] is True and datos["faltantes"] == []
    assert ID not in respuesta.text and "SECRETO" not in respuesta.text and "private_key" not in respuesta.text


def test_status_keeps_the_summary_of_the_last_run_in_memory(entorno):
    with cliente_http() as http:
        http.post("/sync/sheets", json={"simular": True})
        ultima = http.get("/sync/sheets/estado").json()["ultima"]
    assert ultima["simulacion"] is True and ultima["ok"] is True and ultima["error"] is None
    assert ultima["total_filas"] > 0 and len(ultima["pestanas"]) == len(NOMBRES_DE_PESTANAS)


def test_status_remembers_a_failed_run_with_its_safe_message(entorno):
    entorno()
    with cliente_http(cliente_sheets=ClienteFalso(error=ErrorDeSheets("Google no respondió.", estado=503))) as http:
        http.post("/sync/sheets", json={"simular": False})
        ultima = http.get("/sync/sheets/estado").json()["ultima"]
    assert ultima["ok"] is False and ultima["error"] == "Google no respondió." and ultima["simulacion"] is False


# --- Secrets -------------------------------------------------------------------------------------------------------

def test_no_response_contains_the_credential_or_the_sheet_id(entorno):
    entorno()
    con_error = ClienteFalso(error=RuntimeError("SECRETO-NO-DEBE-SALIR " + CREDENCIAL))
    respuestas = []
    with cliente_http(cliente_sheets=ClienteFalso()) as http:
        respuestas.append(http.post("/sync/sheets", json={"simular": True}))
        respuestas.append(http.post("/sync/sheets", json={"simular": False}))
        respuestas.append(http.get("/sync/sheets/estado"))
        respuestas.append(http.get("/sync/sheets/vista/Dolar"))
        app.dependency_overrides[api_module.get_cliente_sheets] = lambda: con_error
        respuestas.append(http.post("/sync/sheets", json={"simular": False}))
        respuestas.append(http.get("/sync/sheets/estado"))
    for respuesta in respuestas:
        assert "SECRETO-NO-DEBE-SALIR" not in respuesta.text and "private_key" not in respuesta.text
        assert ID not in respuesta.text and "client_email" not in respuesta.text


# --- Preview --------------------------------------------------------------------------------------------------------

def test_preview_returns_headers_and_only_the_first_50_rows(entorno):
    fuente = FuenteEnMemoria(productos_costeados_=[producto_costeado(codigo=f"PRD-{i:04d}") for i in range(60)])
    with cliente_http(fuente=fuente) as http:
        datos = http.get("/sync/sheets/vista/Catalogo").json()
    assert datos["pestana"] == "Catalogo" and datos["total_filas"] == 60 and datos["mostradas"] == 50
    assert len(datos["filas"]) == 50 and datos["filas"][0][0] == "PRD-0000"
    assert datos["encabezados"][0] == "Código" and len(datos["filas"][0]) == len(datos["encabezados"])


def test_preview_serialises_money_as_text_never_as_a_number(entorno):
    with cliente_http() as http:
        datos = http.get("/sync/sheets/vista/Dolar").json()
    assert datos["filas"] == [["2026-09-01", "1545", "EXCEL_VIEJO", "", ""]]
    assert all(isinstance(celda, str) for fila in datos["filas"] for celda in fila)


def test_preview_of_an_unknown_tab_is_404(entorno):
    with cliente_http() as http:
        assert http.get("/sync/sheets/vista/Hoja1").status_code == 404


def test_preview_does_not_touch_google_or_the_lock(entorno):
    entorno()
    cliente = ClienteFalso()
    with cliente_http(cliente_sheets=cliente) as http:
        assert http.get("/sync/sheets/vista/Info").status_code == 200
        assert http.get("/sync/sheets/estado").json()["ultima"] is None
    assert cliente.llamadas == []
