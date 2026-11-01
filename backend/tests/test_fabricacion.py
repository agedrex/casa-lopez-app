"""Lots (fabricación), workshops, fixed costs and data quality (T5d).

Pure rules first (no database), then the HTTP flows against the disposable local PostgreSQL
(skipped without TEST_DATABASE_URL, like test_api_integration.py).
"""

from datetime import date
from decimal import Decimal as D

import pytest

from backend import servicios
from backend.servicios import (
    ItemDatos, LoteDatos, PrecioDeTaller, avisos_de_lote, avisos_de_renglon, confeccion_de_renglon,
    controles_de_producto, es_taller_de_ejemplo, estado_de_parametro, hallazgos_de_precios,
    precios_parecidos, precios_por_taller, referencia_de_precio, resumen_casa_vs_taller, severidad_de_aviso, ultimos_meses,
)

# --- Pure rules (plantilla: Lote_Productos P / AA, Lotes Q, Casa_vs_Taller, Precios_Talleres) -------------------


def test_sewing_per_unit_is_paid_else_quoted_and_zero_in_house():
    f = date(2026, 10, 5)
    assert confeccion_de_renglon("EXTERNA", f, D("12500"), D("11000")) == D("11000")
    assert confeccion_de_renglon("EXTERNA", f, D("12500"), None) == D("12500")
    assert confeccion_de_renglon("EXTERNA", f, D("12500"), D("0")) == D("12500")  # a 0 is "not paid yet"
    assert confeccion_de_renglon("EXTERNA", f, None, None) is None
    assert confeccion_de_renglon("INTERNA", f, D("12500"), D("11000")) == D("0")
    assert confeccion_de_renglon("EXTERNA", None, D("12500"), D("11000")) is None  # no lot date, no price


def test_a_line_warns_about_what_the_sheet_control_column_warns_about():
    f = date(2026, 10, 5)
    assert avisos_de_renglon("EXTERNA", f, D("10"), D("1"), None, True) == []
    assert avisos_de_renglon("EXTERNA", f, D("10"), None, None, True) == ["Falta el precio del taller"]
    assert avisos_de_renglon("INTERNA", f, D("10"), None, None, True) == []
    assert avisos_de_renglon("INTERNA", f, D("0"), None, None, True) == ["Falta la cantidad"]
    assert avisos_de_renglon("INTERNA", None, D("1"), None, None, True) == ["El lote no tiene fecha"]
    assert avisos_de_renglon("INTERNA", f, D("1"), None, None, False) == [servicios.AVISO_SIN_COSTO]


def test_a_lot_warns_about_missing_workshop_dates_products_and_delivery():
    f = date(2026, 10, 5)
    assert avisos_de_lote("EXTERNA", "TAL-0001", f, 1, "PLANIFICADA", None, 0) == []
    assert avisos_de_lote("EXTERNA", None, f, 1, "PLANIFICADA", None, 0) == ["Falta el taller"]
    assert avisos_de_lote("INTERNA", None, f, 1, "PLANIFICADA", None, 0) == []  # in house needs no workshop
    assert avisos_de_lote("INTERNA", None, None, 1, "PLANIFICADA", None, 0) == ["Falta la fecha de envío"]
    assert avisos_de_lote("INTERNA", None, f, 0, "PLANIFICADA", None, 0) == ["Sin productos: agregá al menos uno"]
    assert avisos_de_lote("INTERNA", None, f, 1, "CERRADA", None, 0) == [
        "Falta la fecha de entrega (cierra la cotización final)"]
    assert avisos_de_lote("INTERNA", None, f, 1, "CERRADA", f, 2) == ["Hay productos con problemas"]


def test_months_run_newest_first_across_a_year_boundary():
    meses = ultimos_meses("2026-02")
    assert len(meses) == 12 and meses[0] == "2026-02" and meses[1] == "2026-01" and meses[2] == "2025-12"
    assert meses[-1] == "2025-03"


def lote(codigo, donde, taller, envio, entrega=None, estado="PLANIFICADA"):
    return LoteDatos(id=int(codigo[-1]), codigo=codigo, donde=donde, taller=taller, taller_nombre=taller,
                     persona=None, persona_nombre=None, envio=envio, entrega=entrega, estado=estado, nota=None)


def renglon(codigo, lote_codigo, cantidad, pagado=None, cotizado=None, producto="PRD-0001"):
    return ItemDatos(id=int(codigo[-1]), codigo=codigo, lote=lote_codigo, producto=producto,
                     cantidad=D(cantidad), cotizado=cotizado, pagado=pagado, nota=None)


