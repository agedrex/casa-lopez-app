"""Display copy of the app's data for the Google Sheet (T6).

The Sheet is DISPLAY ONLY: the app calculates everything (costing stays in costeo.py / receta.py, reached through
`servicios`), pushes plain values and never reads anything back. Nothing here touches the network or the clock:
`construir_tabs` reads from a `Fuente` and formats; the caller passes `generado_en` and the app version.

Cell rules: Decimal stays exact (only the API-write boundary of sheets_client.py turns it into a JSON number;
SUPUESTO: validar, that boundary is display-only), dates are ISO `YYYY-MM-DD`, booleans are SI / NO, None is an empty
string, and text that a spreadsheet could read as a formula (`= + - @`) gets a single quote in front.
Headers are the column names of the plantilla v4.1 (sheet Diccionario, "Columna en el Excel").
"""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Protocol

from sqlalchemy.orm import Session

from backend import servicios

NOTA_DE_INFO = "Vista generada por la app. No editar: se pisa en cada sincronización."
MAX_CELDA = 50_000  # Google Sheets rejects cells with more than 50,000 characters
_INICIOS_PELIGROSOS = ("=", "+", "-", "@", "\t", "\r")
_ETAPAS = ("CUERO", "FORRO", "FLEX", "GOMA_EVA", "HERRAJES", "HILO_CEMENTO", "CORTE", "CONFECCION")

Celda = str | Decimal


@dataclass(frozen=True)
class Tab:
    name: str
    headers: tuple[str, ...]
    rows: tuple[tuple[Celda, ...], ...]


class Fuente(Protocol):
    """Where the tabs get their data. `FuenteSQL` in production; tests use literals with the same shapes."""

    def productos_costeados(self) -> list[dict]: ...
    def cotizaciones(self) -> list[dict]: ...
    def productos(self) -> list[dict]: ...
    def modelos(self) -> list[dict]: ...
    def precios(self, hoy: date) -> list[dict]: ...
    def dolar(self) -> list[dict]: ...
    def ordenes(self) -> list[dict]: ...
    def costos_fijos(self) -> list[dict]: ...
    def talleres(self) -> list[dict]: ...
    def parametros(self) -> list[dict]: ...
    def materiales(self) -> list[dict]: ...
    def calidad(self, hoy: date) -> dict: ...


class FuenteSQL:
    """The `servicios` loaders over one session. Each is read once per instance (Lotes and Lote_Productos share one)."""

    def __init__(self, session: Session):
        self._session = session
        self._guardado: dict[str, object] = {}

    def _una_vez(self, clave: str, cargar: Callable[[], object]):
        if clave not in self._guardado:
            self._guardado[clave] = cargar()
        return self._guardado[clave]

    def productos_costeados(self) -> list[dict]:
        return self._una_vez("costeados", lambda: servicios.productos_costeados(self._session))

    def cotizaciones(self) -> list[dict]:
        nombres = {p["codigo"]: p["nombre"] for p in self.productos_costeados()}
        return self._una_vez("cotizaciones", lambda: servicios.cotizaciones_guardadas(self._session, nombres))

    def productos(self) -> list[dict]:
        return self._una_vez("productos", lambda: servicios.productos_para_exportar(self._session))

    def modelos(self) -> list[dict]:
        return self._una_vez("modelos", lambda: servicios.modelos_para_exportar(self._session))

    def precios(self, hoy: date) -> list[dict]:
        return self._una_vez("precios", lambda: servicios.listar_precios(self._session, a_fecha=hoy))

    def dolar(self) -> list[dict]:
        return self._una_vez("dolar", lambda: servicios.listar_dolar(self._session))

    def ordenes(self) -> list[dict]:
        return self._una_vez("ordenes", lambda: servicios.listar_ordenes(self._session))

    def costos_fijos(self) -> list[dict]:
        return self._una_vez("fijos", lambda: servicios.costos_fijos_de_todos_los_periodos(self._session))

    def talleres(self) -> list[dict]:
        return self._una_vez("talleres", lambda: servicios.listar_talleres(self._session))

    def parametros(self) -> list[dict]:
        return self._una_vez("parametros", lambda: servicios.listar_parametros(self._session))

    def materiales(self) -> list[dict]:
        return self._una_vez("materiales", lambda: servicios.listar_materiales(self._session))

    def calidad(self, hoy: date) -> dict:
        return self._una_vez("calidad", lambda: servicios.calidad_de_datos(self._session, hoy))


# --- Cells --------------------------------------------------------------------------------------------------

def texto_seguro(texto: str) -> str:
    """Quote text that starts like a formula, and cut it to the size a cell can hold."""
    if texto.startswith(_INICIOS_PELIGROSOS):
        texto = "'" + texto
    return texto[:MAX_CELDA]


