"""Google Sheets API v4 client for the display copy (T6). One-way: the app writes, nothing is ever read back.

Service-account authentication goes through `google-auth` (it signs the JWT and exchanges it for a token); every HTTP
call, including that exchange, goes through `httpx` so tests can play Google with `httpx.MockTransport`.

Configuration comes ONLY from two environment variables. `GOOGLE_SERVICE_ACCOUNT_JSON` holds the JSON content itself
(never a path); it is never logged, never put in a repr and never returned by an endpoint. Errors reaching the caller
carry a fixed Spanish message: Google's own error text and the underlying exceptions are dropped on purpose.

Per run (see `reemplazar_pestanas`): read which tabs exist, create the missing ones / resize and freeze the header row of
the others (one `spreadsheets.batchUpdate`), clear the values of our tabs (`values:batchClear`) and write them
(`values:batchUpdate`, RAW). It only ever touches the tabs in `NOMBRES_DE_PESTANAS` and never deletes a tab.
SUPUESTO: validar. Clear and write are two calls, so a failure between them leaves the tabs empty until the next sync;
that is acceptable for a display-only copy.
"""

import json
import logging
import os
import re
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Protocol, runtime_checkable

import google.auth.exceptions
import google.auth.transport
import httpx
from google.oauth2 import service_account

from backend.sheets_export import NOMBRES_DE_PESTANAS, Tab

# Audit lines go to uvicorn's logger (the app's root logger is left at WARNING). Only counts and tab names are logged.
logger = logging.getLogger("uvicorn.error")

VARIABLE_ID = "GOOGLE_SHEETS_SPREADSHEET_ID"
VARIABLE_CREDENCIAL = "GOOGLE_SERVICE_ACCOUNT_JSON"
VARIABLES = (VARIABLE_ID, VARIABLE_CREDENCIAL)
SCOPES = ("https://www.googleapis.com/auth/spreadsheets",)
API = "https://sheets.googleapis.com/v4/spreadsheets"
ESTADOS_CON_REINTENTO = frozenset({429, 500, 502, 503, 504})
MAX_INTENTOS = 5
ESPERA_BASE = 1.0  # seconds; doubles on every retry
ESPERA_MAXIMA = 30.0
RETRY_AFTER_MAXIMO = 60.0
TIMEOUT = 30.0
_ID_VALIDO = re.compile(r"^[A-Za-z0-9_-]+$")
_CAMPOS_DE_GRILLA = "gridProperties.rowCount,gridProperties.columnCount,gridProperties.frozenRowCount"


class ErrorDeSheets(Exception):
    """A failure talking to Google, with a message that is safe to show to the user (never a credential)."""

    def __init__(self, mensaje: str, estado: int | None = None):
        super().__init__(mensaje)
        self.mensaje = mensaje
        self.estado = estado

    def __str__(self) -> str:
        return self.mensaje


@dataclass(frozen=True)
class ConfigSheets:
    spreadsheet_id: str
    credenciales_json: str = field(repr=False)


@runtime_checkable
class SheetsClient(Protocol):
    def reemplazar_pestanas(self, tabs: Sequence[Tab]) -> None:
        """Replace the values of each tab with its headers and rows. Never touches a tab that is not in `tabs`."""
        ...


def leer_config(env: Mapping[str, str] | None = None) -> ConfigSheets | None:
    """The configuration, or None while either variable is missing or blank."""
    env = os.environ if env is None else env
    valores = [(env.get(nombre) or "").strip() for nombre in VARIABLES]
    return ConfigSheets(*valores) if all(valores) else None


def faltantes(env: Mapping[str, str] | None = None) -> list[str]:
    """Names (never values) of the variables that are missing or blank."""
    env = os.environ if env is None else env
    return [nombre for nombre in VARIABLES if not (env.get(nombre) or "").strip()]


def crear_cliente(env: Mapping[str, str] | None = None) -> "ClienteGoogleSheets":
    config = leer_config(env)
    if config is None:
        raise ErrorDeSheets("Falta configurar " + " y ".join(faltantes(env)) + ".")
    return ClienteGoogleSheets(config)


# --- Authentication: google-auth over httpx ------------------------------------------------------------------

class _RespuestaHttpx(google.auth.transport.Response):
    def __init__(self, respuesta: httpx.Response):
        self._respuesta = respuesta

    @property
    def status(self):
        return self._respuesta.status_code

    @property
    def headers(self):
        return self._respuesta.headers

    @property
    def data(self):
        return self._respuesta.content


class _SolicitudHttpx(google.auth.transport.Request):
    """Lets google-auth make its token request with our httpx client (so it uses the same transport)."""

    def __init__(self, http: httpx.Client):
        self._http = http

    def __call__(self, url, method="GET", body=None, headers=None, timeout=None, **kwargs):
        try:
            respuesta = self._http.request(method, url, content=body, headers=headers, timeout=timeout or TIMEOUT)
        except httpx.HTTPError:
            raise google.auth.exceptions.TransportError("No se pudo conectar con el servidor de tokens.") from None
        return _RespuestaHttpx(respuesta)


