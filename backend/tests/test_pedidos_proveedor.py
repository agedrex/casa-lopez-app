"""Supplier orders (`PED-nnnn`): what arrived, how it came, and the price each line creates.

The first block needs no database (pure rule, models, migration 0018). The second runs against disposable PostgreSQL
(skipped without TEST_DATABASE_URL), inside a transaction that is rolled back.
"""

import runpy
from datetime import date
from decimal import Decimal as D
from pathlib import Path

import pytest
from sqlalchemy import CheckConstraint, UniqueConstraint, func, insert, select, text
from sqlalchemy.exc import IntegrityError

from backend import api as api_module
from backend import proveedores
from backend.auth import Usuario, get_verifier
from backend.main import app
from backend.models import (
    UNITS, Etapa, Material, PedidoLinea, PedidoProveedor, PrecioMaterial, Proveedor,
)

from test_costos_fijos_correccion_integration import api  # noqa: E402,F401  (fixture; its client also carries `.session`)

VERSIONS = Path(__file__).parents[1] / "migrations" / "versions"
DAY = "2026-11-05"
TELA, FLEX = "MAT-FO02", "MAT-FL01"  # both m2 in the seeds


# --- No database --------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("price, content, expected", [
    (D("12000"), D("50"), D("240.0000")),          # a roll of 50 m2 at 12000
    (D("1500"), D("500"), D("3.0000")),            # a spool of 500 m
    (D("100"), D("3"), D("33.3333")),              # rounded to the 4 decimals of money()
    (D("200"), D("3"), D("66.6667")),
    (D("0"), D("10"), D("0.0000")),
])
def test_unit_price_is_the_price_of_a_presentation_over_its_content(price, content, expected):
    assert proveedores.unit_price(price, content) == expected


def test_the_unit_list_has_the_metre_and_keeps_the_old_units():
    assert UNITS == ("m2", "cm", "juego", "unidad", "USD", "m")


def test_the_models_declare_the_order_rules():
    order, line = PedidoProveedor.__table__, PedidoLinea.__table__
    assert order.schema == line.schema == "costos"
    assert order.c.codigo.unique and not order.c.proveedor_id.nullable and not order.c.fecha_de_recepcion.nullable
    assert not order.c.creado_por.nullable
    assert all(order.c[name].nullable for name in ("remito", "documento_id", "nota"))
    assert (line.c.cantidad_presentaciones.type.precision, line.c.cantidad_presentaciones.type.scale) == (12, 6)
    assert (line.c.precio_por_presentacion.type.precision, line.c.precio_por_presentacion.type.scale) == (14, 4)
    assert not line.c.precio_material_id.nullable and not line.c.presentacion.nullable
    checks = {c.name: str(c.sqltext) for c in line.constraints if isinstance(c, CheckConstraint)}
    assert checks["ck_pedido_linea_cantidad_positiva"] == "cantidad_presentaciones > 0"
    assert checks["ck_pedido_linea_contenido_positivo"] == "contenido_por_presentacion > 0"
    assert checks["ck_pedido_linea_precio_no_negativo"] == "precio_por_presentacion >= 0"
    assert checks["ck_pedido_linea_moneda"] == "moneda IN ('ARS','USD')"
    assert ("pedido_id", "orden") in [tuple(c.columns.keys()) for c in line.constraints if isinstance(c, UniqueConstraint)]