def test_house_vs_workshop_counts_a_lot_in_its_delivery_month_else_its_shipping_month():
    lotes = [
        lote("LOT-0001", "EXTERNA", "TAL-0001", date(2026, 10, 20), date(2026, 11, 2)),  # delivered in November
        lote("LOT-0002", "INTERNA", None, date(2026, 10, 10)),
        lote("LOT-0003", "EXTERNA", "TAL-0002", date(2026, 10, 12)),  # not back yet: October
        lote("LOT-0004", "INTERNA", None, None),  # no date: counted nowhere
    ]
    items = [
        renglon("LIT-0001", "LOT-0001", "10", pagado=D("1000")), renglon("LIT-0002", "LOT-0002", "5"),
        renglon("LIT-0003", "LOT-0003", "4", cotizado=D("900"), pagado=D("800")), renglon("LIT-0004", "LOT-0004", "7"),
    ]
    filas = resumen_casa_vs_taller(lotes, items, [("TAL-0001", "A"), ("TAL-0002", "B")], ultimos_meses("2026-11"))
    nov, octubre = filas[0], filas[1]
    assert nov["periodo"] == "2026-11" and (nov["lotes_taller"], nov["lotes_casa"]) == (1, 0)
    assert nov["unidades_taller"] == D("10") and nov["pagado_a_talleres"] == D("10000")
    assert nov["porcentaje_taller"] == D("100.00") and nov["unidades_por_taller"] == {"TAL-0001": D("10"), "TAL-0002": D("0")}
    assert (octubre["lotes_casa"], octubre["lotes_taller"]) == (1, 1)
    assert (octubre["unidades_casa"], octubre["unidades_taller"]) == (D("5"), D("4"))
    assert octubre["pagado_a_talleres"] == D("3200")  # only what was paid, never what was quoted
    assert octubre["porcentaje_taller"] == D("44.44")
    assert filas[2]["porcentaje_taller"] is None and filas[2]["lotes_casa"] == 0
    assert len(filas) == 12


def precio(taller, producto, dia, valor, orden, categoria="Carteras", tamano="CHICO", lote_codigo="LOT-0001"):
    return PrecioDeTaller(fecha=dia, orden=orden, producto=producto, nombre=f"Nombre {producto}", categoria=categoria,
                          tamano=tamano, taller=taller, taller_nombre=f"Taller {taller}", cantidad=D("3"),
                          precio=D(valor), lote=lote_codigo)


PRECIOS = [
    precio("TAL-0001", "PRD-0001", date(2026, 9, 10), "10000", 1),
    precio("TAL-0001", "PRD-0001", date(2026, 10, 10), "11000", 2),
    precio("TAL-0002", "PRD-0001", date(2026, 10, 1), "12000", 3),
    precio("TAL-0003", "PRD-0002", date(2026, 10, 3), "9000", 4),  # similar: same category and size
    precio("TAL-0003", "PRD-0003", date(2026, 10, 4), "8000", 5, tamano="GRANDE"),  # same category, other size
    precio("TAL-0003", "PRD-0004", date(2026, 10, 5), "7000", 6, categoria="Billeteras"),
]
TALLERES = [("TAL-0001", "Taller A"), ("TAL-0002", "Taller B"), ("TAL-0003", "Taller C")]


def test_latest_price_per_workshop_for_the_product_with_the_previous_one():
    filas = {f["taller"]: f for f in precios_por_taller(PRECIOS, "PRD-0001", TALLERES)}
    a = filas["TAL-0001"]
    assert a["hizo"] and a["precio"] == D("11000") and a["fecha"] == date(2026, 10, 10) and a["veces"] == 2
    assert a["precio_anterior"] == D("10000") and a["variacion_pct"] == D("10.00")
    b = filas["TAL-0002"]
    assert b["precio"] == D("12000") and b["veces"] == 1 and b["precio_anterior"] is None and b["variacion_pct"] is None
    assert filas["TAL-0003"]["hizo"] is False and filas["TAL-0003"]["precio"] is None


def test_similar_products_share_category_and_size_and_mark_the_same_product():
    filas = precios_parecidos(PRECIOS, "PRD-0001", "Carteras", "CHICO", True)
    assert [(f["producto"], f["taller"], f["precio"], f["es_mismo_producto"]) for f in filas] == [
        ("PRD-0001", "TAL-0001", D("11000"), True), ("PRD-0002", "TAL-0003", D("9000"), False),
        ("PRD-0001", "TAL-0002", D("12000"), True)]  # newest first; one row per (workshop, product)
    todos = precios_parecidos(PRECIOS, "PRD-0001", "Carteras", "CHICO", False)
    assert "PRD-0003" in {f["producto"] for f in todos} and "PRD-0004" not in {f["producto"] for f in todos}
    assert precios_parecidos(PRECIOS, "PRD-0001", None, None, True) == []  # no category, nothing to compare


HOY = date(2026, 11, 1)


def test_reference_same_product_uses_the_latest_paid_per_workshop_with_days_and_change():
    ref = referencia_de_precio(PRECIOS, "PRD-0001", "Carteras", "CHICO", HOY)
    assert ref["nivel"] == "MISMO_PRODUCTO" and ref["categoria"] == "Carteras" and ref["tamano"] == "CHICO"
    primero, segundo = ref["items"]  # newest first
    assert (primero["taller"], primero["precio"], primero["fecha"], primero["dias"]) == ("TAL-0001", D("11000"), date(2026, 10, 10), 22)
    assert (primero["lote"], primero["cantidad"], primero["precio_anterior"], primero["variacion_pct"]) == ("LOT-0001", D("3"), D("10000"), D("10.00"))
    assert (segundo["taller"], segundo["precio"], segundo["dias"]) == ("TAL-0002", D("12000"), 31)
    assert segundo["precio_anterior"] is None and segundo["variacion_pct"] is None


def test_reference_same_category_and_size_when_the_product_has_no_paid_price():
    ref = referencia_de_precio(PRECIOS, "PRD-0009", "Carteras", "CHICO", HOY)
    assert ref["nivel"] == "MISMA_CATEGORIA_Y_TAMANO"
    assert [(f["producto"], f["taller"], f["precio"], f["dias"]) for f in ref["items"]] == [
        ("PRD-0001", "TAL-0001", D("11000"), 22), ("PRD-0002", "TAL-0003", D("9000"), 29), ("PRD-0001", "TAL-0002", D("12000"), 31)]
    assert all(f["tamano"] == "CHICO" for f in ref["items"])  # PRD-0003 (GRANDE) and PRD-0004 (Billeteras) stay out


