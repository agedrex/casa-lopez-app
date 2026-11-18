"""S6 of flujo-modelos-lotes-precio: the leather check while a lot is being created uses the same availability as the
detail of the created lot (stock minus what the other open lots reserve). Skipped without TEST_DATABASE_URL."""

from decimal import Decimal as D

from test_cueros_lote import api, comprar, lote, producto  # noqa: F401  (api is a fixture)

# MOD-0001 and MOD-0031 use 0.25 m2 of leather per unit: 8 units need 2 m2.
CAMPOS_COMUNES = ("material", "color", "necesario", "ya_cortado", "por_cortar", "disponible", "reservado_por_otros",
                  "reservado_por", "libre", "alcanza", "faltante", "sobrante", "mensaje", "productos")


def normalizado(valor):
    """Numbers compare as numbers (the API writes `2.000000` for a stored quantity and more zeros for a typed one)."""
    return D(valor) if isinstance(valor, str) and valor.replace(".", "", 1).isdigit() else valor


def chequear(client, *lineas):
    respuesta = client.post("/cueros/alcanza-lote", json={
        "lineas": [{"producto": p, "cantidad": c} for p, c in lineas]})
    assert respuesta.status_code == 200, respuesta.text
    return respuesta.json()


def grupo_de(client, codigo):
    respuesta = client.get(f"/ordenes/{codigo}/cuero")
    assert respuesta.status_code == 200, respuesta.text
    return respuesta.json()["cueros"][0]


def test_the_check_at_creation_discounts_what_other_open_lots_reserve(api):
    client, _ = api
    comprar(client, "3")
    p = producto(client)
    primero, _ = lote(client, [(p, "8")])
    previo = chequear(client, (p, "8"))["cueros"][0]
    assert D(previo["necesario"]) == 2 and D(previo["disponible"]) == 3
    assert D(previo["reservado_por_otros"]) == 2 and previo["reservado_por"] == [primero]
    assert D(previo["libre"]) == 1 and previo["alcanza"] is False and D(previo["faltante"]) == 1
    assert previo["mensaje"] == (
        f"No alcanza: faltan 1 m² de Estándar. Hay 3 m² en stock y {primero} tiene reservados 2 m².")


def test_the_check_at_creation_and_the_created_lot_agree_field_by_field(api):
    client, _ = api
    comprar(client, "3")
    p = producto(client)
    lote(client, [(p, "8")])
    previo = chequear(client, (p, "8"))["cueros"][0]
    creado, _ = lote(client, [(p, "8")])
    real = grupo_de(client, creado)
    assert {c: normalizado(previo[c]) for c in CAMPOS_COMUNES} == {c: normalizado(real[c]) for c in CAMPOS_COMUNES}


def test_lines_that_share_a_leather_are_added_up_like_in_the_lot(api):
    client, _ = api
    comprar(client, "3")
    a, b = producto(client), producto(client, modelo="MOD-0031")
    # 4 units (1 m2) + 8 units (2 m2) need 3 m2: fits one by one but also together.
    assert chequear(client, (a, "4"), (b, "8"))["cueros"][0]["alcanza"] is True
    # 8 + 8 units need 4 m2: each line alone fits in 3 m2, the lot does not.
    junto = chequear(client, (a, "8"), (b, "8"))["cueros"]
    assert len(junto) == 1 and D(junto[0]["necesario"]) == 4 and junto[0]["alcanza"] is False
    assert D(junto[0]["faltante"]) == 1 and sorted(junto[0]["productos"]) == sorted([a, b])
    creado, _ = lote(client, [(a, "8"), (b, "8")])
    assert D(grupo_de(client, creado)["faltante"]) == D(junto[0]["faltante"])


def test_without_reservations_it_fits_and_a_closed_lot_reserves_nothing(api):
    client, _ = api
    comprar(client, "3")
    p = producto(client)
    libre = chequear(client, (p, "8"))["cueros"][0]
    assert libre["alcanza"] is True and D(libre["reservado_por_otros"]) == 0 and libre["reservado_por"] == []
    assert D(libre["libre"]) == 3 and libre["mensaje"] is None
    primero, _ = lote(client, [(p, "8")])
    for estado in ("EN_CORTE", "CORTADA", "EN_CONFECCION", "LISTA"):
        assert client.post(f"/ordenes/{primero}/estado", json={"estado": estado, "fecha": "2026-10-03"}).status_code in (200, 201)
    assert client.post(f"/ordenes/{primero}/estado", json={
        "estado": "CERRADA", "fecha": "2026-10-04", "fecha_de_entrega": "2026-10-04"}).status_code in (200, 201)
    assert chequear(client, (p, "8"))["cueros"][0]["reservado_por"] == []


def test_invalid_lines_are_refused_and_nothing_is_saved(api):
    client, _ = api
    comprar(client, "3")
    p = producto(client)
    assert client.post("/cueros/alcanza-lote", json={"lineas": []}).status_code == 422
    assert client.post("/cueros/alcanza-lote", json={"lineas": [{"producto": "PRD-9999", "cantidad": "1"}]}).status_code == 404
    assert client.post("/cueros/alcanza-lote", json={"lineas": [{"producto": p, "cantidad": "0"}]}).status_code == 422
    assert client.get("/ordenes").json() == []


def test_only_the_admin_checks_a_lot_in_creation(api):
    client, role = api
    p = producto(client)
    role["value"] = "taller"
    assert client.post("/cueros/alcanza-lote", json={"lineas": [{"producto": p, "cantidad": "1"}]}).status_code == 403
    role["value"] = "gerente"
    assert client.post("/cueros/alcanza-lote", json={"lineas": [{"producto": p, "cantidad": "1"}]}).status_code == 403


def test_the_single_product_check_is_unchanged(api):
    """GET /cueros/alcanza (the Corte screen) keeps answering from the stock alone."""
    client, _ = api
    comprar(client, "3")
    p = producto(client)
    lote(client, [(p, "8")])
    datos = client.get("/cueros/alcanza", params={"producto": p, "cantidad": "8"}).json()
    assert datos["alcanza"] is True and D(datos["disponible"]) == 3 and D(datos["necesario"]) == 2