def celda(valor: object) -> Celda:
    if valor is None:
        return ""
    if isinstance(valor, bool):  # before int: bool is an int
        return "SI" if valor else "NO"
    if isinstance(valor, Decimal):
        return valor
    if isinstance(valor, int):
        return Decimal(valor)
    if isinstance(valor, datetime):
        return valor.isoformat(timespec="seconds")
    if isinstance(valor, date):
        return valor.isoformat()
    if isinstance(valor, str):
        return texto_seguro(valor)
    raise TypeError(f"No se puede mostrar un valor de tipo {type(valor).__name__} (el dinero nunca pasa por float).")


def _fila(*valores: object) -> tuple[Celda, ...]:
    return tuple(celda(v) for v in valores)


def _avisos(avisos: list[str]) -> str:
    return "; ".join(avisos)


# --- Tabs ---------------------------------------------------------------------------------------------------

def _catalogo(fuente: Fuente, hoy: date) -> Tab:
    encabezados = (
        "Código", "Nombre", "Categoría", "Estado del ciclo", "Dónde se hace", "Kit", "Fecha de alta", "CV hoy ARS",
        "CV hoy USD", "Cotización inicial ARS", "Cotización final ARS", "Última cotización ARS",
        "Fecha última cotización", "¿Recotizar?", "Alertas",
    )
    filas = []
    for p in fuente.productos_costeados():
        costo = p["costo"]
        recotizar = p["recotizar"]  # None = cannot be decided (no cost today, no stored quote or no tolerance)
        filas.append(_fila(
            p["codigo"], p["nombre"], p["categoria"], p["estado_del_ciclo"], p["quien_lo_confecciona"], p["es_kit"],
            p["fecha_de_alta"], costo and costo["total_ars"], costo and costo["total_usd"], p["inicial_ars"],
            p["final_ars"], p["ultima_ars"], p["ultima_fecha"], recotizar, _avisos(p["avisos"]),
        ))
    return Tab("Catalogo", encabezados, tuple(filas))


def _costos_variables(fuente: Fuente, hoy: date) -> Tab:
    encabezados = (
        "Código", "Producto", "Confección", *_ETAPAS, "Subtotal etapas", "Componentes del kit",
        "IVA de compras (si es costo)", "CV por unidad ARS", "CV por unidad USD", "Dólar usado",
        "Alertas (vacío = sin alertas)", "Arreglos",
    )
    filas = []
    for p in fuente.productos_costeados():
        c = p["costo"]
        etapas = [c["etapas"][e] for e in _ETAPAS] if c else [None] * len(_ETAPAS)
        filas.append(_fila(
            p["codigo"], p["nombre"], p["quien_lo_confecciona"], *etapas,
            c and c["subtotal"], c and c["componentes_kit"], c and c["iva_compras"], c and c["total_ars"],
            c and c["total_usd"], c and c["dolar"], _avisos(p["avisos"]), c and c["arreglos"],
        ))
    return Tab("Costos_Variables", encabezados, tuple(filas))


def _cotizaciones(fuente: Fuente, hoy: date) -> Tab:
    encabezados = (
        "Producto", "Producto (nombre)", "Tipo", "Fecha", "Dólar de esa fecha", "CUERO", "FORRO", "FLEX", "GOMA_EVA",
        "HERRAJES", "HILO_CEMENTO", "CORTE", "CONFECCION", "Subtotal etapas", "Componentes del kit",
        "IVA de compras", "Total ARS", "Total USD", "Estado", "Arreglos",
    )
    filas = [_fila(
        c["producto"], c["producto_nombre"], c["tipo"], c["fecha"], c["dolar"], c["cuero"], c["forro"], c["flex"],
        c["goma_eva"], c["herrajes"], c["hilo_cemento"], c["corte"], c["confeccion"], c["subtotal_etapas"],
        c["componentes_kit"], c["iva_compras"], c["total_ars"], c["total_usd"], c["estado"], c["arreglos"],
    ) for c in fuente.cotizaciones()]
    return Tab("Cotizaciones", encabezados, tuple(filas))


def _productos(fuente: Fuente, hoy: date) -> Tab:
    encabezados = (
        "Código", "Modelo", "Cuero", "Color", "¿Quién lo confecciona?", "Estado del ciclo", "Fecha de alta",
        "Fecha de recotización", "Fecha de cierre", "Nombre propio (opcional)", "Es kit", "Nota", "Nombre", "Categoría",
    )
    filas = [_fila(
        p["codigo"], p["modelo"], p["cuero"], p["color"], p["quien_lo_confecciona"], p["estado_del_ciclo"],
        p["fecha_de_alta"], p["fecha_de_recotizacion"], p["fecha_de_cierre"], p["nombre_propio"], p["es_kit"],
        p["nota"], p["nombre"], p["categoria"],
    ) for p in fuente.productos()]
    return Tab("Productos", encabezados, tuple(filas))


