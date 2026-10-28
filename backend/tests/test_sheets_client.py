"""Google Sheets client (T6). No real Google endpoint is ever called: `httpx.MockTransport` plays Google.

The service account used here is generated on the spot and has never existed anywhere else.
"""

import json
import logging
from decimal import Decimal as D

import httpx
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from backend import sheets_client
from backend.sheets_client import (
    ClienteGoogleSheets, ConfigSheets, ErrorDeSheets, SheetsClient, crear_cliente, faltantes, leer_config,
)
from backend.sheets_export import NOMBRES_DE_PESTANAS, Tab

ID = "1AbCdEfGhIjKlMnOpQrStUvWxYz_0123456789-abc"
BASE = f"https://sheets.googleapis.com/v4/spreadsheets/{ID}"
MARCADOR_SECRETO = "SECRETO-NO-DEBE-SALIR"


def tab(nombre="Dolar", filas=2):
    return Tab(nombre, ("Fecha", "ARS por USD", "Nota"),
               tuple(("2026-09-0%d" % (i + 1), D("1545.5000"), "x") for i in range(filas)))


class FakeGoogle:
    """Records every request and answers like the Sheets API does for a spreadsheet with some tabs."""

    def __init__(self, existentes=(), respuestas=None):
        self.existentes = {nombre: 100 + i for i, nombre in enumerate(existentes)}
        self.pedidos: list[httpx.Request] = []
        self.respuestas = list(respuestas or [])  # forced answers, consumed in order, before the normal ones

    def __call__(self, pedido: httpx.Request) -> httpx.Response:
        self.pedidos.append(pedido)
        if self.respuestas:
            forzada = self.respuestas.pop(0)
            if forzada is not None:
                return forzada
        url = str(pedido.url)
        if pedido.method == "GET":
            hojas = [{"properties": {"sheetId": i, "title": n, "gridProperties": {"rowCount": 1000, "columnCount": 26}}}
                     for n, i in self.existentes.items()]
            return httpx.Response(200, json={"sheets": hojas})
        cuerpo = json.loads(pedido.content)
        if url.endswith(f"{ID}:batchUpdate"):
            respuestas = []
            for peticion in cuerpo["requests"]:
                if "addSheet" in peticion:
                    titulo = peticion["addSheet"]["properties"]["title"]
                    self.existentes[titulo] = 500 + len(self.existentes)
                    respuestas.append({"addSheet": {"properties": {"sheetId": self.existentes[titulo], "title": titulo}}})
                else:
                    respuestas.append({})
            return httpx.Response(200, json={"spreadsheetId": ID, "replies": respuestas})
        if url.endswith("/values:batchClear"):
            return httpx.Response(200, json={"spreadsheetId": ID, "clearedRanges": cuerpo["ranges"]})
        if url.endswith("/values:batchUpdate"):
            return httpx.Response(200, json={"spreadsheetId": ID, "totalUpdatedSheets": len(cuerpo["data"])})
        return httpx.Response(404, json={"error": {"message": "no existe " + url}})

    def llamadas(self):
        return [(p.method, str(p.url).removeprefix(BASE)) for p in self.pedidos]

    def cuerpos(self, sufijo):
        return [json.loads(p.content) for p in self.pedidos if str(p.url).endswith(sufijo)]


def cliente(google, **extra):
    pausas = extra.pop("pausas", [])
    return ClienteGoogleSheets(
        ConfigSheets(ID, "{}"), transport=httpx.MockTransport(google), obtener_token=lambda: "token-de-prueba",
        pausa=pausas.append, **extra,
    )


# --- Behaviour of one sync -----------------------------------------------------------------------------------

def test_the_fake_and_the_real_client_share_the_protocol():
    assert hasattr(ClienteGoogleSheets, "reemplazar_pestanas")
    assert isinstance(cliente(FakeGoogle()), SheetsClient)


def test_requests_go_in_order_read_structure_clear_write():
    google = FakeGoogle(existentes=["Dolar"])
    cliente(google).reemplazar_pestanas([tab("Dolar"), tab("Precios")])
    assert [(m, ruta.split("?")[0]) for m, ruta in google.llamadas()] == [
        ("GET", ""), ("POST", ":batchUpdate"), ("POST", "/values:batchClear"), ("POST", "/values:batchUpdate"),
    ]