def test_reference_same_category_other_size_is_capped_at_five_comparables():
    mas = [precio("TAL-0003", f"PRD-010{i}", date(2026, 9, i + 1), "5000", 10 + i, tamano="GRANDE") for i in range(4)]
    ref = referencia_de_precio(PRECIOS + mas, "PRD-0009", "Carteras", "MEDIANO", HOY)
    assert ref["nivel"] == "MISMA_CATEGORIA" and ref["tamano"] == "MEDIANO"
    assert len(ref["items"]) == 5  # 8 comparables exist; only the 5 newest come back
    assert [f["fecha"] for f in ref["items"]] == sorted((f["fecha"] for f in ref["items"]), reverse=True)
    assert [f["producto"] for f in ref["items"]] == ["PRD-0001", "PRD-0003", "PRD-0002", "PRD-0001", "PRD-0103"]  # newest first
    assert ref["items"][0]["dias"] == 22 and all(f["precio_anterior"] is None for f in ref["items"])


def test_reference_without_paid_prices_says_so_and_never_invents_one():
    ref = referencia_de_precio(PRECIOS, "PRD-0009", "Bolsos", "CHICO", HOY)
    assert ref == {"nivel": "SIN_DATOS", "categoria": "Bolsos", "tamano": "CHICO", "items": []}
    assert referencia_de_precio(PRECIOS, "PRD-0009", None, None, HOY)["nivel"] == "SIN_DATOS"
    assert referencia_de_precio([], "PRD-0001", "Carteras", "CHICO", HOY)["items"] == []


def test_example_workshops_are_recognised_by_their_note():
    assert es_taller_de_ejemplo('Ejemplo: Robert 24/10, "tres talleres"') is True
    assert es_taller_de_ejemplo("  ejemplo") is True
    assert es_taller_de_ejemplo("Taller real de Lanús") is False and es_taller_de_ejemplo(None) is False


def test_product_controls_cover_the_dates_and_the_repeated_name():
    from test_servicios import producto as datos_de
    base = datos_de(fecha_de_alta=date(2026, 9, 1))
    assert controles_de_producto(base, False) == []
    assert controles_de_producto(base, True) == ["Nombre repetido: cambiá el color o poné un nombre propio"]
    sin_alta = datos_de(fecha_de_alta=None)
    assert controles_de_producto(sin_alta, False) == ["Falta la fecha de alta"]
    raro = datos_de(fecha_de_alta=date(2026, 9, 10), fecha_de_recotizacion=date(2026, 9, 1), fecha_de_cierre=date(2026, 9, 2))
    assert controles_de_producto(raro, False) == ["La recotización es anterior al alta", "El cierre es anterior al alta"]
    producido = datos_de(fecha_de_alta=date(2026, 9, 1), estado_del_ciclo="PRODUCIDO")
    assert controles_de_producto(producido, False) == ["Falta la fecha de cierre"]


def test_warning_severity_by_what_it_blocks():
    assert severidad_de_aviso("Sin precio para MAT-FL01 a esa fecha") == "alta"
    assert severidad_de_aviso("Falta elegir quién lo confecciona") == "alta"
    assert severidad_de_aviso("El kit no tiene componentes") == "alta"
    assert severidad_de_aviso("Falta hilo y cemento") == "media"


def test_price_findings_flag_big_jumps_repeated_dates_zero_and_vat_included():
    filas = [
        {"codigo": "PRE-0001", "material": "MAT-CU01", "color": None, "precio": D("24"), "vigente_desde": date(2026, 9, 1),
         "salto_grande": False, "variacion_pct": None, "iva_incluido": False},
        {"codigo": "PRE-0002", "material": "MAT-CU01", "color": None, "precio": D("46"), "vigente_desde": date(2026, 10, 1),
         "salto_grande": True, "variacion_pct": D("91.67"), "iva_incluido": False},
        {"codigo": "PRE-0003", "material": "MAT-FL01", "color": None, "precio": D("0"), "vigente_desde": date(2026, 9, 3),
         "salto_grande": False, "variacion_pct": None, "iva_incluido": True},
        {"codigo": "PRE-0004", "material": "MAT-FL01", "color": None, "precio": D("5"), "vigente_desde": date(2026, 9, 3),
         "salto_grande": False, "variacion_pct": None, "iva_incluido": False},
    ]
    hallazgos = hallazgos_de_precios(filas)
    mensajes = {(h["entidad"], h["mensaje"].split(":")[0]) for h in hallazgos}
    assert ("PRE-0002", "Salto grande de precio") in mensajes
    assert ("PRE-0003", "Precio en cero") in mensajes and ("PRE-0003", "Cargar sin IVA") in mensajes
    assert any(h["entidad"] in ("PRE-0003", "PRE-0004") and h["mensaje"].startswith("Fecha repetida") for h in hallazgos)
    assert not any(h["entidad"] == "PRE-0001" for h in hallazgos)


def test_parameters_are_unconfirmed_unless_their_source_says_so():
    assert estado_de_parametro("Confirmado por Robert") is None
    assert estado_de_parametro("confirmada") is None
    assert estado_de_parametro("Pendiente: Robert / Casa López")[0] == "media"
    assert estado_de_parametro("Propuesta, a confirmar con Robert")[0] == "media"
    assert estado_de_parametro("DER v3")[0] == "baja" and estado_de_parametro(None)[0] == "baja"