# --- Request building ------------------------------------------------------------------------------------------

def _a1(nombre: str) -> str:
    return "'" + nombre.replace("'", "''") + "'"


def _columna(numero: int) -> str:
    """1 -> A, 26 -> Z, 27 -> AA."""
    letras = ""
    while numero > 0:
        numero, resto = divmod(numero - 1, 26)
        letras = chr(65 + resto) + letras
    return letras


def _json_celda(valor: object) -> str:
    # A Decimal becomes a JSON number written from its exact digits, never through float. SUPUESTO: validar. Google parses
    # it into a double, which is fine because the Sheet is display only.
    if isinstance(valor, Decimal):
        return format(valor, "f") if valor.is_finite() else json.dumps(str(valor))
    return json.dumps(valor, ensure_ascii=False)


def _cuerpo_de_valores(tabs: Sequence[Tab]) -> bytes:
    bloques = []
    for tab in tabs:
        filas = [tab.headers, *tab.rows]
        valores = ",".join("[" + ",".join(_json_celda(c) for c in fila) + "]" for fila in filas)
        rango = f"{_a1(tab.name)}!A1:{_columna(len(tab.headers))}{len(filas)}"
        bloques.append(f'{{"range":{json.dumps(rango, ensure_ascii=False)},"majorDimension":"ROWS","values":[{valores}]}}')
    return ('{"valueInputOption":"RAW","data":[' + ",".join(bloques) + "]}").encode()


def _grilla(tab: Tab) -> dict:
    # A frozen header needs at least one more row under it, hence the minimum of 2 rows.
    return {"rowCount": max(len(tab.rows) + 1, 2), "columnCount": max(len(tab.headers), 1), "frozenRowCount": 1}


def _mensaje_para(estado: int) -> str:
    if estado == 400:
        return "Google rechazó los datos enviados (400). Revisá el Sheet y volvé a intentar."
    if estado == 401:
        return f"Google no aceptó las credenciales de la cuenta de servicio. Revisá {VARIABLE_CREDENCIAL}."
    if estado == 403:
        return ("Google rechazó el acceso: la cuenta de servicio no tiene permiso sobre el Sheet. "
                "¿Lo compartiste con su email como editor? ¿Está habilitada la API de Google Sheets?")
    if estado == 404:
        return f"No se encontró el Sheet. Revisá {VARIABLE_ID} y que esté compartido con la cuenta de servicio."
    if estado == 429:
        return "Google alcanzó el límite de solicitudes. Esperá un minuto y volvé a intentar."
    if estado >= 500:
        return f"Google Sheets no respondió bien (error {estado}). Probá de nuevo en unos minutos."
    return f"Google respondió con un error inesperado ({estado})."


