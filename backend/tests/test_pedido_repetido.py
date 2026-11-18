"""A second order of the same material on the same date is refused (rule kept) with a message that says what already exists.

Runs against disposable PostgreSQL (skipped without TEST_DATABASE_URL), inside a transaction that is rolled back.
"""

from sqlalchemy import select

from backend.models import Material, PrecioMaterial

from test_pedidos_proveedor import (  # noqa: F401  (`api` is a fixture)
    CUERO, DAY, FLEX, TELA, api, como, counts, line, make_supplier, order, pieces, pieles,
)

SKINS = {"fecha_de_recepcion": DAY, "lineas": [], "pieles": [pieles(tamanos=["2", "3"])]}


def detail(response):
    assert response.status_code == 409, response.text
    return response.json()["detail"]


def test_pg_the_same_leather_and_date_again_is_409_and_names_the_order_the_price_and_the_pieces(api):
    como("admin")
    code = make_supplier(api)
    first = api.post(f"/proveedores/{code}/pedidos", json=SKINS)
    assert first.status_code == 201, first.text
    before = counts(api)
    stored = {p.codigo for p in pieces(api)}
    price = api.session.scalar(select(PrecioMaterial.codigo).where(PrecioMaterial.nota_fuente == "Pedido PED-0001"))
    name = api.session.scalar(select(Material.nombre).where(Material.codigo == CUERO))

    text = detail(api.post(f"/proveedores/{code}/pedidos", json=SKINS))

    assert text.startswith(f"Línea 1 ({CUERO}): Ya hay un precio de {name} para el 05/11/2026")
    assert "PED-0001" in text and price in text
    assert all(piece in text for piece in stored)
    assert "usá otra fecha" in text
    assert counts(api) == before and {p.codigo for p in pieces(api)} == stored  # rule unchanged: nothing is saved


def test_pg_the_message_has_no_internal_field_names_or_dates_in_iso_format(api):
    como("admin")
    code = make_supplier(api)
    api.post(f"/proveedores/{code}/pedidos", json=order())
    text = detail(api.post(f"/proveedores/{code}/pedidos", json=order()))
    assert "2026-11-05" not in text and "05/11/2026" in text
    assert "_" not in text.replace(TELA, "")  # only the material code, which is a business key


def test_pg_a_material_typed_twice_in_one_order_names_that_same_order(api):
    como("admin")
    code = make_supplier(api)
    text = detail(api.post(f"/proveedores/{code}/pedidos", json=order([line(), line()])))
    assert text.startswith(f"Línea 2 ({TELA}): Ya hay un precio de ") and "PED-0001" in text


def test_pg_a_price_loaded_by_hand_is_named_by_its_code_without_an_order(api):
    como("admin")
    code = make_supplier(api)
    created = api.post("/precios", json={"material": FLEX, "precio": "5", "moneda": "ARS", "unidad_del_precio": "m2",
                                         "vigente_desde": DAY})
    assert created.status_code == 201
    text = detail(api.post(f"/proveedores/{code}/pedidos", json=order([line(FLEX)])))
    assert created.json()["codigo"] in text and "PED-" not in text


def test_pg_another_date_is_still_accepted(api):
    como("admin")
    code = make_supplier(api)
    assert api.post(f"/proveedores/{code}/pedidos", json=SKINS).status_code == 201
    other = {**SKINS, "fecha_de_recepcion": "2026-11-06"}
    assert api.post(f"/proveedores/{code}/pedidos", json=other).status_code == 201
