"""Derived reservation in the leather summary of a lot (QA S2); no migration. Skipped without TEST_DATABASE_URL."""

from decimal import Decimal as D

from test_cueros_lote import api, comprar, lote, producto  # noqa: F401  (api is a fixture)

# MOD-0001 uses 0.25 m2 of leather per unit: 8 units need 2 m2.


def grupo_de(client, codigo):
    respuesta = client.get(f"/ordenes/{codigo}/cuero")
    assert respuesta.status_code == 200, respuesta.text
    return respuesta.json()["cueros"][0]


def test_two_lots_do_not_both_fit_in_the_same_stock(api):
    client, role = api
    comprar(client, "3")
    p = producto(client)
    primero, _ = lote(client, [(p, "8")])
    segundo, _ = lote(client, [(p, "8")])
    role["value"] = "taller"
    g = grupo_de(client, segundo)
    assert D(g["necesario"]) == 2 and D(g["disponible"]) == 3
    assert D(g["reservado_por_otros"]) == 2 and g["reservado_por"] == [primero]
    assert D(g["libre"]) == 1 and g["alcanza"] is False
    assert D(g["faltante"]) == 1 and D(g["sobrante"]) == 0
    assert g["mensaje"] == (
        f"No alcanza: faltan 1 m² de Estándar. Hay 3 m² en stock y {primero} tiene reservados 2 m².")
    # Reading it never blocks anything: both lots exist and keep their state.
    assert grupo_de(client, primero)["reservado_por"] == [segundo]


def test_a_closed_lot_does_not_reserve(api):
    client, _ = api
    comprar(client, "3")
    p = producto(client)
    primero, _ = lote(client, [(p, "8")])
    segundo, _ = lote(client, [(p, "8")])
    for estado in ("EN_CORTE", "CORTADA", "EN_CONFECCION", "LISTA"):
        assert client.post(f"/ordenes/{primero}/estado", json={"estado": estado, "fecha": "2026-10-03"}).status_code in (200, 201)
    assert client.post(f"/ordenes/{primero}/estado", json={
        "estado": "CERRADA", "fecha": "2026-10-04", "fecha_de_entrega": "2026-10-04"}).status_code in (200, 201)
    g = grupo_de(client, segundo)
    assert D(g["reservado_por_otros"]) == 0 and g["reservado_por"] == [] and g["alcanza"] is True
    assert g["mensaje"] is None


def test_leather_already_cut_by_another_lot_is_not_reserved_twice(api):
    client, _ = api
    pieza = comprar(client, "3")
    p = producto(client)
    primero, items = lote(client, [(p, "8")])
    segundo, _ = lote(client, [(p, "8")])
    corte = client.post(f"/cueros/{pieza}/cortes", json={"m2": "1.5", "orden_item": items[0], "fecha": "2026-10-02"})
    assert corte.status_code == 201, corte.text
    # Stock is now 1.5 (the cut already left it); the first lot still has 0.5 m2 to cut: reserved 0.5, not 2.
    g = grupo_de(client, segundo)
    assert D(g["disponible"]) == D("1.5") and D(g["reservado_por_otros"]) == D("0.5")
    assert D(g["libre"]) == 1 and g["alcanza"] is False and D(g["faltante"]) == 1
    # Fully cut: nothing left to reserve.
    assert client.post(f"/cueros/{pieza}/cortes", json={"m2": "0.5", "orden_item": items[0]}).status_code == 201
    g = grupo_de(client, segundo)
    assert D(g["reservado_por_otros"]) == 0 and g["reservado_por"] == []


def test_other_leather_and_removed_lines_do_not_reserve(api):
    client, _ = api
    comprar(client, "3")
    p, carpincho = producto(client), producto(client, cuero="MAT-CU02")
    otro, items = lote(client, [(p, "8"), (carpincho, "8")])
    mio, _ = lote(client, [(p, "8")])
    assert D(grupo_de(client, mio)["reservado_por_otros"]) == 2
    assert client.delete(f"/ordenes/{otro}/items/{items[0]}").status_code in (200, 204)
    g = grupo_de(client, mio)
    assert D(g["reservado_por_otros"]) == 0 and g["alcanza"] is True


def test_a_single_lot_summary_is_unchanged(api):
    client, _ = api
    comprar(client, "3")
    codigo, _ = lote(client, [(producto(client), "4")])
    g = grupo_de(client, codigo)
    assert g["alcanza"] is True and D(g["faltante"]) == 0 and D(g["sobrante"]) == 2 and D(g["disponible"]) == 3
    assert D(g["reservado_por_otros"]) == 0 and g["reservado_por"] == [] and D(g["libre"]) == 3 and g["mensaje"] is None