def test_every_request_carries_the_bearer_token_and_nothing_else_secret():
    google = FakeGoogle()
    cliente(google).reemplazar_pestanas([tab()])
    assert {p.headers["authorization"] for p in google.pedidos} == {"Bearer token-de-prueba"}


def test_a_missing_tab_is_created_with_the_header_row_frozen():
    google = FakeGoogle(existentes=[])
    cliente(google).reemplazar_pestanas([tab("Dolar", filas=3)])
    (estructura,) = google.cuerpos(f"{ID}:batchUpdate")
    (peticion,) = estructura["requests"]
    propiedades = peticion["addSheet"]["properties"]
    assert propiedades["title"] == "Dolar"
    assert propiedades["gridProperties"] == {"rowCount": 4, "columnCount": 3, "frozenRowCount": 1}


def test_an_existing_tab_is_resized_and_frozen_not_recreated():
    google = FakeGoogle(existentes=["Dolar"])
    cliente(google).reemplazar_pestanas([tab("Dolar", filas=5)])
    (estructura,) = google.cuerpos(f"{ID}:batchUpdate")
    (peticion,) = estructura["requests"]
    assert "addSheet" not in peticion
    cambio = peticion["updateSheetProperties"]
    assert cambio["properties"]["sheetId"] == 100
    assert cambio["properties"]["gridProperties"] == {"rowCount": 6, "columnCount": 3, "frozenRowCount": 1}
    assert set(cambio["fields"].split(",")) == {
        "gridProperties.rowCount", "gridProperties.columnCount", "gridProperties.frozenRowCount"}


def test_a_tab_without_rows_still_keeps_one_scrollable_row_below_the_frozen_header():
    google = FakeGoogle(existentes=["Dolar"])
    cliente(google).reemplazar_pestanas([tab("Dolar", filas=0)])
    (estructura,) = google.cuerpos(f"{ID}:batchUpdate")
    assert estructura["requests"][0]["updateSheetProperties"]["properties"]["gridProperties"]["rowCount"] == 2


def test_the_tabs_are_cleared_whole_then_written_raw_with_exact_ranges():
    google = FakeGoogle(existentes=["Dolar", "Precios"])
    cliente(google).reemplazar_pestanas([tab("Dolar", filas=2), tab("Precios", filas=0)])
    (limpiar,) = google.cuerpos("/values:batchClear")
    assert limpiar == {"ranges": ["'Dolar'", "'Precios'"]}
    (escribir,) = google.cuerpos("/values:batchUpdate")
    assert escribir["valueInputOption"] == "RAW"
    assert [d["range"] for d in escribir["data"]] == ["'Dolar'!A1:C3", "'Precios'!A1:C1"]
    assert all(d["majorDimension"] == "ROWS" for d in escribir["data"])
    assert escribir["data"][0]["values"][0] == ["Fecha", "ARS por USD", "Nota"]
    assert len(escribir["data"][0]["values"]) == 3


def test_wide_tabs_use_double_letter_columns():
    google = FakeGoogle(existentes=["Catalogo"])
    ancho = Tab("Catalogo", tuple(f"C{i}" for i in range(30)), (tuple("x" for _ in range(30)),))
    cliente(google).reemplazar_pestanas([ancho])
    (escribir,) = google.cuerpos("/values:batchUpdate")
    assert escribir["data"][0]["range"] == "'Catalogo'!A1:AD2"


def test_decimals_travel_as_exact_json_numbers_and_text_as_strings():
    google = FakeGoogle(existentes=["Dolar"])
    fila = ("2026-09-01", D("1234567890123.4567"), "=no es formula")
    cliente(google).reemplazar_pestanas([Tab("Dolar", ("a", "b", "c"), (fila,))])
    crudo = [p.content for p in google.pedidos if str(p.url).endswith("/values:batchUpdate")][0].decode()
    assert "1234567890123.4567" in crudo and '"1234567890123.4567"' not in crudo
    (escribir,) = google.cuerpos("/values:batchUpdate")
    assert escribir["data"][0]["values"][1][0] == "2026-09-01" and escribir["data"][0]["values"][1][2] == "=no es formula"