# --- HTTP flows (PostgreSQL) -----------------------------------------------------------------------------------

from test_api_integration import api, dolar_nuevo, producto  # noqa: E402,F401  (fixture and helpers)
from sqlalchemy import text  # noqa: E402
from backend.auth import Usuario, get_verifier  # noqa: E402
from backend.database import get_session  # noqa: E402
from backend.main import app  # noqa: E402

TOTAL_MATERIALES = D("22310.6")  # materials of the seeded model at dollar 1700 (INTERNA product: no sewing)


def taller_nuevo(api, **cambios):
    respuesta = api.post("/talleres", json={"nombre": "Taller Real", "cuit": "30-12345678-9", **cambios})
    assert respuesta.status_code == 201, respuesta.text
    return respuesta.json()


def lote_nuevo(api, producto_codigo, **cambios):
    cuerpo = {"donde_se_hace": "EXTERNA", "taller": "TAL-0001", "fecha_de_envio": "2026-10-05",
              "items": [{"producto": producto_codigo, "cantidad": "10", "taller_precio_cotizado_por_unidad_ars": "12500"}],
              **cambios}
    respuesta = api.post("/ordenes", json=cuerpo)
    assert respuesta.status_code == 201, respuesta.text
    return respuesta.json()


def test_a_workshop_is_created_with_a_server_code_and_cannot_repeat_name_or_cuit(api):
    asignado = taller_nuevo(api, telefono="11 5555 0000", contacto="Marta")
    assert asignado["codigo"] == "TAL-0004" and asignado["activo"] is True and asignado["ejemplo"] is False
    assert asignado["lotes"] == 0 and D(asignado["cobro_total_ars"]) == 0
    assert api.post("/talleres", json={"nombre": "Taller Real"}).status_code == 409
    assert api.post("/talleres", json={"nombre": "Otro", "cuit": "30-12345678-9"}).status_code == 409
    assert api.post("/talleres", json={"nombre": "Sin cuit uno"}).status_code == 201
    assert api.post("/talleres", json={"nombre": "Sin cuit dos", "cuit": ""}).status_code == 201  # empty CUIT is "none"
    assert api.post("/talleres", json={"nombre": ""}).status_code == 422
    assert api.post("/talleres", json={"nombre": "X", "codigo": "TAL-0099"}).status_code == 422


def test_seeded_workshops_are_flagged_as_examples(api):
    lista = {t["codigo"]: t for t in api.get("/talleres").json()}
    assert [t["ejemplo"] for t in lista.values()] == [True, True, True]
    assert taller_nuevo(api)["ejemplo"] is False


def test_a_workshop_is_deactivated_not_deleted(api):
    taller_nuevo(api)
    apagado = api.post("/talleres/TAL-0004/activo", json={"activo": False})
    assert apagado.status_code == 200 and apagado.json()["activo"] is False
    assert any(t["codigo"] == "TAL-0004" and t["activo"] is False for t in api.get("/talleres").json())
    assert api.post("/talleres/TAL-0004/activo", json={"activo": True}).json()["activo"] is True
    assert api.post("/talleres/TAL-9999/activo", json={"activo": False}).status_code == 404
    assert api.post("/talleres/TAL-0004/activo", json={}).status_code == 422


def test_a_lot_is_costed_with_materials_of_today_plus_the_workshop_price(api):
    codigo = producto(api, quien_lo_confecciona="EXTERNA")["codigo"]
    dolar_nuevo(api)
    taller_nuevo(api)
    lote = lote_nuevo(api, codigo, taller="TAL-0004")
    assert lote["codigo"] == "LOT-0001"
    fila = api.get("/ordenes").json()[0]
    assert (fila["codigo"], fila["productos"], fila["estado"], fila["periodo"]) == ("LOT-0001", 1, "PLANIFICADA", "2026-10")
    assert D(fila["unidades"]) == 10 and D(fila["total_cotizado"]) == D("125000") and D(fila["total_cobrado"]) == 0
    assert D(fila["costo_total"]) == 10 * (TOTAL_MATERIALES + D("12500"))
    assert D(fila["costo_promedio_por_unidad"]) == TOTAL_MATERIALES + D("12500") and fila["avisos"] == []
    assert fila["taller"] == "TAL-0004" and fila["taller_nombre"] == "Taller Real"
    detalle = api.get("/ordenes/LOT-0001").json()
    item = detalle["items"][0]
    assert (item["codigo"], item["producto"]) == ("LIT-0001", codigo)
    assert D(item["confeccion_por_unidad"]) == D("12500") and D(item["materiales_por_unidad"]) == TOTAL_MATERIALES
    assert D(item["costo_por_unidad"]) == TOTAL_MATERIALES + D("12500")
    assert D(item["total_linea"]) == 10 * (TOTAL_MATERIALES + D("12500"))
    assert isinstance(item["costo_por_unidad"], str)
    assert [e["estado"] for e in detalle["estados"]] == ["PLANIFICADA"]  # creation writes the first history row
    assert api.get("/ordenes/LOT-9999").status_code == 404