def test_revision_0018_creates_the_tables_replaces_the_unit_checks_and_reverses_everything(monkeypatch):
    from test_migrations import load_revision
    operations, base = load_revision(monkeypatch, "0003_der_v3.py")
    base["upgrade"]()
    for filename in ("0005_gasto_reemplaza_a.py", "0006_precio_venta.py", "0007_proveedores_documentos.py",
                     "0011_precio_material_proveedor.py"):
        runpy.run_path(str(VERSIONS / filename))["upgrade"]()
    revision = runpy.run_path(str(VERSIONS / "0018_pedidos_proveedor.py"))
    assert revision["revision"] == "0018_pedidos_proveedor" and revision["down_revision"] == "0017_formulario_modelo"
    revision["upgrade"]()
    created = list(operations.metadata.tables)
    assert created.index("costos.pedido_proveedor") < created.index("costos.pedido_linea")
    assert {fk.target_fullname for fk in operations.metadata.tables["costos.pedido_linea"].foreign_keys} == {
        "costos.pedido_proveedor.id", "costos.material.id", "costos.precio_material.id"}
    assert {fk.target_fullname for fk in operations.metadata.tables["costos.pedido_proveedor"].foreign_keys} == {
        "costos.proveedor.id", "costos.documento_proveedor.id"}

    def unit_checks():
        return {c.name: str(c.sqltext) for table in ("material", "precio_material")
                for c in operations.metadata.tables[f"costos.{table}"].constraints
                if isinstance(c, CheckConstraint) and "unidad" in c.name}

    assert unit_checks() == {
        "ck_material_unidad_de_consumo": "unidad_de_consumo IN ('m2','cm','juego','unidad','USD','m')",
        "ck_precio_material_unidad_del_precio": "unidad_del_precio IN ('m2','cm','juego','unidad','USD','m')"}
    assert operations.dropped_constraints == ["ck_material_unidad_de_consumo", "ck_precio_material_unidad_del_precio"]
    operations.dropped.clear()
    operations.dropped_constraints.clear()
    revision["downgrade"]()
    assert operations.dropped == ["pedido_linea", "pedido_proveedor"]  # the child first
    assert unit_checks() == {
        "ck_material_unidad_de_consumo": "unidad_de_consumo IN ('m2','cm','juego','unidad','USD')",
        "ck_precio_material_unidad_del_precio": "unidad_del_precio IN ('m2','cm','juego','unidad','USD')"}
    assert "FAILS" in revision["__doc__"] and "'m'" in revision["__doc__"]


# --- PostgreSQL ---------------------------------------------------------------------------------------------------

def como(role, usuario="admin-1"):
    app.dependency_overrides[get_verifier] = lambda: (lambda request: Usuario(id=usuario, role=role))


def make_supplier(api, name="Rouez"):
    response = api.post("/proveedores", json={"nombre": name})
    assert response.status_code == 201, response.text
    return response.json()["codigo"]


def line(material=TELA, **extra):
    return {"material": material, "cantidad_presentaciones": "2", "presentacion": "ROLLO",
            "contenido_por_presentacion": "50", "precio_por_presentacion": "12000", "moneda": "ARS", **extra}


def order(lineas=None, **extra):
    return {"fecha_de_recepcion": DAY, "lineas": lineas if lineas is not None else [line()], **extra}


def counts(api):
    return (api.session.scalar(select(func.count()).select_from(PedidoProveedor)),
            api.session.scalar(select(func.count()).select_from(PedidoLinea)),
            api.session.scalar(select(func.count()).select_from(PrecioMaterial)))


def material_in_metres(api):
    stage = api.session.scalar(select(Etapa.id).where(Etapa.codigo == "HILO_CEMENTO"))
    row = Material(codigo="MAT-HI99", nombre="Hilo encerado", etapa_id=stage, unidad_de_consumo="m")
    api.session.add(row)
    api.session.flush()
    return row


