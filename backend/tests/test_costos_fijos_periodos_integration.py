"""Regression: the period list after annulling, creating, copying and exporting (skipped without TEST_DATABASE_URL)."""
from backend import servicios
from test_costos_fijos_anular_integration import api, como, lote_con  # noqa: F401

NUEVO = {"concepto": "Seguro", "fabrica_o_tienda": "TIENDA", "categoria": "OTROS"}


def periodos(api):
    return api.get("/costos-fijos/periodos").json()


def codigos(api, periodo):
    return [g["codigo"] for g in api.get("/costos-fijos", params={"periodo": periodo}).json()["gastos"]]


def test_p1_vigente_stays_listed_even_with_every_row_annulled_and_can_be_copied_into(api):
    como("admin")
    vigente = periodos(api)["vigente"]
    assert vigente and vigente in periodos(api)["periodos"]
    for c in codigos(api, vigente):
        assert api.post(f"/costos-fijos/{c}/anular").status_code == 200
    assert codigos(api, vigente) == []
    p = periodos(api)
    assert p["vigente"] == vigente and vigente in p["periodos"]
    assert api.post("/costos-fijos", json={"periodo": "2027-01", **NUEVO, "monto_ars_del_mes": "5"}).status_code == 201
    copia = api.post("/costos-fijos/copiar", json={"desde": "2027-01", "hasta": vigente})
    assert copia.status_code in (200, 201), copia.text
    assert len(codigos(api, vigente)) == 1


def test_p2_month_with_one_live_row_stays(api):
    como("admin")
    for concepto in ("A", "B"):
        assert api.post("/costos-fijos", json={"periodo": "2027-02", **NUEVO, "concepto": concepto}).status_code == 201
    assert "2027-02" in periodos(api)["periodos"]
    assert api.post(f"/costos-fijos/{codigos(api, '2027-02')[0]}/anular").status_code == 200
    assert "2027-02" in periodos(api)["periodos"]


def test_p3_corrected_then_correction_annulled_leaves_the_list_and_get_still_works(api):
    como("admin")
    api.post("/costos-fijos", json={"periodo": "2027-03", **NUEVO, "monto_ars_del_mes": "10"})
    c = codigos(api, "2027-03")[0]
    assert api.post(f"/costos-fijos/{c}/corregir", json={"monto_ars_del_mes": "20"}).status_code == 201
    actual = codigos(api, "2027-03")[0]
    assert actual != c and "2027-03" in periodos(api)["periodos"]
    assert api.post(f"/costos-fijos/{actual}/anular").status_code == 200
    assert "2027-03" not in periodos(api)["periodos"]
    mes = api.get("/costos-fijos", params={"periodo": "2027-03"})
    assert mes.status_code == 200 and mes.json()["gastos"] == [] and mes.json()["total"] in ("0", "0.0000", 0)


def test_p4_batch_annul_of_every_row_leaves_the_list_and_export(api):
    como("admin")
    api.post("/costos-fijos", json={"periodo": "2027-04", **NUEVO})
    api.post("/costos-fijos", json={"periodo": "2027-04", **NUEVO, "concepto": "Luz"})
    r = lote_con(api, anulados=codigos(api, "2027-04"), periodo="2027-04")
    assert r.status_code == 200, r.text
    assert "2027-04" not in periodos(api)["periodos"]
    assert "2027-04" not in {p["periodo"] for p in servicios.costos_fijos_de_todos_los_periodos(api.session)}


def test_p5_create_still_lists_new_month(api):
    como("admin")
    r = api.post("/costos-fijos", json={"periodo": "2027-05", **NUEVO, "monto_ars_del_mes": "12.5"})
    assert r.status_code == 201 and r.json()["periodo"] == "2027-05" and r.json()["total"] in ("12.5", "12.5000")
    assert "2027-05" in periodos(api)["periodos"]
    assert periodos(api)["periodos"] == sorted(periodos(api)["periodos"], reverse=True)