def _modelos(fuente: Fuente, hoy: date) -> Tab:
    encabezados = (
        "Código", "Nombre del modelo", "Categoría", "Modelo Excel viejo", "Fila Excel viejo", "Cuero m² por unidad",
        "Forro", "Forro m² por unidad", "Flex m² por unidad", "Goma EVA m² por unidad", "Herrajes USD por unidad",
        "Hilo y cemento (juegos)", "Confección estimada ARS (Mariano)", "Horas de confección",
        "Origen de los consumos", "Validado", "Nota", "Tamaño (opcional)", "Productos que lo usan",
    )
    filas = [_fila(
        m["codigo"], m["nombre_del_modelo"], m["categoria"], m["modelo_excel_viejo"], m["fila_excel_viejo"],
        m["cuero_m2_por_unidad"], m["forro"], m["forro_m2_por_unidad"], m["flex_m2_por_unidad"],
        m["goma_eva_m2_por_unidad"], m["herrajes_usd_por_unidad"], m["hilo_y_cemento"], m["confeccion_estimada_ars"],
        m["horas_de_confeccion"], m["origen_de_los_consumos"], m["validado"], m["nota"], m["tamano"], m["productos"],
    ) for m in fuente.modelos()]
    return Tab("Modelos", encabezados, tuple(filas))


def _precios(fuente: Fuente, hoy: date) -> Tab:
    encabezados = (
        "Código", "Material", "Color (opcional)", "Proveedor", "Precio", "Moneda", "Unidad del precio", "IVA incluido",
        "Vigente desde", "Nota / fuente", "¿Es el vigente?",
    )
    filas = [_fila(
        p["codigo"], p["material"], p["color"], p["proveedor"], p["precio"], p["moneda"], p["unidad_del_precio"],
        p["iva_incluido"], p["vigente_desde"], p["nota_fuente"], p["vigente"],
    ) for p in fuente.precios(hoy)]
    return Tab("Precios", encabezados, tuple(filas))


def _dolar(fuente: Fuente, hoy: date) -> Tab:
    encabezados = ("Fecha", "ARS por USD", "Fuente", "Tipo", "Nota")
    filas = [_fila(d["fecha"], d["ars_por_usd"], d["fuente"], d["tipo"], d["nota"]) for d in fuente.dolar()]
    return Tab("Dolar", encabezados, tuple(filas))


def _lotes(fuente: Fuente, hoy: date) -> Tab:
    encabezados = (
        "Código", "¿Dónde se hace?", "Taller", "Persona", "Fecha de envío", "Fecha de entrega", "Estado", "Nota",
        "Período", "Productos", "Unidades", "Taller cotizó (total ARS)", "Taller cobró (total ARS)",
        "Costo total del lote ARS", "Costo promedio por unidad ARS",
    )
    filas = [_fila(
        o["codigo"], o["donde_se_hace"], o["taller"], o["persona"], o["fecha_de_envio"], o["fecha_de_entrega"],
        o["estado"], o["nota"], o["periodo"], o["productos"], o["unidades"], o["total_cotizado"], o["total_cobrado"],
        o["costo_total"], o["costo_promedio_por_unidad"],
    ) for o in fuente.ordenes()]
    return Tab("Lotes", encabezados, tuple(filas))


def _lote_productos(fuente: Fuente, hoy: date) -> Tab:
    encabezados = (
        "Código", "Lote", "Producto", "Cantidad", "Taller: precio cotizado por unidad ARS",
        "Taller: precio pagado por unidad ARS", "Nota", "Producto (nombre)", "Dónde", "Taller", "Fecha",
        "Estado del lote", "Período", "Confección por unidad ARS", "Materiales por unidad ARS (hoy)",
        "Costo por unidad ARS", "Total de la línea ARS", "Categoría", "Tamaño",
    )
    filas = []
    for o in fuente.ordenes():
        fecha = o["fecha_de_entrega"] or o["fecha_de_envio"]  # the date a lot counts on
        for i in o["items"]:
            filas.append(_fila(
                i["codigo"], o["codigo"], i["producto"], i["cantidad"], i["cotizado"], i["pagado"], i["nota"],
                i["producto_nombre"], o["donde_se_hace"], o["taller"], fecha, o["estado"], o["periodo"],
                i["confeccion_por_unidad"], i["materiales_por_unidad"], i["costo_por_unidad"], i["total_linea"],
                i["categoria"], i["tamano"],
            ))
    return Tab("Lote_Productos", encabezados, tuple(filas))


