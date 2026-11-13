"""What a supplier sells (`proveedor_producto`, `PPR-nnnn`): a list of products with unit, quantity and reference price.

The first block needs no database (rules, models, migration 0020). The second runs against disposable PostgreSQL
(skipped without TEST_DATABASE_URL), inside a transaction that is rolled back. Rows are append-only: a change of price,
unit or quantity is a new dated row of the same product; the list shows the newest row of each product.
"""

from datetime import date, timedelta
from decimal import Decimal as D

import pytest
from sqlalchemy import CheckConstraint, func, select, text
from sqlalchemy.exc import IntegrityError

from backend import proveedores
from backend.auth import Usuario, get_verifier
from backend.main import app
from backend.models import UNITS, ProveedorProducto

from test_costos_fijos_correccion_integration import api  # noqa: E402,F401  (fixture; its client also carries `.session`)

DAY = "2026-11-05"
TELA = "MAT-FO02"  # m2 in the seeds


# --- No database --------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("price, quantity, expected", [
    (D("14000"), D("1.4"), D("10000.0000")),   # a roll of 1.4 m2 at 14000: 10000 per m2
    (D("8200"), D("1.4"), D("5857.1429")),     # rounded half up to the 4 decimals of money()
    (D("500"), None, D("500.0000")),           # no quantity: the price is already per unit
    (D("100"), D("3"), D("33.3333")),
])
def test_price_per_unit_is_the_price_of_the_presentation_over_its_quantity(price, quantity, expected):
    assert proveedores.price_per_unit(price, quantity) == expected


def test_the_model_declares_the_catalogue_rules_and_reuses_the_closed_unit_list():
    table = ProveedorProducto.__table__
    assert table.schema == "costos" and table.c.codigo.unique
    for required in ("proveedor_id", "nombre", "unidad", "precio_referencial", "moneda", "iva_incluido", "vigente_desde",
                     "creado_por"):
        assert not table.c[required].nullable, required
    for optional in ("material_id", "cantidad", "nota"):
        assert table.c[optional].nullable, optional
    assert (table.c.cantidad.type.precision, table.c.cantidad.type.scale) == (12, 6)
    assert (table.c.precio_referencial.type.precision, table.c.precio_referencial.type.scale) == (14, 4)
    assert {fk.target_fullname for fk in table.foreign_keys} == {"costos.proveedor.id", "costos.material.id"}
    checks = {c.name: str(c.sqltext) for c in table.constraints if isinstance(c, CheckConstraint)}
    assert checks == {
        "ck_proveedor_producto_cantidad_positiva": "cantidad IS NULL OR cantidad > 0",
        "ck_proveedor_producto_precio_positivo": "precio_referencial > 0",
        "ck_proveedor_producto_moneda": "moneda IN ('ARS','USD')",
        "ck_proveedor_producto_unidad": "unidad IN ('m2','cm','juego','unidad','USD','m')",
    }
    assert UNITS == ("m2", "cm", "juego", "unidad", "USD", "m")


def test_revision_0020_creates_the_table_and_the_downgrade_drops_it(monkeypatch):
    from test_migrations import load_revision
    operations, revision = load_revision(monkeypatch, "0020_proveedor_producto.py")
    assert revision["revision"] == "0020_proveedor_producto" and revision["down_revision"] == "0019_modelo_insumo"
    revision["upgrade"]()
    assert list(operations.metadata.tables) == ["costos.proveedor_producto"]
    created = operations.metadata.tables["costos.proveedor_producto"]
    assert {fk.target_fullname for fk in created.foreign_keys} == {"costos.proveedor.id", "costos.material.id"}
    revision["downgrade"]()
    assert operations.dropped == ["proveedor_producto"]
    assert "lost" in revision["__doc__"]


# --- PostgreSQL ---------------------------------------------------------------------------------------------------

def como(role, usuario="admin-1"):
    app.dependency_overrides[get_verifier] = lambda: (lambda request: Usuario(id=usuario, role=role))


def make_supplier(api, name="Rouez"):
    response = api.post("/proveedores", json={"nombre": name})
    assert response.status_code == 201, response.text
    return response.json()["codigo"]


def item(nombre="Flex 1 × 1,40", **extra):
    return {"nombre": nombre, "unidad": "m2", "cantidad": "1.4", "precio_referencial": "14000", "moneda": "ARS", **extra}


def add(api, code, *items):
    return api.post(f"/proveedores/{code}/productos", json={"productos": list(items)})


def count(api):
    return api.session.scalar(select(func.count()).select_from(ProveedorProducto))


def test_pg_adding_products_stores_them_with_a_code_and_lists_the_price_per_unit(api):
    como("admin")
    code = make_supplier(api)
    response = add(api, code, item(nota="Rollo entero"), item("Hilo encerado", unidad="m", cantidad=None,
                                                                 precio_referencial="12.5", moneda="USD", iva_incluido=True))
    assert response.status_code == 201, response.text
    first, second = response.json()
    assert (first["codigo"], second["codigo"]) == ("PPR-0001", "PPR-0002")
    assert first["proveedor"] == code and first["nombre"] == "Flex 1 × 1,40" and first["unidad"] == "m2"
    # Quantities and money travel as strings (no float); the per-unit price is the API's, never the front's.
    assert first["cantidad"] == "1.400000" and first["precio_referencial"] == "14000.0000"
    assert first["precio_por_unidad"] == "10000.0000" and first["iva_incluido"] is False and first["nota"] == "Rollo entero"
    assert first["vigente_desde"] == date.today().isoformat() and first["cargas"] == 1 and first["precio_anterior"] is None
    assert first["material"] is None and first["material_nombre"] is None
    assert second["cantidad"] is None and second["precio_por_unidad"] == "12.5000" and second["moneda"] == "USD"
    assert second["iva_incluido"] is True
    stored = api.session.scalar(select(ProveedorProducto).where(ProveedorProducto.codigo == "PPR-0001"))
    assert stored.creado_por == "admin-1" and stored.precio_referencial == D("14000")
    assert api.get(f"/proveedores/{code}/productos").json() == [first, second]