def test_non_finite_decimals_are_written_as_text_not_as_invalid_json():
    google = FakeGoogle(existentes=["Dolar"])
    cliente(google).reemplazar_pestanas([Tab("Dolar", ("a",), ((D("NaN"),),))])
    (escribir,) = google.cuerpos("/values:batchUpdate")
    assert escribir["data"][0]["values"][1] == ["NaN"]


def test_it_never_deletes_a_tab_and_never_touches_the_ones_that_are_not_ours():
    google = FakeGoogle(existentes=["Dolar", "Hoja de la dueña", "Notas"])
    cliente(google).reemplazar_pestanas([tab("Dolar")])
    for pedido in google.pedidos:
        assert b"deleteSheet" not in pedido.content
        assert b"Hoja de la due" not in pedido.content and b"Notas" not in pedido.content
        assert pedido.method in ("GET", "POST")
    assert set(google.existentes) == {"Dolar", "Hoja de la dueña", "Notas"}


def test_a_tab_outside_the_fixed_list_is_refused_before_any_request():
    google = FakeGoogle()
    with pytest.raises(ErrorDeSheets) as error:
        cliente(google).reemplazar_pestanas([tab("Dolar"), tab("Hoja1")])
    assert google.pedidos == []
    assert "Hoja1" in error.value.mensaje


def test_the_fixed_list_has_every_tab_the_export_builds():
    assert "Info" in NOMBRES_DE_PESTANAS and "Calidad" in NOMBRES_DE_PESTANAS


def test_a_duplicated_tab_name_is_refused():
    with pytest.raises(ErrorDeSheets):
        cliente(FakeGoogle()).reemplazar_pestanas([tab("Dolar"), tab("Dolar")])


def test_with_nothing_to_write_it_does_nothing():
    google = FakeGoogle()
    cliente(google).reemplazar_pestanas([])
    assert google.pedidos == []


# --- Retries and error mapping ------------------------------------------------------------------------------

def test_a_429_is_retried_with_backoff_and_then_succeeds():
    google = FakeGoogle(existentes=["Dolar"], respuestas=[httpx.Response(429), httpx.Response(429), None])
    pausas: list[float] = []
    cliente(google, pausas=pausas).reemplazar_pestanas([tab("Dolar")])
    assert len(pausas) == 2 and pausas[1] > pausas[0] > 0
    assert [m for m, _ in google.llamadas()].count("GET") == 3  # the first read was attempted three times


def test_retry_after_is_honoured_when_longer_than_the_backoff():
    google = FakeGoogle(existentes=["Dolar"], respuestas=[httpx.Response(429, headers={"retry-after": "17"}), None])
    pausas: list[float] = []
    cliente(google, pausas=pausas).reemplazar_pestanas([tab("Dolar")])
    assert pausas == [17]


def test_a_5xx_is_retried():
    google = FakeGoogle(existentes=["Dolar"], respuestas=[httpx.Response(503), None])
    pausas: list[float] = []
    cliente(google, pausas=pausas).reemplazar_pestanas([tab("Dolar")])
    assert len(pausas) == 1


def test_a_network_error_is_retried_then_mapped_without_the_raw_exception():
    def caido(pedido):
        raise httpx.ConnectError("boom " + MARCADOR_SECRETO)

    pausas: list[float] = []
    sheets = ClienteGoogleSheets(ConfigSheets(ID, "{}"), transport=httpx.MockTransport(caido),
                                 obtener_token=lambda: "t", pausa=pausas.append, max_intentos=3)
    with pytest.raises(ErrorDeSheets) as error:
        sheets.reemplazar_pestanas([tab()])
    assert len(pausas) == 2
    assert MARCADOR_SECRETO not in error.value.mensaje and MARCADOR_SECRETO not in repr(error.value)
    assert error.value.__cause__ is None and error.value.__suppress_context__


def test_it_gives_up_after_the_attempts_with_a_clear_message():
    google = FakeGoogle(respuestas=[httpx.Response(429)] * 10)
    with pytest.raises(ErrorDeSheets) as error:
        cliente(google, max_intentos=3).reemplazar_pestanas([tab()])
    assert error.value.estado == 429
    assert "límite" in error.value.mensaje.lower()
    assert len(google.pedidos) == 3


