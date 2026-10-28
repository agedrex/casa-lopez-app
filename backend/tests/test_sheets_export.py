"""Display copy for the Google Sheet (T6): the tabs the app builds, with no network and no database.

`construir_tabs` reads from a `Fuente` (in production `FuenteSQL`, here an in-memory one) and only formats:
costs come already calculated by `servicios`. The Sheet is display only, so what matters here is the shape
(Spanish headers of the plantilla's Diccionario, SI/NO flags, ISO dates, exact Decimals, no formula injection).
"""

from datetime import date, datetime
from decimal import Decimal as D

import pytest
from sheets_datos import AHORA, AR, ETAPAS, FuenteEnMemoria, producto_costeado

from backend import sheets_export
from backend.sheets_export import (
    NOMBRES_DE_PESTANAS, NOTA_DE_INFO, Tab, celda, construir_tab, construir_tabs, texto_seguro,
)

@pytest.fixture
def tabs():
    return {t.name: t for t in construir_tabs(FuenteEnMemoria(), generado_en=AHORA, version="9.9.9")}


# --- Cell formatting ----------------------------------------------------------------------------------------

def test_cells_follow_the_display_rules():
    assert celda(None) == ""
    assert celda(True) == "SI" and celda(False) == "NO"
    assert celda(date(2026, 9, 1)) == "2026-09-01"
    assert celda(datetime(2026, 9, 1, 10, 0, 5, tzinfo=AR)) == "2026-09-01T10:00:05-03:00"
    assert celda("Estándar") == "Estándar"
    assert celda(3) == D(3) and isinstance(celda(3), D)


def test_decimals_stay_exact_decimals():
    valor = celda(D("1234567890123.4567"))
    assert isinstance(valor, D) and valor == D("1234567890123.4567")
    assert str(celda(D("0.1000"))) == "0.1000"


def test_a_float_is_refused_because_money_never_goes_through_float():
    with pytest.raises(TypeError):
        celda(0.1)


@pytest.mark.parametrize("peligroso", ["=1+1", "+54 11 5555", "-2+3", "@SUM(A1)", "=HYPERLINK(\"http://x\")", "\t=1", "\r=1"])
def test_text_that_starts_like_a_formula_gets_a_single_quote(peligroso):
    assert texto_seguro(peligroso) == "'" + peligroso
    assert celda(peligroso) == "'" + peligroso


@pytest.mark.parametrize("texto", ["Cartera", "a=b", "10 - 5", "", "'ya con comilla", "ñandú"])
def test_ordinary_text_is_left_alone(texto):
    assert texto_seguro(texto) == texto


def test_a_huge_text_is_cut_to_the_cell_limit_of_the_sheet():
    assert len(texto_seguro("x" * 60000)) <= sheets_export.MAX_CELDA


# --- Tabs ---------------------------------------------------------------------------------------------------

def test_the_fixed_list_of_tabs_is_built_in_order(tabs):
    assert tuple(tabs) == NOMBRES_DE_PESTANAS
    assert set(NOMBRES_DE_PESTANAS) == {
        "Info", "Catalogo", "Costos_Variables", "Cotizaciones", "Productos", "Modelos", "Precios", "Dolar", "Lotes",
        "Lote_Productos", "Costos_Fijos", "Talleres", "Parametros", "Materiales", "Calidad",
    }


def test_every_tab_has_unique_headers_and_rectangular_rows(tabs):
    for nombre, tab in tabs.items():
        assert isinstance(tab, Tab) and tab.name == nombre
        assert tab.headers and all(h for h in tab.headers), nombre
        assert len(set(tab.headers)) == len(tab.headers), nombre
        assert all(len(fila) == len(tab.headers) for fila in tab.rows), nombre


def test_no_cell_is_a_float_none_bool_or_date(tabs):
    for tab in tabs.values():
        for fila in tab.rows:
            for valor in fila:
                assert type(valor) in (str, D), (tab.name, valor)