def test_recording_the_paid_price_changes_the_lot_cost_in_place(api):
    codigo = producto(api, quien_lo_confecciona="EXTERNA")["codigo"]
    dolar_nuevo(api)
    lote_nuevo(api, codigo)
    cambiado = api.post("/ordenes/LOT-0001/items/LIT-0001/precios", json={"pagado": "11000"})
    assert cambiado.status_code == 200, cambiado.text
    item = cambiado.json()["items"][0]
    assert D(item["pagado"]) == 11000 and D(item["cotizado"]) == 12500  # the quote is kept
    assert D(item["confeccion_por_unidad"]) == D("11000")  # paid wins over quoted
    assert D(cambiado.json()["total_cobrado"]) == D("110000")
    assert D(api.get("/ordenes").json()[0]["costo_total"]) == 10 * (TOTAL_MATERIALES + D("11000"))
    solo_cotizado = api.post("/ordenes/LOT-0001/items/LIT-0001/precios", json={"cotizado": "13000"}).json()["items"][0]
    assert D(solo_cotizado["cotizado"]) == 13000 and D(solo_cotizado["pagado"]) == 11000
    assert api.post("/ordenes/LOT-0001/items/LIT-0001/precios", json={}).status_code == 422
    assert api.post("/ordenes/LOT-0001/items/LIT-0001/precios", json={"pagado": "-1"}).status_code == 422
    assert api.post("/ordenes/LOT-0001/items/LIT-0001/precios", json={"pagado": "1", "total": "1"}).status_code == 422
    assert api.post("/ordenes/LOT-0001/items/LIT-9999/precios", json={"pagado": "1"}).status_code == 404
    assert api.post("/ordenes/LOT-9999/items/LIT-0001/precios", json={"pagado": "1"}).status_code == 404
    lote_nuevo(api, codigo)  # LOT-0002 / LIT-0002: an item of another lot cannot be priced through this one
    assert api.post("/ordenes/LOT-0001/items/LIT-0002/precios", json={"pagado": "1"}).status_code == 404


def test_items_can_be_added_to_an_existing_lot(api):
    codigo = producto(api)["codigo"]
    lote_nuevo(api, codigo, donde_se_hace="INTERNA", taller=None, persona="PER-0003")
    agregado = api.post("/ordenes/LOT-0001/items", json={"producto": codigo, "cantidad": "4"})
    assert agregado.status_code == 201, agregado.text
    assert [i["codigo"] for i in agregado.json()["items"]] == ["LIT-0001", "LIT-0002"]
    assert api.post("/ordenes/LOT-0001/items", json={"producto": "PRD-9999", "cantidad": "1"}).status_code == 422
    assert api.post("/ordenes/LOT-9999/items", json={"producto": codigo, "cantidad": "1"}).status_code == 404
    assert api.post("/ordenes/LOT-0001/items", json={"producto": codigo}).status_code == 422
    assert api.get("/ordenes/LOT-0001").json()["donde_se_hace"] == "INTERNA"


def test_state_changes_append_history_and_closing_needs_the_delivery_date(api):
    codigo = producto(api)["codigo"]
    lote_nuevo(api, codigo)
    avance = api.post("/ordenes/LOT-0001/estado", json={"estado": "EN_CORTE", "fecha": "2026-10-06", "quien": "PER-0002"})
    assert avance.status_code == 201, avance.text
    assert avance.json()["estado"] == "EN_CORTE"
    assert [(e["estado"], e["fecha"], e["quien"]) for e in avance.json()["estados"]][-1] == ("EN_CORTE", "2026-10-06", "PER-0002")
    sin_entrega = api.post("/ordenes/LOT-0001/estado", json={"estado": "CERRADA", "fecha": "2026-10-20"})
    assert sin_entrega.status_code == 422 and "entrega" in sin_entrega.json()["detail"]
    assert api.get("/ordenes/LOT-0001").json()["estado"] == "EN_CORTE"  # nothing was stored
    cierre = api.post("/ordenes/LOT-0001/estado",
                      json={"estado": "CERRADA", "fecha": "2026-10-20", "fecha_de_entrega": "2026-10-19"})
    assert cierre.status_code == 201
    assert cierre.json()["estado"] == "CERRADA" and cierre.json()["fecha_de_entrega"] == "2026-10-19"
    assert cierre.json()["periodo"] == "2026-10" and len(cierre.json()["estados"]) == 3
    for estado in ("EN_CONFECCION", "CERRADA"):
        reabrir = api.post("/ordenes/LOT-0001/estado", json={"estado": estado, "fecha": "2026-10-21"})
        assert reabrir.status_code == 409, estado
    assert len(api.get("/ordenes/LOT-0001").json()["estados"]) == 3  # rejected changes leave no history
    assert api.post("/ordenes/LOT-9999/estado", json={"estado": "LISTA", "fecha": "2026-10-21"}).status_code == 404


def test_state_change_validation(api):
    codigo = producto(api)["codigo"]
    lote_nuevo(api, codigo)
    assert api.post("/ordenes/LOT-0001/estado", json={"estado": "LISTA"}).status_code == 422  # date is required
    assert api.post("/ordenes/LOT-0001/estado", json={"estado": "INVENTADO", "fecha": "2026-10-06"}).status_code == 422
    assert api.post("/ordenes/LOT-0001/estado", json={"estado": "LISTA", "fecha": "2026-10-06", "quien": "PER-9999"}).status_code == 422
    assert api.post("/ordenes/LOT-0001/estado", json={"estado": "LISTA", "fecha": "2026-10-06", "estado_anterior": "x"}).status_code == 422
    assert api.post("/ordenes/LOT-0001/estado", json={"estado": "PLANIFICADA", "fecha": "2026-10-06"}).status_code == 409  # already there
    cerrado_con_entrega = lote_nuevo(api, codigo, fecha_de_entrega="2026-10-12")  # LOT-0002 already has its delivery date
    ok = api.post(f"/ordenes/{cerrado_con_entrega['codigo']}/estado", json={"estado": "CERRADA", "fecha": "2026-10-13"})
    assert ok.status_code == 201 and ok.json()["fecha_de_entrega"] == "2026-10-12"