def test_pg_an_order_creates_the_price_per_unit_dated_at_the_reception_linked_to_the_supplier(api):
    como("admin")
    code = make_supplier(api)
    response = api.post(f"/proveedores/{code}/pedidos", json=order(
        [line(), line(FLEX, contenido_por_presentacion="3", precio_por_presentacion="100", moneda="USD", iva_incluido=True)],
        remito="R-0001-123", nota="Llegó completo"))
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["codigo"] == "PED-0001" and body["proveedor"] == code and body["fecha_de_recepcion"] == DAY
    assert body["remito"] == "R-0001-123" and body["nota"] == "Llegó completo" and body["creado_por"] == "admin-1"
    first, second = body["lineas"]
    assert [first["orden"], second["orden"]] == [1, 2]
    assert (first["material"], first["material_nombre"], first["unidad_de_consumo"]) == (TELA, "Tela forrería (Gross textil 1 × 1,50)", "m2")
    # Quantities travel as strings (no float).
    assert first["cantidad_presentaciones"] == "2.000000" and first["contenido_por_presentacion"] == "50.000000"
    assert first["precio_por_presentacion"] == "12000.0000" and first["precio_unitario"] == "240.0000"
    assert second["precio_unitario"] == "33.3333" and second["moneda"] == "USD" and second["iva_incluido"] is True
    # The prices are real rows: unit = price / content, in the consumption unit, dated the reception, linked to the supplier.
    supplier_id = api.session.scalar(select(Proveedor.id).where(Proveedor.codigo == code))
    for stored, expected in ((first, D("240")), (second, D("33.3333"))):
        price = api.session.scalar(select(PrecioMaterial).where(PrecioMaterial.codigo == stored["precio_codigo"]))
        assert price.precio == expected and price.vigente_desde == date(2026, 11, 5) and price.proveedor_id == supplier_id
        assert price.unidad_del_precio == "m2" and price.proveedor == code and price.color_id is None
        assert api.session.scalar(select(PedidoLinea.precio_material_id).where(PedidoLinea.orden == stored["orden"])) == price.id
    assert api.session.scalar(select(PrecioMaterial.iva_incluido).where(PrecioMaterial.codigo == second["precio_codigo"])) is True
    # The supplier's page sees the new prices.
    materials = {m["material"]: m for m in api.get(f"/proveedores/{code}/materiales").json()["materiales"]}
    assert materials[TELA]["ultimo_precio"] == "240.0000" and materials[FLEX]["moneda"] == "USD"


def test_pg_codes_follow_one_another_and_the_list_is_newest_reception_first(api):
    como("admin")
    code = make_supplier(api)
    api.post(f"/proveedores/{code}/pedidos", json=order([line()], fecha_de_recepcion="2026-11-01"))
    api.post(f"/proveedores/{code}/pedidos", json=order([line(FLEX)], fecha_de_recepcion="2026-11-09"))
    listed = api.get(f"/proveedores/{code}/pedidos").json()
    assert [(o["codigo"], o["fecha_de_recepcion"]) for o in listed] == [("PED-0002", "2026-11-09"), ("PED-0001", "2026-11-01")]
    assert listed[0]["lineas"][0]["material"] == FLEX and listed[0]["lineas"][0]["precio_unitario"] == "240.0000"
    other = make_supplier(api, "Acropol")
    assert api.get(f"/proveedores/{other}/pedidos").json() == []  # scoped to the supplier


def test_pg_a_failing_line_saves_no_order_and_no_price_and_names_the_line(api):
    como("admin")
    code = make_supplier(api)
    before = counts(api)
    response = api.post(f"/proveedores/{code}/pedidos", json=order([line(), line("MAT-NO-EXISTE")]))
    assert response.status_code == 422
    assert "Línea 2" in response.json()["detail"] and "MAT-NO-EXISTE" in response.json()["detail"]
    assert counts(api) == before
    # The failed order did not use up a code.
    assert api.post(f"/proveedores/{code}/pedidos", json=order()).json()["codigo"] == "PED-0001"


def test_pg_a_price_already_there_for_that_material_and_date_is_409_and_nothing_is_saved(api):
    como("admin")
    code = make_supplier(api)
    assert api.post("/precios", json={"material": FLEX, "precio": "5", "moneda": "ARS", "unidad_del_precio": "m2",
                                      "vigente_desde": DAY}).status_code == 201
    before = counts(api)
    response = api.post(f"/proveedores/{code}/pedidos", json=order([line(), line(FLEX)]))
    assert response.status_code == 409
    assert "Línea 2" in response.json()["detail"] and FLEX in response.json()["detail"]
    assert counts(api) == before


def test_pg_the_same_material_twice_in_one_order_is_409_and_nothing_is_saved(api):
    como("admin")
    code = make_supplier(api)
    before = counts(api)
    response = api.post(f"/proveedores/{code}/pedidos", json=order([line(), line()]))
    assert response.status_code == 409 and "Línea 2" in response.json()["detail"]
    assert counts(api) == before