def test_with_data_every_tab_has_at_least_one_row(tabs):
    for nombre, tab in tabs.items():
        assert tab.rows, nombre


@pytest.mark.parametrize("nombre, encabezados", [
    # Names copied from the plantilla v4.1 (sheet Diccionario, "Columna en el Excel").
    ("Dolar", ("Fecha", "ARS por USD", "Fuente", "Tipo", "Nota")),
    ("Materiales", ("Código", "Nombre", "Nombre corto", "Etapa", "Unidad de consumo", "Cotizable", "Controla inventario",
                    "Desperdicio manual (opcional)")),
    ("Parametros", ("Constante", "Valor", "Unidad", "Qué es", "Fuente / estado", "Código en la base")),
    ("Talleres", ("Código", "Nombre", "CUIT", "Teléfono", "Dirección", "Contacto", "Activo", "Nota", "Lotes", "Unidades",
                  "Último lote", "Cobró en total ARS")),
    ("Cotizaciones", ("Producto", "Producto (nombre)", "Tipo", "Fecha", "Dólar de esa fecha", "CUERO", "FORRO", "FLEX",
                      "GOMA_EVA", "HERRAJES", "HILO_CEMENTO", "CORTE", "CONFECCION", "Subtotal etapas", "Componentes del kit",
                      "IVA de compras", "Total ARS", "Total USD", "Estado", "Arreglos")),
    ("Costos_Variables", ("Código", "Producto", "Confección", "CUERO", "FORRO", "FLEX", "GOMA_EVA", "HERRAJES",
                          "HILO_CEMENTO", "CORTE", "CONFECCION", "Subtotal etapas", "Componentes del kit",
                          "IVA de compras (si es costo)", "CV por unidad ARS", "CV por unidad USD", "Dólar usado",
                          "Alertas (vacío = sin alertas)", "Arreglos")),
])
def test_headers_are_the_plantilla_names(tabs, nombre, encabezados):
    assert tabs[nombre].headers == encabezados


@pytest.mark.parametrize("nombre, primeros", [
    ("Productos", ("Código", "Modelo", "Cuero", "Color", "¿Quién lo confecciona?", "Estado del ciclo", "Fecha de alta",
                   "Fecha de recotización", "Fecha de cierre", "Nombre propio (opcional)", "Es kit", "Nota")),
    ("Modelos", ("Código", "Nombre del modelo", "Categoría", "Modelo Excel viejo", "Fila Excel viejo", "Cuero m² por unidad",
                 "Forro", "Forro m² por unidad", "Flex m² por unidad", "Goma EVA m² por unidad", "Herrajes USD por unidad",
                 "Hilo y cemento (juegos)", "Confección estimada ARS (Mariano)", "Horas de confección",
                 "Origen de los consumos", "Validado", "Nota", "Tamaño (opcional)")),
    ("Precios", ("Código", "Material", "Color (opcional)", "Proveedor", "Precio", "Moneda", "Unidad del precio",
                 "IVA incluido", "Vigente desde", "Nota / fuente")),
    ("Lotes", ("Código", "¿Dónde se hace?", "Taller", "Persona", "Fecha de envío", "Fecha de entrega", "Estado", "Nota",
               "Período", "Productos", "Unidades", "Taller cotizó (total ARS)", "Taller cobró (total ARS)",
               "Costo total del lote ARS", "Costo promedio por unidad ARS")),
    ("Lote_Productos", ("Código", "Lote", "Producto", "Cantidad", "Taller: precio cotizado por unidad ARS",
                        "Taller: precio pagado por unidad ARS", "Nota")),
    ("Costos_Fijos", ("Código", "Período", "Concepto", "¿Fábrica o tienda?", "Categoría", "Persona", "Monto ARS del mes",
                      "¿Ficticio?", "Nota / fuente")),
])
def test_load_columns_come_first_in_the_plantilla_order(tabs, nombre, primeros):
    assert tabs[nombre].headers[:len(primeros)] == primeros