def test_lot_list_filters(api):
    codigo = producto(api)["codigo"]
    lote_nuevo(api, codigo)
    lote_nuevo(api, codigo, donde_se_hace="INTERNA", taller=None, persona="PER-0003", estado="EN_CORTE")
    assert [o["codigo"] for o in api.get("/ordenes").json()] == ["LOT-0002", "LOT-0001"]  # newest date, then newest code
    assert [o["codigo"] for o in api.get("/ordenes", params={"estado": "EN_CORTE"}).json()] == ["LOT-0002"]
    assert [o["codigo"] for o in api.get("/ordenes", params={"donde": "EXTERNA"}).json()] == ["LOT-0001"]
    assert [o["codigo"] for o in api.get("/ordenes", params={"taller": "TAL-0001"}).json()] == ["LOT-0001"]
    assert api.get("/ordenes", params={"estado": "NADA"}).status_code == 422
    assert api.get("/ordenes", params={"donde": "AFUERA"}).status_code == 422
    en_casa = [o for o in api.get("/ordenes").json() if o["codigo"] == "LOT-0002"][0]
    assert en_casa["persona"] == "PER-0003" and en_casa["persona_nombre"] == "Hugo"


def test_a_lot_without_a_workshop_or_a_date_warns(api):
    codigo = producto(api)["codigo"]
    dolar_nuevo(api)
    lote_nuevo(api, codigo, taller=None, fecha_de_envio=None)
    fila = api.get("/ordenes").json()[0]
    assert "Falta el taller" in fila["avisos"] and "Falta la fecha de envío" in fila["avisos"]
    assert fila["periodo"] is None


def test_house_vs_workshop_endpoint(api):
    codigo = producto(api, quien_lo_confecciona="EXTERNA")["codigo"]
    lote_nuevo(api, codigo, fecha_de_envio="2026-10-20", fecha_de_entrega="2026-11-02",
               items=[{"producto": codigo, "cantidad": "10", "taller_precio_pagado_por_unidad_ars": "1000"}])
    lote_nuevo(api, codigo, donde_se_hace="INTERNA", taller=None, fecha_de_envio="2026-10-10",
               items=[{"producto": codigo, "cantidad": "5"}])
    lote_nuevo(api, codigo, donde_se_hace="INTERNA", taller=None, fecha_de_envio=None,
               items=[{"producto": codigo, "cantidad": "99"}])
    respuesta = api.get("/fabricacion/casa-vs-taller", params={"hasta": "2026-11"}).json()
    assert [t["codigo"] for t in respuesta["talleres"]] == ["TAL-0001", "TAL-0002", "TAL-0003"]
    meses = respuesta["meses"]
    assert len(meses) == 12 and meses[0]["periodo"] == "2026-11" and meses[-1]["periodo"] == "2025-12"
    nov, octubre = meses[0], meses[1]
    assert nov["lotes_taller"] == 1 and D(nov["unidades_taller"]) == 10 and D(nov["pagado_a_talleres"]) == 10000
    assert nov["porcentaje_taller"] == "100.00" and D(nov["unidades_por_taller"]["TAL-0001"]) == 10
    assert octubre["lotes_casa"] == 1 and D(octubre["unidades_casa"]) == 5 and octubre["porcentaje_taller"] == "0.00"
    assert meses[2]["porcentaje_taller"] is None
    assert api.get("/fabricacion/casa-vs-taller", params={"hasta": "2026-13"}).status_code == 422
    assert len(api.get("/fabricacion/casa-vs-taller").json()["meses"]) == 12  # default: up to the current month


def test_workshop_prices_for_a_product_and_for_similar_ones(api):
    a = producto(api, quien_lo_confecciona="EXTERNA")["codigo"]
    b = producto(api, quien_lo_confecciona="EXTERNA")["codigo"]
    otra_categoria = next(m for m in api.get("/modelos").json() if m["categoria"] != "Portafolios")
    c = producto(api, modelo=otra_categoria["codigo"], quien_lo_confecciona="EXTERNA")["codigo"]

    def en_taller(taller, codigo, dia, **precios):
        lote_nuevo(api, codigo, taller=taller, fecha_de_envio=dia, items=[{"producto": codigo, "cantidad": "3", **precios}])

    en_taller("TAL-0001", a, "2026-09-10", taller_precio_pagado_por_unidad_ars="10000")
    en_taller("TAL-0001", a, "2026-10-10", taller_precio_pagado_por_unidad_ars="11000")
    en_taller("TAL-0002", a, "2026-10-01", taller_precio_cotizado_por_unidad_ars="12000")
    en_taller("TAL-0003", b, "2026-10-03", taller_precio_pagado_por_unidad_ars="9000")
    en_taller("TAL-0003", c, "2026-10-04", taller_precio_pagado_por_unidad_ars="7000")
    respuesta = api.get(f"/productos/{a}/precios-talleres")
    assert respuesta.status_code == 200, respuesta.text
    datos = respuesta.json()
    assert datos["producto"] == a and datos["categoria"] == "Portafolios" and datos["veces_en_taller"] == 3
    por_taller = {f["taller"]: f for f in datos["por_taller"]}
    assert por_taller["TAL-0001"]["precio"] == "11000.0000" and por_taller["TAL-0001"]["veces"] == 2
    assert por_taller["TAL-0001"]["precio_anterior"] == "10000.0000" and por_taller["TAL-0001"]["variacion_pct"] == "10.00"
    assert por_taller["TAL-0002"]["precio"] == "12000.0000"
    assert por_taller["TAL-0003"]["hizo"] is False and por_taller["TAL-0003"]["precio"] is None
    parecidos = {(f["producto"], f["taller"]): f for f in datos["parecidos"]}
    assert parecidos[(b, "TAL-0003")]["es_mismo_producto"] is False and parecidos[(a, "TAL-0001")]["es_mismo_producto"] is True
    assert c not in {f["producto"] for f in datos["parecidos"]}  # another category
    referencia = datos["referencia"]  # paid prices only: TAL-0002 just quoted, so it is not a reference
    assert referencia["nivel"] == "MISMO_PRODUCTO" and [f["taller"] for f in referencia["items"]] == ["TAL-0001"]
    assert referencia["items"][0]["precio"] == "11000.0000" and referencia["items"][0]["precio_anterior"] == "10000.0000"
    assert referencia["items"][0]["fecha"] == "2026-10-10" and isinstance(referencia["items"][0]["dias"], int)
    assert api.get(f"/productos/{a}/precios-talleres", params={"mismo_tamano": "false"}).status_code == 200
    assert api.get("/productos/PRD-9999/precios-talleres").status_code == 404