@pytest.mark.parametrize("estado, fragmento", [
    (403, "compartiste"), (401, "credenciales"), (404, "GOOGLE_SHEETS_SPREADSHEET_ID"), (400, "rechazó"),
])
def test_client_errors_are_not_retried_and_have_their_own_message(estado, fragmento):
    google = FakeGoogle(respuestas=[httpx.Response(estado, json={"error": {"message": MARCADOR_SECRETO}})])
    pausas: list[float] = []
    with pytest.raises(ErrorDeSheets) as error:
        cliente(google, pausas=pausas).reemplazar_pestanas([tab()])
    assert pausas == [] and len(google.pedidos) == 1
    assert fragmento in error.value.mensaje
    assert error.value.estado == estado
    assert MARCADOR_SECRETO not in error.value.mensaje  # Google's own text is never relayed


def test_5xx_after_the_attempts_says_google_is_failing():
    google = FakeGoogle(respuestas=[httpx.Response(500)] * 10)
    with pytest.raises(ErrorDeSheets) as error:
        cliente(google, max_intentos=2).reemplazar_pestanas([tab()])
    assert "Google" in error.value.mensaje and error.value.estado == 500


# --- Configuration and secrets ---------------------------------------------------------------------------------

def test_config_comes_only_from_the_two_env_vars():
    assert leer_config({}) is None
    assert leer_config({"GOOGLE_SHEETS_SPREADSHEET_ID": ID}) is None
    assert leer_config({"GOOGLE_SERVICE_ACCOUNT_JSON": "{}"}) is None
    assert leer_config({"GOOGLE_SHEETS_SPREADSHEET_ID": "  ", "GOOGLE_SERVICE_ACCOUNT_JSON": "{}"}) is None
    config = leer_config({"GOOGLE_SHEETS_SPREADSHEET_ID": ID, "GOOGLE_SERVICE_ACCOUNT_JSON": "{}"})
    assert config.spreadsheet_id == ID


def test_missing_variables_are_listed_by_name_only():
    assert faltantes({}) == ["GOOGLE_SHEETS_SPREADSHEET_ID", "GOOGLE_SERVICE_ACCOUNT_JSON"]
    assert faltantes({"GOOGLE_SHEETS_SPREADSHEET_ID": ID}) == ["GOOGLE_SERVICE_ACCOUNT_JSON"]
    assert faltantes({"GOOGLE_SHEETS_SPREADSHEET_ID": ID, "GOOGLE_SERVICE_ACCOUNT_JSON": "{}"}) == []


def test_the_credential_is_in_no_repr_or_str():
    config = ConfigSheets(ID, '{"private_key": "%s"}' % MARCADOR_SECRETO)
    assert MARCADOR_SECRETO not in repr(config) and MARCADOR_SECRETO not in str(config)
    sheets = ClienteGoogleSheets(config, transport=httpx.MockTransport(FakeGoogle()), obtener_token=lambda: "t")
    assert MARCADOR_SECRETO not in repr(sheets) and MARCADOR_SECRETO not in str(sheets)


@pytest.mark.parametrize("malo", ["no es json " + MARCADOR_SECRETO, "[]", '"texto"', "{}", '{"client_email": "a@b"}'])
def test_an_unusable_credential_gives_a_safe_error_that_does_not_echo_it(malo):
    sheets = ClienteGoogleSheets(ConfigSheets(ID, malo), transport=httpx.MockTransport(FakeGoogle()))
    with pytest.raises(ErrorDeSheets) as error:
        sheets.reemplazar_pestanas([tab()])
    assert "GOOGLE_SERVICE_ACCOUNT_JSON" in error.value.mensaje
    assert MARCADOR_SECRETO not in error.value.mensaje and MARCADOR_SECRETO not in repr(error.value)


@pytest.mark.parametrize("id_malo", ["", "a/b", "../x", "abc?x=1", "a b", "id:batchUpdate"])
def test_a_spreadsheet_id_that_is_not_an_id_is_refused_before_any_request(id_malo):
    google = FakeGoogle()
    sheets = ClienteGoogleSheets(ConfigSheets(id_malo, "{}"), transport=httpx.MockTransport(google), obtener_token=lambda: "t")
    with pytest.raises(ErrorDeSheets) as error:
        sheets.reemplazar_pestanas([tab()])
    assert google.pedidos == [] and "GOOGLE_SHEETS_SPREADSHEET_ID" in error.value.mensaje