def test_catalogo_row_shows_cost_quotes_and_the_recotizar_flag(tabs):
    catalogo = tabs["Catalogo"]
    fila = dict(zip(catalogo.headers, catalogo.rows[0]))
    assert fila["Código"] == "PRD-0001" and fila["Categoría"] == "Portafolios"
    assert fila["Estado del ciclo"] == "COTIZADO" and fila["Kit"] == "NO"
    assert fila["CV hoy ARS"] == D("20760.6") and fila["CV hoy USD"] == D("13.4375")
    assert fila["Cotización inicial ARS"] == D("20760.6") and fila["Cotización final ARS"] == ""
    assert fila["Fecha última cotización"] == "2026-09-03" and fila["¿Recotizar?"] == "NO"
    assert fila["Alertas"] == ""


def test_catalogo_without_a_cost_today_keeps_the_warnings_and_blank_numbers():
    fuente = FuenteEnMemoria(productos_costeados_=[
        producto_costeado(costo=None, recotizar=None, avisos=["Falta el dólar", "Falta el consumo de cuero"],
                          inicial_ars=None, ultima_ars=None, ultima_fecha=None)])
    catalogo = construir_tab("Catalogo", fuente, generado_en=AHORA, version="1")
    fila = dict(zip(catalogo.headers, catalogo.rows[0]))
    assert fila["CV hoy ARS"] == "" and fila["CV hoy USD"] == "" and fila["¿Recotizar?"] == ""
    assert fila["Alertas"] == "Falta el dólar; Falta el consumo de cuero"
    variables = construir_tab("Costos_Variables", fuente, generado_en=AHORA, version="1")
    fila = dict(zip(variables.headers, variables.rows[0]))
    assert fila["CUERO"] == "" and fila["CV por unidad ARS"] == "" and fila["Alertas (vacío = sin alertas)"].startswith("Falta el dólar")


def test_costos_variables_has_one_column_per_stage_and_the_total(tabs):
    variables = tabs["Costos_Variables"]
    fila = dict(zip(variables.headers, variables.rows[0]))
    assert [fila[etapa] for etapa in ETAPAS] == [D("9270"), D("810.6"), D("4500"), D("0"), D("3090"), D("3090"), D("0"), D("12000.1234")]
    assert fila["CV por unidad ARS"] == D("20760.6") and fila["Dólar usado"] == D("1545")
    assert fila["Confección"] == "INTERNA"


def test_cotizaciones_lists_the_stored_quotes_with_every_stage(tabs):
    cotizaciones = tabs["Cotizaciones"]
    fila = dict(zip(cotizaciones.headers, cotizaciones.rows[0]))
    assert fila["Producto"] == "PRD-0001" and fila["Tipo"] == "INICIAL" and fila["Fecha"] == "2026-09-03"
    assert fila["Dólar de esa fecha"] == D("1545") and fila["Total ARS"] == D("20760.6") and fila["Estado"] == "COMPLETA"


def test_precios_flag_the_row_in_force(tabs):
    precios = tabs["Precios"]
    fila = dict(zip(precios.headers, precios.rows[0]))
    assert fila["Precio"] == D("24") and fila["IVA incluido"] == "NO" and fila["¿Es el vigente?"] == "SI"
    assert fila["Color (opcional)"] == "" and fila["Vigente desde"] == "2026-09-01"


def test_parametros_show_the_text_value_when_there_is_no_number(tabs):
    parametros = tabs["Parametros"]
    valores = {fila[0]: fila[1] for fila in parametros.rows}
    assert valores["Arreglos"] == D("0") and valores["Período vigente"] == "2026-10"
    assert parametros.rows[0][-1] == "ARREGLOS_PCT"