def test_pg_the_whole_order_is_one_commit_and_the_old_price_endpoints_still_commit_per_call(api, monkeypatch):
    como("admin")
    code = make_supplier(api)
    commits = []
    real_commit = api.session.commit
    monkeypatch.setattr(api.session, "commit", lambda: (commits.append(1), real_commit())[1])
    assert api.post(f"/proveedores/{code}/pedidos", json=order([line(), line(FLEX)])).status_code == 201
    assert len(commits) == 1  # two prices and the order, saved together
    commits.clear()
    body = {"material": TELA, "precio": "7", "moneda": "ARS", "unidad_del_precio": "m2", "vigente_desde": "2026-11-06"}
    assert api.post("/precios", json=body).status_code == 201 and len(commits) == 1  # default: commit per price
    commits.clear()
    assert api.post(f"/proveedores/{code}/precios", json={**body, "vigente_desde": "2026-11-07"}).status_code == 201
    assert len(commits) == 1


def test_pg_the_unit_metre_is_accepted_and_an_unknown_unit_is_rejected(api):
    como("admin")
    code = make_supplier(api)
    thread = material_in_metres(api)
    response = api.post(f"/proveedores/{code}/pedidos", json=order([line(
        thread.codigo, presentacion="CARRETE", contenido_por_presentacion="500", precio_por_presentacion="1500")]))
    assert response.status_code == 201, response.text
    created = response.json()["lineas"][0]
    assert created["unidad_de_consumo"] == "m" and created["precio_unitario"] == "3.0000"
    assert api.session.scalar(select(PrecioMaterial.unidad_del_precio).where(PrecioMaterial.codigo == created["precio_codigo"])) == "m"
    # The API list and the database list both refuse anything else.
    assert api.post("/precios", json={"material": thread.codigo, "precio": "1", "moneda": "ARS", "unidad_del_precio": "km",
                                      "vigente_desde": "2026-11-06"}).status_code == 422
    with pytest.raises(IntegrityError):
        with api.session.begin_nested():
            api.session.execute(text("update costos.material set unidad_de_consumo = 'km' where codigo = :c"), {"c": thread.codigo})
    with pytest.raises(IntegrityError):
        with api.session.begin_nested():
            api.session.execute(text("update costos.precio_material set unidad_del_precio = 'km' where codigo = :c"),
                                {"c": created["precio_codigo"]})
    # The old units keep working: the price of an m2 material must still be in m2.
    assert api.post("/precios", json={"material": TELA, "precio": "1", "moneda": "ARS", "unidad_del_precio": "m",
                                      "vigente_desde": "2026-11-06"}).status_code == 422


def test_pg_the_document_must_be_one_of_this_supplier(api):
    como("admin")
    code, other = make_supplier(api), make_supplier(api, "Acropol")
    png = b"\x89PNG\r\n\x1a\n" + b"pixels-1"
    document = api.post(f"/proveedores/{code}/documentos", data={"tipo": "FACTURA"}, files={"archivo": ("f.png", png, "image/png")})
    assert document.status_code == 201, document.text
    document_id = document.json()["id"]
    before = counts(api)
    refused = api.post(f"/proveedores/{other}/pedidos", json=order(documento_id=document_id))
    assert refused.status_code == 422 and counts(api) == before
    assert api.post(f"/proveedores/{code}/pedidos", json=order(documento_id=999999)).status_code == 422
    accepted = api.post(f"/proveedores/{code}/pedidos", json=order(documento_id=document_id))
    assert accepted.status_code == 201 and accepted.json()["documento_id"] == document_id