def test_workshop_detail_lists_its_lots_and_adds_up_what_it_charged(api):
    codigo = producto(api, quien_lo_confecciona="EXTERNA")["codigo"]
    taller_nuevo(api)
    lote_nuevo(api, codigo, taller="TAL-0004", items=[
        {"producto": codigo, "cantidad": "10", "taller_precio_pagado_por_unidad_ars": "1000"}])
    lote_nuevo(api, codigo, taller="TAL-0004", fecha_de_envio="2026-10-08", items=[
        {"producto": codigo, "cantidad": "2", "taller_precio_pagado_por_unidad_ars": "1500"}])
    detalle = api.get("/talleres/TAL-0004").json()
    assert detalle["lotes"] == 2 and D(detalle["unidades"]) == 12 and D(detalle["cobro_total_ars"]) == 13000
    assert detalle["ultimo_lote"] == "2026-10-08"
    assert {o["codigo"] for o in detalle["ordenes"]} == {"LOT-0001", "LOT-0002"}
    assert api.get("/talleres/TAL-9999").status_code == 404
    lista = {t["codigo"]: t for t in api.get("/talleres").json()}
    assert lista["TAL-0004"]["lotes"] == 2 and D(lista["TAL-0004"]["cobro_total_ars"]) == 13000
    assert lista["TAL-0001"]["lotes"] == 0 and lista["TAL-0001"]["ultimo_lote"] is None


def test_fixed_cost_periods_and_amount_of_a_pending_row(api):
    periodos = api.get("/costos-fijos/periodos").json()
    assert periodos["vigente"] == "2026-10" and "2026-10" in periodos["periodos"]
    pendiente = next(g for g in api.get("/costos-fijos").json()["gastos"] if g["monto_ars_del_mes"] is None)
    antes = api.get("/costos-fijos").json()
    cargado = api.post(f"/costos-fijos/{pendiente['codigo']}/monto", json={"monto_ars_del_mes": "250000"})
    assert cargado.status_code == 200, cargado.text
    despues = cargado.json()
    assert despues["pendientes"] == antes["pendientes"] - 1
    cambio = D(despues["total_fabrica"]) + D(despues["total_tienda"]) - D(antes["total_fabrica"]) - D(antes["total_tienda"])
    assert cambio == D("250000")
    assert api.post(f"/costos-fijos/{pendiente['codigo']}/monto", json={"monto_ars_del_mes": "1"}).status_code == 409
    fijo = next(g for g in api.get("/costos-fijos").json()["gastos"] if g["monto_ars_del_mes"] is not None)
    assert api.post(f"/costos-fijos/{fijo['codigo']}/monto", json={"monto_ars_del_mes": "1"}).status_code == 409
    assert api.post("/costos-fijos/GF-9999/monto", json={"monto_ars_del_mes": "1"}).status_code == 404
    assert api.post("/costos-fijos/GF-0001/monto", json={"monto_ars_del_mes": "-1"}).status_code == 422
    assert api.post("/costos-fijos/GF-0001/monto", json={}).status_code == 422
    nuevo = api.post("/costos-fijos", json={"periodo": "2027-01", "concepto": "Luz", "fabrica_o_tienda": "FABRICA",
                                            "categoria": "SERVICIOS"})
    assert nuevo.status_code == 201 and nuevo.json()["pendientes"] == 1
    assert "2027-01" in api.get("/costos-fijos/periodos").json()["periodos"]
    assert api.get("/costos-fijos/periodos").json()["periodos"][0] == "2027-01"  # newest first


def hallazgos(api):
    datos = api.get("/calidad").json()
    grupos = {g["clave"]: g for g in datos["grupos"]}
    return datos, grupos