def test_nothing_secret_is_logged_even_on_failure(caplog):
    caplog.set_level(logging.DEBUG)
    google = FakeGoogle(respuestas=[httpx.Response(403, json={"error": {"message": MARCADOR_SECRETO}})])
    config = ConfigSheets(ID, '{"private_key": "%s"}' % MARCADOR_SECRETO)
    sheets = ClienteGoogleSheets(config, transport=httpx.MockTransport(google), obtener_token=lambda: "token-secreto-2")
    with pytest.raises(ErrorDeSheets):
        sheets.reemplazar_pestanas([tab()])
    texto = caplog.text
    assert MARCADOR_SECRETO not in texto and "token-secreto-2" not in texto and "Bearer" not in texto


def test_crear_cliente_needs_the_configuration():
    with pytest.raises(ErrorDeSheets) as error:
        crear_cliente({})
    assert "GOOGLE_SHEETS_SPREADSHEET_ID" in error.value.mensaje
    assert isinstance(crear_cliente({"GOOGLE_SHEETS_SPREADSHEET_ID": ID, "GOOGLE_SERVICE_ACCOUNT_JSON": "{}"}), ClienteGoogleSheets)


# --- Service-account authentication (JWT exchange against a fake token endpoint) -----------------------------

def cuenta_de_servicio():
    clave = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pem = clave.private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()).decode()
    return {
        "type": "service_account", "project_id": "p", "private_key_id": "k1", "private_key": pem,
        "client_email": "sync@p.iam.gserviceaccount.com", "client_id": "1", "token_uri": "https://token.invalid/token",
    }


def test_the_jwt_assertion_is_exchanged_for_a_token_that_then_authorizes_the_calls():
    google = FakeGoogle(existentes=["Dolar"])
    intercambios = []

    def ruteador(pedido: httpx.Request) -> httpx.Response:
        if str(pedido.url) == "https://token.invalid/token":
            intercambios.append(pedido)
            return httpx.Response(200, json={"access_token": "ya29.token-falso", "expires_in": 3600, "token_type": "Bearer"})
        return google(pedido)

    cuenta = cuenta_de_servicio()
    sheets = ClienteGoogleSheets(ConfigSheets(ID, json.dumps(cuenta)), transport=httpx.MockTransport(ruteador))
    sheets.reemplazar_pestanas([tab("Dolar")])
    assert len(intercambios) == 1  # one exchange for the whole run
    cuerpo = intercambios[0].content.decode()
    assert "grant_type=urn%3Aietf%3Aparams%3Aoauth%3Agrant-type%3Ajwt-bearer" in cuerpo and "assertion=" in cuerpo
    assert {p.headers["authorization"] for p in google.pedidos} == {"Bearer ya29.token-falso"}
    assert cuenta["private_key"] not in cuerpo


def test_a_rejected_token_exchange_is_a_safe_authentication_error(caplog):
    caplog.set_level(logging.DEBUG)

    def ruteador(pedido: httpx.Request) -> httpx.Response:
        if "token.invalid" in str(pedido.url):
            return httpx.Response(400, json={"error": "invalid_grant", "error_description": MARCADOR_SECRETO})
        raise AssertionError("must not reach the Sheets API without a token")

    cuenta = cuenta_de_servicio()
    sheets = ClienteGoogleSheets(ConfigSheets(ID, json.dumps(cuenta)), transport=httpx.MockTransport(ruteador))
    with pytest.raises(ErrorDeSheets) as error:
        sheets.reemplazar_pestanas([tab()])
    assert "credenciales" in error.value.mensaje
    assert MARCADOR_SECRETO not in error.value.mensaje and cuenta["private_key"] not in caplog.text
    assert MARCADOR_SECRETO not in caplog.text


def test_the_scope_asked_is_only_spreadsheets():
    assert sheets_client.SCOPES == ("https://www.googleapis.com/auth/spreadsheets",)