def _costos_fijos(fuente: Fuente, hoy: date) -> Tab:
    encabezados = (
        "Código", "Período", "Concepto", "¿Fábrica o tienda?", "Categoría", "Persona", "Monto ARS del mes",
        "¿Ficticio?", "Nota / fuente", "Total fábrica del período ARS", "Total tienda del período ARS",
        "Total del período ARS", "Montos pendientes del período",
    )
    filas = []
    for periodo in fuente.costos_fijos():
        for g in periodo["gastos"]:
            filas.append(_fila(
                g["codigo"], periodo["periodo"], g["concepto"], g["fabrica_o_tienda"], g["categoria"], g["persona"],
                g["monto_ars_del_mes"], g["ficticio"], g["nota_fuente"], periodo["total_fabrica"],
                periodo["total_tienda"], periodo["total"], periodo["pendientes"],
            ))
    return Tab("Costos_Fijos", encabezados, tuple(filas))


def _talleres(fuente: Fuente, hoy: date) -> Tab:
    encabezados = (
        "Código", "Nombre", "CUIT", "Teléfono", "Dirección", "Contacto", "Activo", "Nota", "Lotes", "Unidades",
        "Último lote", "Cobró en total ARS",
    )
    filas = [_fila(
        t["codigo"], t["nombre"], t["cuit"], t["telefono"], t["direccion"], t["contacto"], t["activo"], t["nota"],
        t["lotes"], t["unidades"], t["ultimo_lote"], t["cobro_total_ars"],
    ) for t in fuente.talleres()]
    return Tab("Talleres", encabezados, tuple(filas))


def _parametros(fuente: Fuente, hoy: date) -> Tab:
    encabezados = ("Constante", "Valor", "Unidad", "Qué es", "Fuente / estado", "Código en la base")
    filas = [_fila(
        p["constante"], p["valor"] if p["valor"] is not None else p["valor_texto"], p["unidad"], p["que_es"],
        p["fuente_estado"], p["codigo"],
    ) for p in fuente.parametros()]
    return Tab("Parametros", encabezados, tuple(filas))


def _materiales(fuente: Fuente, hoy: date) -> Tab:
    encabezados = (
        "Código", "Nombre", "Nombre corto", "Etapa", "Unidad de consumo", "Cotizable", "Controla inventario",
        "Desperdicio manual (opcional)",
    )
    filas = [_fila(
        m["codigo"], m["nombre"], m["nombre_corto"], m["etapa"], m["unidad_de_consumo"], m["cotizable"],
        m["controla_inventario"], m["desperdicio_manual"],
    ) for m in fuente.materiales()]
    return Tab("Materiales", encabezados, tuple(filas))


def _calidad(fuente: Fuente, hoy: date) -> Tab:
    encabezados = ("Severidad", "Grupo", "Entidad", "Mensaje", "Dónde corregirlo")
    filas = [
        _fila(h["severidad"], grupo["titulo"], h["entidad"], h["mensaje"], h["ruta"])
        for grupo in fuente.calidad(hoy)["grupos"] for h in grupo["hallazgos"]
    ]
    return Tab("Calidad", encabezados, tuple(filas))


_CONSTRUCTORES: dict[str, Callable[[Fuente, date], Tab]] = {
    "Catalogo": _catalogo, "Costos_Variables": _costos_variables, "Cotizaciones": _cotizaciones,
    "Productos": _productos, "Modelos": _modelos, "Precios": _precios, "Dolar": _dolar, "Lotes": _lotes,
    "Lote_Productos": _lote_productos, "Costos_Fijos": _costos_fijos, "Talleres": _talleres,
    "Parametros": _parametros, "Materiales": _materiales, "Calidad": _calidad,
}
# The fixed list of tabs the app owns in the Sheet; the client never touches any other.
NOMBRES_DE_PESTANAS = ("Info", *_CONSTRUCTORES)


def _info(otras: list[Tab], generado_en: datetime, version: str) -> Tab:
    filas = [
        ("Aviso", NOTA_DE_INFO), ("Generado", generado_en), ("Versión de la app", version),
        *((f"Filas en {t.name}", len(t.rows)) for t in otras),
    ]
    return Tab("Info", ("Dato", "Valor"), tuple(_fila(*f) for f in filas))


def construir_tabs(fuente: Fuente, *, generado_en: datetime, version: str) -> list[Tab]:
    """Every tab, in `NOMBRES_DE_PESTANAS` order (Info first). `generado_en` must be timezone-aware."""
    hoy = generado_en.date()
    otras = [construir(fuente, hoy) for construir in _CONSTRUCTORES.values()]
    return [_info(otras, generado_en, version), *otras]


def construir_tab(nombre: str, fuente: Fuente, *, generado_en: datetime, version: str) -> Tab:
    """One tab; the others are only built for Info (it counts their rows). KeyError if the name is not ours."""
    if nombre not in NOMBRES_DE_PESTANAS:
        raise KeyError(nombre)
    if nombre == "Info":
        return construir_tabs(fuente, generado_en=generado_en, version=version)[0]
    return _CONSTRUCTORES[nombre](fuente, generado_en.date())