def test_quality_report_shape_and_the_seeded_findings(api):
    datos, grupos = hallazgos(api)
    assert set(datos["resumen"]) == {"alta", "media", "baja", "total"}
    todos = [h for g in datos["grupos"] for h in g["hallazgos"]]
    assert datos["resumen"]["total"] == len(todos) == sum(datos["resumen"][s] for s in ("alta", "media", "baja"))
    assert all(h["severidad"] in ("alta", "media", "baja") and h["entidad"] and h["mensaje"] and h["ruta"].startswith("/")
               for h in todos)
    assert len(grupos["modelos_sin_validar"]["hallazgos"]) == 325 and grupos["modelos_sin_validar"]["total"] == 325
    assert len(grupos["parametros"]["hallazgos"]) == 8
    gastos = grupos["gastos_fijos"]["hallazgos"]
    assert {h["entidad"] for h in gastos if "sin monto" in h["mensaje"]} and any("ficticio" in h["mensaje"] for h in gastos)
    assert all(h["ruta"].startswith("/costos-fijos?periodo=2026-10") for h in gastos)
    materiales = {h["entidad"]: h for h in grupos["materiales"]["hallazgos"]}
    assert set(materiales) == {"MAT-CU03", "MAT-CU04"} and materiales["MAT-CU03"]["severidad"] == "baja"
    assert "talleres" not in grupos or grupos["talleres"]["hallazgos"] == []


def test_quality_flags_products_lots_example_workshops_and_recotizar(api):
    sin_quien = api.post("/productos", json={"modelo": "MOD-0001", "cuero": "MAT-CU01", "fecha_de_alta": "2026-09-03"}).json()["codigo"]
    igual_a = producto(api)["codigo"]
    igual_b = producto(api)["codigo"]
    api.post(f"/productos/{igual_a}/cotizaciones", json={"tipo": "INICIAL"})
    dolar_nuevo(api)
    lote_nuevo(api, igual_a, taller=None, fecha_de_envio=None)
    lote_nuevo(api, igual_a, estado="CERRADA")
    _, grupos = hallazgos(api)
    productos = grupos["productos"]["hallazgos"]
    de = lambda entidad: [h["mensaje"] for h in productos if h["entidad"] == entidad]  # noqa: E731
    assert "Falta elegir quién lo confecciona" in de(sin_quien)
    assert "Nombre repetido: cambiá el color o poné un nombre propio" in de(igual_a)
    assert "Nombre repetido: cambiá el color o poné un nombre propio" in de(igual_b)
    assert all(h["ruta"] == f"/productos/{h['entidad']}" for h in productos)
    assert next(h for h in productos if h["entidad"] == sin_quien and "quién" in h["mensaje"])["severidad"] == "alta"
    assert [h["entidad"] for h in grupos["recotizar"]["hallazgos"]] == [igual_a]
    mensajes_lotes = {(h["entidad"], h["mensaje"]) for h in grupos["lotes"]["hallazgos"]}
    assert ("LOT-0001", "Falta el taller") in mensajes_lotes and ("LOT-0001", "Falta la fecha de envío") in mensajes_lotes
    assert ("LOT-0002", "Falta la fecha de entrega (cierra la cotización final)") in mensajes_lotes
    assert all(h["ruta"] == f"/fabricacion/{h['entidad']}" for h in grupos["lotes"]["hallazgos"] if h["entidad"].startswith("LOT-"))
    ejemplo = grupos["talleres"]["hallazgos"]
    assert [h["entidad"] for h in ejemplo] == ["TAL-0001"] and ejemplo[0]["ruta"] == "/talleres/TAL-0001"


def test_quality_asks_for_the_dollar_once_when_there_is_none(api):
    sesion = app.dependency_overrides[get_session]()  # the fixture's session: rolled back at the end of the test
    sesion.execute(text("DELETE FROM costos.tipo_cambio"))
    producto(api)
    _, grupos = hallazgos(api)
    sin_dolar = [h for h in grupos["productos"]["hallazgos"] if "dólar" in h["mensaje"]]
    assert len(sin_dolar) == 1 and sin_dolar[0]["severidad"] == "alta" and sin_dolar[0]["ruta"] == "/dolar"


def test_new_endpoints_honour_roles(api):
    codigo = producto(api)["codigo"]
    lote_nuevo(api, codigo)
    app.dependency_overrides[get_verifier] = lambda: (lambda request: Usuario(id="u", role="consulta"))
    escrituras = [
        ("/talleres", {"nombre": "Nuevo"}), ("/talleres/TAL-0001/activo", {"activo": False}),
        ("/ordenes/LOT-0001/estado", {"estado": "LISTA", "fecha": "2026-10-06"}),
        ("/ordenes/LOT-0001/items", {"producto": codigo, "cantidad": "1"}),
        ("/ordenes/LOT-0001/items/LIT-0001/precios", {"pagado": "1"}),
        ("/costos-fijos/GF-0001/monto", {"monto_ars_del_mes": "1"}),
    ]
    for ruta, cuerpo in escrituras:
        assert api.post(ruta, json=cuerpo).status_code == 403, ruta
    for ruta in ("/ordenes", "/ordenes/LOT-0001", "/talleres/TAL-0001", "/fabricacion/casa-vs-taller",
                 "/costos-fijos/periodos", "/calidad", f"/productos/{codigo}/precios-talleres"):
        assert api.get(ruta).status_code == 200, ruta
    assert api.get("/ordenes/LOT-0001").json()["estado"] == "PLANIFICADA"  # the refused writes changed nothing
    assert api.get("/talleres/TAL-0001").json()["activo"] is True


def test_people_are_listed_and_fixed_costs_carry_their_own_grand_total(api):
    personas = api.get("/personas").json()
    assert [p["codigo"] for p in personas][:3] == ["PER-0001", "PER-0002", "PER-0003"]
    assert {"codigo", "nombre", "rol", "activo"} == set(personas[0])
    mes = api.get("/costos-fijos").json()
    assert D(mes["total"]) == D(mes["total_fabrica"]) + D(mes["total_tienda"]) and isinstance(mes["total"], str)
