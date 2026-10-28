"""Official BNA dollar quote, read from the public page https://www.bna.com.ar/Personas.

`parse_bna` is pure (page text in, quote out); `descargar_bna` is the only function that touches the network.
Nothing here reads the database. Every error is a `BnaError` with a fixed Spanish message: the page text, the
URL details and the library errors never travel in it, because the message ends up in the API answer.
"""

import re
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from html.parser import HTMLParser

import httpx

URL_BNA = "https://www.bna.com.ar/Personas"
TIMEOUT_SEGUNDOS = 15.0
MAX_BYTES = 5_000_000
USER_AGENT = "CasaLopezCostos/1.0 (+actualizacion del dolar BNA)"
# Exclusive upper bound of a believable quote; it also keeps the value inside NUMERIC(12,4).
MAX_COTIZACION = Decimal("100000000")

PANEL = "billetes"
CELDA_FECHA = "fechacot"
FILA = "dolar u.s.a"

MENSAJE_NO_DISPONIBLE = "No se pudo consultar al Banco Nación. Probá de nuevo en un rato."
MENSAJE_ESTRUCTURA = "La página del Banco Nación cambió y no se pudo leer el dólar. Avisá al equipo."
MENSAJE_FECHA = "La fecha de la cotización del Banco Nación no es válida."
MENSAJE_VALORES = "Los valores del dólar del Banco Nación no son válidos."


class BnaError(Exception):
    """The BNA quote could not be fetched or read. `str(error)` is safe to show to the user."""


@dataclass(frozen=True)
class CotizacionBna:
    fecha: date
    compra: Decimal
    venta: Decimal


class _TablaBilletes(HTMLParser):
    """Collects the first table of the `billetes` pane: the `fechaCot` header and the text of every row."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.fecha: str | None = None
        self.filas: list[list[str]] = []
        self._profundidad = 0  # open <div>s since the pane started; 0 = outside the pane
        self._fin = False
        self._tabla = False
        self._celda: list[str] | None = None
        self._es_fecha = False

    def handle_starttag(self, tag, attrs):
        if self._fin:
            return
        atributos = dict(attrs)
        if self._profundidad == 0:
            if tag == "div" and atributos.get("id") == PANEL:
                self._profundidad = 1
            return
        if tag == "div":
            self._profundidad += 1
        elif tag == "table" and not self._tabla:
            self._tabla = True
        elif self._tabla and tag == "tr":
            self.filas.append([])
        elif self._tabla and tag in ("td", "th"):
            self._celda = []
            clases = (atributos.get("class") or "").lower().split()
            self._es_fecha = tag == "th" and CELDA_FECHA in clases

    def handle_endtag(self, tag):
        if self._fin or self._profundidad == 0:
            return
        if tag == "div":
            self._profundidad -= 1
            if self._profundidad == 0:
                self._fin = True
        elif tag == "table" and self._tabla:
            self._fin = True
        elif tag in ("td", "th") and self._celda is not None:
            texto = " ".join("".join(self._celda).split())
            if self._es_fecha and self.fecha is None:
                self.fecha = texto
            elif self.filas:
                self.filas[-1].append(texto)
            self._celda = None
            self._es_fecha = False

    def handle_data(self, data):
        if self._celda is not None and not self._fin:
            self._celda.append(data)


def parse_bna(html: str) -> CotizacionBna:
    """Reads date, buy and sell of the "Dolar U.S.A" row of the `billetes` pane. Raises `BnaError` otherwise."""
    lector = _TablaBilletes()
    try:
        lector.feed(html)
        lector.close()
    except Exception:  # noqa: BLE001 - the parser's own message may quote the page
        raise BnaError(MENSAJE_ESTRUCTURA) from None
    if lector.fecha is None:
        raise BnaError(MENSAJE_ESTRUCTURA)
    fila = next((f for f in lector.filas if len(f) >= 3 and " ".join(f[0].lower().split()) == FILA), None)
    if fila is None:
        raise BnaError(MENSAJE_ESTRUCTURA)
    return CotizacionBna(fecha=_fecha(lector.fecha), compra=_importe(fila[1]), venta=_importe(fila[2]))


def _fecha(texto: str) -> date:
    if not re.fullmatch(r"\d{2}/\d{2}/\d{4}", texto):
        raise BnaError(MENSAJE_FECHA)
    try:
        return datetime.strptime(texto, "%d/%m/%Y").date()
    except ValueError:
        raise BnaError(MENSAJE_FECHA) from None


def _importe(texto: str) -> Decimal:
    """`1.560,50`, `1560,00`, `1560.50` and `1.560` (thousands) to Decimal, never through float."""
    texto = texto.strip()
    if re.fullmatch(r"\d{1,3}(\.\d{3})+(,\d+)?", texto):
        normal = texto.replace(".", "").replace(",", ".")
    elif re.fullmatch(r"\d+(,\d+)?", texto):
        normal = texto.replace(",", ".")
    elif re.fullmatch(r"\d+\.\d+", texto):
        normal = texto
    else:
        raise BnaError(MENSAJE_VALORES)
    try:
        valor = Decimal(normal)
    except InvalidOperation:
        raise BnaError(MENSAJE_VALORES) from None
    if not 0 < valor < MAX_COTIZACION:
        raise BnaError(MENSAJE_VALORES)
    return valor


def descargar_bna(client: httpx.Client | None = None) -> str:
    """Downloads the BNA page. Any network or HTTP failure becomes a `BnaError` with a fixed message."""
    propio = client is None
    cliente = httpx.Client(follow_redirects=True) if propio else client
    try:
        respuesta = cliente.get(URL_BNA, headers={"User-Agent": USER_AGENT}, timeout=TIMEOUT_SEGUNDOS)
        respuesta.raise_for_status()
        if len(respuesta.content) > MAX_BYTES:
            raise BnaError(MENSAJE_NO_DISPONIBLE)
        return respuesta.text
    except httpx.HTTPError:
        raise BnaError(MENSAJE_NO_DISPONIBLE) from None
    finally:
        if propio:
            cliente.close()