class ClienteGoogleSheets:
    """`SheetsClient` over the real API. `transport` and `obtener_token` exist for tests; `pausa` replaces `time.sleep`."""

    def __init__(
        self, config: ConfigSheets, *, transport: httpx.BaseTransport | None = None,
        obtener_token: Callable[[], str] | None = None, pausa: Callable[[float], None] = time.sleep,
        max_intentos: int = MAX_INTENTOS,
    ):
        self._config = config
        self._transport = transport
        self._obtener_token = obtener_token
        self._pausa = pausa
        self._max_intentos = max(1, max_intentos)
        self._token: str | None = None

    def __repr__(self) -> str:
        return f"{type(self).__name__}()"

    # -- public --

    def reemplazar_pestanas(self, tabs: Sequence[Tab]) -> None:
        if not _ID_VALIDO.fullmatch(self._config.spreadsheet_id):
            raise ErrorDeSheets(f"{VARIABLE_ID} no tiene el formato de un id de Google Sheets.")
        self._validar(tabs)
        if not tabs:
            return
        with httpx.Client(transport=self._transport, timeout=TIMEOUT, follow_redirects=False) as http:
            base = f"{API}/{self._config.spreadsheet_id}"
            existentes = self._pestanas_existentes(http, base)
            self._preparar_pestanas(http, base, tabs, existentes)
            self._pedir(http, "POST", f"{base}/values:batchClear", json_body={"ranges": [_a1(t.name) for t in tabs]})
            self._pedir(http, "POST", f"{base}/values:batchUpdate", contenido=_cuerpo_de_valores(tabs))
        logger.info("Sheets: %d pestañas reemplazadas (%d filas).", len(tabs), sum(len(t.rows) for t in tabs))

    # -- steps --

    @staticmethod
    def _validar(tabs: Sequence[Tab]) -> None:
        vistos: set[str] = set()
        for tab in tabs:
            if tab.name not in NOMBRES_DE_PESTANAS:
                raise ErrorDeSheets(f"La pestaña {tab.name!r} no está en la lista que la app puede escribir.")
            if tab.name in vistos:
                raise ErrorDeSheets(f"La pestaña {tab.name!r} está repetida.")
            vistos.add(tab.name)

    def _pestanas_existentes(self, http: httpx.Client, base: str) -> dict[str, int]:
        datos = self._pedir(http, "GET", base, params={"fields": "sheets.properties(sheetId,title)"})
        return {
            hoja["properties"]["title"]: hoja["properties"]["sheetId"]
            for hoja in datos.get("sheets", []) if "properties" in hoja
        }

    def _preparar_pestanas(self, http: httpx.Client, base: str, tabs: Sequence[Tab], existentes: dict[str, int]) -> None:
        peticiones = []
        for tab in tabs:
            if tab.name in existentes:
                peticiones.append({"updateSheetProperties": {
                    "properties": {"sheetId": existentes[tab.name], "gridProperties": _grilla(tab)},
                    "fields": _CAMPOS_DE_GRILLA,
                }})
            else:
                peticiones.append({"addSheet": {"properties": {"title": tab.name, "gridProperties": _grilla(tab)}}})
        self._pedir(http, "POST", f"{base}:batchUpdate", json_body={"requests": peticiones})

    # -- HTTP --

    def _token_de_acceso(self, http: httpx.Client) -> str:
        if self._obtener_token is not None:
            return self._obtener_token()
        if self._token is None:
            self._token = self._pedir_token(http)
        return self._token

    def _pedir_token(self, http: httpx.Client) -> str:
        try:
            info = json.loads(self._config.credenciales_json)
            if not isinstance(info, dict):
                raise ValueError
            credenciales = service_account.Credentials.from_service_account_info(info, scopes=list(SCOPES))
        except Exception:  # noqa: BLE001 - whatever is wrong with the JSON, never echo any of it
            raise ErrorDeSheets(f"{VARIABLE_CREDENCIAL} no es el JSON de una cuenta de servicio válida.") from None
        try:
            credenciales.refresh(_SolicitudHttpx(http))
        except google.auth.exceptions.TransportError:
            raise ErrorDeSheets("No se pudo conectar con Google para autenticar la cuenta de servicio.") from None
        except Exception:  # noqa: BLE001 - RefreshError and anything else from the library
            raise ErrorDeSheets(
                f"Google no aceptó las credenciales de la cuenta de servicio. Revisá {VARIABLE_CREDENCIAL}.", 401,
            ) from None
        if not credenciales.token:
            raise ErrorDeSheets(f"Google no entregó un token. Revisá {VARIABLE_CREDENCIAL}.", 401)
        return credenciales.token

    def _espera(self, intento: int, respuesta: httpx.Response | None) -> float:
        espera = min(ESPERA_BASE * 2 ** (intento - 1), ESPERA_MAXIMA)
        indicada = respuesta.headers.get("retry-after") if respuesta is not None else None
        try:
            if indicada is not None:
                espera = max(espera, min(float(indicada), RETRY_AFTER_MAXIMO))
        except ValueError:
            pass  # the HTTP-date form: the backoff is enough
        return espera

    def _pedir(
        self, http: httpx.Client, metodo: str, url: str, *, params: dict | None = None, json_body: dict | None = None,
        contenido: bytes | None = None,
    ) -> dict:
        token = self._token_de_acceso(http)
        cabeceras = {"authorization": f"Bearer {token}", "accept": "application/json"}
        if contenido is not None:
            cabeceras["content-type"] = "application/json"
            argumentos: dict = {"content": contenido}
        else:
            argumentos = {"json": json_body} if json_body is not None else {}
        for intento in range(1, self._max_intentos + 1):
            ultimo = intento == self._max_intentos
            try:
                respuesta = http.request(metodo, url, params=params, headers=cabeceras, **argumentos)
            except httpx.HTTPError:
                if ultimo:
                    raise ErrorDeSheets("No se pudo conectar con Google Sheets.") from None
                self._pausa(self._espera(intento, None))
                continue
            if respuesta.status_code in ESTADOS_CON_REINTENTO and not ultimo:
                self._pausa(self._espera(intento, respuesta))
                continue
            if respuesta.status_code >= 400:
                raise ErrorDeSheets(_mensaje_para(respuesta.status_code), respuesta.status_code)
            try:
                datos = respuesta.json()
            except ValueError:
                raise ErrorDeSheets("Google respondió algo que no se pudo leer.", respuesta.status_code) from None
            return datos if isinstance(datos, dict) else {}
        raise AssertionError("unreachable")  # pragma: no cover - the last attempt always returns or raises