@pytest.mark.parametrize("changes", [
    {"lineas": []},
    {"fecha_de_recepcion": "no-es-fecha"},
    {"proveedor": "PRV-0002"},                      # the supplier comes from the URL only
    {"creado_por": "otro"},                         # nor the author
    {"lineas": [{**line(), "cantidad_presentaciones": "0"}]},
    {"lineas": [{**line(), "contenido_por_presentacion": "0"}]},
    {"lineas": [{**line(), "precio_por_presentacion": "-1"}]},
    {"lineas": [{**line(), "presentacion": "   "}]},
    {"lineas": [{**line(), "presentacion": ""}]},
    {"lineas": [{**line(), "moneda": "EUR"}]},
    {"lineas": [{**line(), "unidad_del_precio": "m2"}]},   # the unit is the material's, never typed
    {"lineas": [{**line(), "precio_unitario": "1"}]},      # the unit price is computed
])
def test_pg_invalid_orders_are_422_and_save_nothing(api, changes):
    como("admin")
    code = make_supplier(api)
    before = counts(api)
    response = api.post(f"/proveedores/{code}/pedidos", json={**order(), **changes})
    assert response.status_code == 422, response.text
    assert counts(api) == before


def test_pg_a_free_price_of_zero_is_allowed_and_an_unknown_supplier_is_404(api):
    como("admin")
    code = make_supplier(api)
    assert api.post(f"/proveedores/{code}/pedidos", json=order([line(precio_por_presentacion="0")])).status_code == 201
    assert api.post("/proveedores/PRV-9999/pedidos", json=order()).status_code == 404
    assert api.get("/proveedores/PRV-9999/pedidos").status_code == 404


def test_pg_orders_are_append_only_there_is_no_way_to_edit_or_delete_one(api):
    como("admin")
    code = make_supplier(api)
    created = api.post(f"/proveedores/{code}/pedidos", json=order()).json()
    paths = [f"/proveedores/{code}/pedidos", f"/proveedores/{code}/pedidos/{created['codigo']}"]
    for path in paths:
        for method in ("PUT", "PATCH", "DELETE"):
            assert api.request(method, path, json=order()).status_code in (404, 405), (method, path)
    assert api.post(paths[1], json=order()).status_code in (404, 405)
    routes = {(m, r.path) for r in api_module.router.routes for m in r.methods if "pedidos" in r.path}
    assert routes == {("GET", "/proveedores/{codigo}/pedidos"), ("POST", "/proveedores/{codigo}/pedidos")}
    assert len(api.get(f"/proveedores/{code}/pedidos").json()) == 1


def test_pg_only_admin_registers_and_reads_gerente_and_taller_see_nothing(api):
    como("admin")
    code = make_supplier(api)
    api.post(f"/proveedores/{code}/pedidos", json=order())
    before = counts(api)
    como("gerente")
    assert api.get(f"/proveedores/{code}/pedidos").status_code == 403
    assert api.post(f"/proveedores/{code}/pedidos", json=order([line(FLEX)])).status_code == 403
    como("taller")
    assert api.get(f"/proveedores/{code}/pedidos").status_code == 403
    assert api.post(f"/proveedores/{code}/pedidos", json=order([line(FLEX)])).status_code == 403
    assert counts(api) == before


def test_pg_the_database_checks_the_line_rules(api):
    como("admin")
    code = make_supplier(api)
    created = api.post(f"/proveedores/{code}/pedidos", json=order()).json()
    pedido_id = api.session.scalar(select(PedidoProveedor.id).where(PedidoProveedor.codigo == created["codigo"]))
    material_id = api.session.scalar(select(Material.id).where(Material.codigo == TELA))
    price_id = api.session.scalar(select(PedidoLinea.precio_material_id))
    base = {"pedido_id": pedido_id, "orden": 2, "material_id": material_id, "cantidad_presentaciones": D("1"),
            "presentacion": "CAJA", "contenido_por_presentacion": D("1"), "precio_por_presentacion": D("1"),
            "moneda": "ARS", "precio_material_id": price_id}
    for changes in ({"cantidad_presentaciones": D("0")}, {"contenido_por_presentacion": D("0")},
                    {"precio_por_presentacion": D("-1")}, {"moneda": "EUR"}, {"orden": 1}, {"precio_material_id": None},
                    {"presentacion": None}):
        with pytest.raises(IntegrityError):
            with api.session.begin_nested():
                api.session.execute(insert(PedidoLinea).values(**{**base, **changes}))
    with api.session.begin_nested():  # and the valid row goes in
        api.session.execute(insert(PedidoLinea).values(**base))