def test_lotes_carry_their_totals_and_lote_productos_one_row_per_line(tabs):
    lotes = tabs["Lotes"]
    fila = dict(zip(lotes.headers, lotes.rows[0]))
    assert fila["Productos"] == D(1) and fila["Unidades"] == D("10") and fila["Taller cobró (total ARS)"] == D("85000")
    assert fila["Costo total del lote ARS"] == D("292606") and fila["Período"] == "2026-09"
    lineas = tabs["Lote_Productos"]
    fila = dict(zip(lineas.headers, lineas.rows[0]))
    assert fila["Lote"] == "LOT-0001" and fila["Producto"] == "PRD-0001" and fila["Cantidad"] == D("10")
    assert fila["Total de la línea ARS"] == D("292606") and fila["Dónde"] == "EXTERNA" and fila["Taller"] == "TAL-0001"
    assert fila["Estado del lote"] == "CERRADA"


def test_costos_fijos_repeat_the_totals_of_their_period_on_every_row(tabs):
    fijos = tabs["Costos_Fijos"]
    assert len(fijos.rows) == 2
    for fila in map(lambda r: dict(zip(fijos.headers, r)), fijos.rows):
        assert fila["Total fábrica del período ARS"] == D("4000000")
        assert fila["Total tienda del período ARS"] == D("3000000")
        assert fila["Total del período ARS"] == D("7000000")
        assert fila["Montos pendientes del período"] == D(1)
    pendiente = dict(zip(fijos.headers, fijos.rows[1]))
    assert pendiente["Monto ARS del mes"] == "" and pendiente["¿Ficticio?"] == "NO"


def test_talleres_phone_that_starts_with_plus_is_quoted(tabs):
    talleres = tabs["Talleres"]
    fila = dict(zip(talleres.headers, talleres.rows[0]))
    assert fila["Teléfono"] == "'+54 11 5555-0000" and fila["Activo"] == "SI"


def test_calidad_flattens_the_findings_of_the_report(tabs):
    calidad = tabs["Calidad"]
    assert calidad.headers == ("Severidad", "Grupo", "Entidad", "Mensaje", "Dónde corregirlo")
    assert calidad.rows == (("alta", "Productos con avisos", "PRD-0002", "Falta el consumo de cuero", "/productos/PRD-0002"),)


def test_info_tab_says_what_it_is_and_counts_the_rows(tabs):
    info = tabs["Info"]
    assert info.headers == ("Dato", "Valor")
    datos = {fila[0]: fila[1] for fila in info.rows}
    assert datos["Generado"] == "2026-10-28T15:30:05-03:00"
    assert datos["Versión de la app"] == "9.9.9"
    assert datos["Aviso"] == NOTA_DE_INFO == "Vista generada por la app. No editar: se pisa en cada sincronización."
    for nombre in NOMBRES_DE_PESTANAS:
        if nombre != "Info":
            assert datos[f"Filas en {nombre}"] == D(len(tabs[nombre].rows)), nombre


def test_construir_tab_builds_only_the_requested_tab():
    class Solo(FuenteEnMemoria):
        def productos_costeados(self): raise AssertionError("not needed for Dolar")

    tab = construir_tab("Dolar", Solo(), generado_en=AHORA, version="1")
    assert tab.name == "Dolar" and len(tab.rows) == 1


def test_an_unknown_tab_name_is_refused():
    with pytest.raises(KeyError):
        construir_tab("Hoja1", FuenteEnMemoria(), generado_en=AHORA, version="1")


def test_the_builder_never_reads_the_clock_or_the_network(monkeypatch):
    # Same inputs, same tabs: nothing depends on "now" because the caller passes `generado_en`.
    a = construir_tabs(FuenteEnMemoria(), generado_en=AHORA, version="1")
    b = construir_tabs(FuenteEnMemoria(), generado_en=AHORA, version="1")
    assert a == b


def test_an_injected_text_inside_a_row_is_neutralised_end_to_end():
    fuente = FuenteEnMemoria()
    fuente.productos_[0]["nota"] = "=cmd|' /C calc'!A0"
    productos = construir_tab("Productos", fuente, generado_en=AHORA, version="1")
    fila = dict(zip(productos.headers, productos.rows[0]))
    assert fila["Nota"] == "'=cmd|' /C calc'!A0"