def test_pg_a_product_can_point_to_a_material_or_to_none(api):
    como("admin")
    code = make_supplier(api)
    response = add(api, code, item("Tela forro", material=TELA))
    assert response.status_code == 201, response.text
    body = response.json()[0]
    assert body["material"] == TELA and body["material_nombre"].startswith("Tela forrería")
    unknown = add(api, code, item("Otra", material="MAT-NO-EXISTE"))
    assert unknown.status_code == 422 and "MAT-NO-EXISTE" in unknown.json()["detail"]
    assert count(api) == 1


def test_pg_a_change_is_a_new_row_of_the_same_product_and_the_list_shows_the_newest(api):
    como("admin")
    code = make_supplier(api)
    add(api, code, item(vigente_desde="2026-10-01"))
    response = add(api, code, item("  flex 1 × 1,40 ", precio_referencial="16000", vigente_desde="2026-11-01"))
    assert response.status_code == 201, response.text
    current = response.json()
    assert len(current) == 1 and current[0]["codigo"] == "PPR-0002" and current[0]["cargas"] == 2
    assert current[0]["precio_referencial"] == "16000.0000" and current[0]["precio_anterior"] == "14000.0000"
    assert current[0]["nombre"] == "flex 1 × 1,40"  # the same product (case and spaces ignored), as last typed
    assert count(api) == 2  # nothing was overwritten
    history = api.get(f"/proveedores/{code}/productos", params={"historial": "true"}).json()
    assert [(row["codigo"], row["precio_referencial"]) for row in history] == [("PPR-0002", "16000.0000"), ("PPR-0001", "14000.0000")]


def test_pg_two_changes_the_same_day_keep_the_later_one_as_current(api):
    como("admin")
    code = make_supplier(api)
    add(api, code, item(vigente_desde=DAY))
    add(api, code, item(precio_referencial="15000", vigente_desde=DAY))
    current = api.get(f"/proveedores/{code}/productos").json()
    assert [row["codigo"] for row in current] == ["PPR-0002"] and current[0]["precio_referencial"] == "15000.0000"


def test_pg_the_list_is_scoped_to_the_supplier_and_ordered_by_name(api):
    como("admin")
    code, other = make_supplier(api), make_supplier(api, "Acropol")
    add(api, code, item("Zipper"), item("Cartón"))
    add(api, other, item("Flex"))
    assert [row["nombre"] for row in api.get(f"/proveedores/{code}/productos").json()] == ["Cartón", "Zipper"]
    assert [row["nombre"] for row in api.get(f"/proveedores/{other}/productos").json()] == ["Flex"]
    assert api.get("/proveedores/PRV-9999/productos").status_code == 404
    assert add(api, "PRV-9999", item()).status_code == 404


@pytest.mark.parametrize("cambio, mensaje", [
    ({"nombre": "   "}, None),
    ({"unidad": "kg"}, None),
    ({"cantidad": "0"}, None),
    ({"cantidad": "-1"}, None),
    ({"precio_referencial": "0"}, None),
    ({"precio_referencial": "-5"}, None),
    ({"moneda": "EUR"}, None),
    ({"vigente_desde": (date.today() + timedelta(days=1)).isoformat()}, "futuro"),
])
def test_pg_invalid_products_are_refused_and_nothing_is_saved(api, cambio, mensaje):
    como("admin")
    code = make_supplier(api)
    response = add(api, code, item("Bueno"), {**item("Malo"), **cambio})
    assert response.status_code == 422, response.text
    if mensaje:
        assert mensaje in response.text
    assert count(api) == 0  # all or nothing


def test_pg_unknown_fields_are_refused(api):
    como("admin")
    code = make_supplier(api)
    assert add(api, code, item(proveedor="PRV-0002")).status_code == 422  # the supplier comes from the URL
    assert count(api) == 0


def test_pg_the_database_refuses_what_the_rules_refuse(api):
    como("admin")
    code = make_supplier(api)
    supplier_id = api.session.scalar(text("select id from costos.proveedor where codigo = :c"), {"c": code})
    for bad in ({"unidad": "kg"}, {"cantidad": D("0")}, {"precio_referencial": D("0")}, {"moneda": "EUR"}):
        values = {"codigo": "PPR-9999", "proveedor_id": supplier_id, "nombre": "X", "unidad": "m2",
                  "precio_referencial": D("1"), "moneda": "ARS", "vigente_desde": date(2026, 11, 5), "creado_por": "t", **bad}
        with pytest.raises(IntegrityError), api.session.begin_nested():
            api.session.add(ProveedorProducto(**values))
            api.session.flush()


def test_pg_only_the_admin_reads_and_writes(api):
    como("admin")
    code = make_supplier(api)
    assert add(api, code, item()).status_code == 201
    for role in ("gerente", "taller"):
        como(role)
        assert api.get(f"/proveedores/{code}/productos").status_code == 403, role
        assert add(api, code, item("Otro")).status_code == 403, role
    como("admin")
    assert count(api) == 1
