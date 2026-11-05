"""Suppliers and their documents against the migrated local PostgreSQL (skipped without TEST_DATABASE_URL).

Each test runs inside an outer transaction that is rolled back. The OCR is a fake behind `get_ocr_llm`: what is real is
the database (constraints, bytea, ILIKE search, the unique indexes) and the endpoints.
"""

import hashlib
from datetime import date
from decimal import Decimal as D

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import insert, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend import api as api_module
from backend import proveedores
from backend.auth import Usuario, get_verifier
from backend.database import get_session
from backend.main import app
from backend.models import DocumentoProveedor, Proveedor
from backend.ocr_llm import OcrError, OcrResult, OcrSuggestion

PNG = b"\x89PNG\r\n\x1a\n" + b"pixels-1"
PNG_2 = b"\x89PNG\r\n\x1a\n" + b"pixels-2"
JPEG = b"\xff\xd8\xff\xe0\x00\x10JFIF" + b"\x00" * 10
PDF = b"%PDF-1.7\n" + b"body"
SECRET = "sk-ant-api03-SECRET-THAT-MUST-NOT-LEAK"


class FakeOcr:
    def __init__(self):
        self.result = OcrResult(
            text="FACTURA A Rouez\nN° 0001-00001234\nTotal $ 1.234,50",
            suggestion=OcrSuggestion(numero="0001-00001234", fecha=date(2026, 9, 3), total=D("1234.50"), moneda="ARS"))
        self.error: Exception | None = None
        self.calls = 0

    def read(self, content, mime):
        self.calls += 1
        if self.error:
            raise self.error
        return self.result


@pytest.fixture
def env(local_postgres, monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    connection = local_postgres.connect()
    outer = connection.begin()
    session = Session(bind=connection, join_transaction_mode="create_savepoint")
    ocr = FakeOcr()
    holder = {"ocr": ocr}
    app.dependency_overrides[get_session] = lambda: session
    app.dependency_overrides[get_verifier] = lambda: (lambda request: Usuario(id="usuario-de-prueba", role="admin"))
    app.dependency_overrides[api_module.get_ocr_llm] = lambda: holder["ocr"]
    try:
        with TestClient(app) as client:
            yield client, session, holder
    finally:
        app.dependency_overrides.clear()
        session.close()
        outer.rollback()
        connection.close()


def supplier(client, name="Rouez", **extra):
    response = client.post("/proveedores", json={"nombre": name, **extra})
    assert response.status_code == 201, response.text
    return response.json()


def upload(client, code="PRV-0001", content=PNG, filename="factura.png", **fields):
    return client.post(f"/proveedores/{code}/documentos", data={"tipo": "FACTURA", **fields},
                       files={"archivo": (filename, content, "application/octet-stream")})


def count(session, table):
    return session.execute(text(f"select count(*) from costos.{table}")).scalar_one()


# --- suppliers ----------------------------------------------------------------------------------------------------

def test_codes_are_assigned_in_order_and_an_explicit_code_is_respected(env):
    client, _, _ = env
    assert supplier(client, "Rouez")["codigo"] == "PRV-0001"
    assert supplier(client, "Acropol")["codigo"] == "PRV-0002"
    assert supplier(client, "Otro", codigo="PRV-0100")["codigo"] == "PRV-0100"
    assert supplier(client, "Siguiente")["codigo"] == "PRV-0101"


def test_a_new_supplier_is_active_with_no_documents_and_trimmed_text(env):
    client, _, _ = env
    data = supplier(client, "  Rouez  ", cuit=" 30-12345678-9 ", contacto="", nota=" hola ")
    assert data["nombre"] == "Rouez" and data["cuit"] == "30-12345678-9" and data["contacto"] is None
    assert data["nota"] == "hola" and data["activo"] is True and data["documentos"] == 0


def test_name_is_unique_ignoring_case_cuit_and_code_are_unique_too(env):
    client, _, _ = env
    supplier(client, "Rouez", cuit="30-1")
    for body in ({"nombre": "ROUEZ"}, {"nombre": "rouez "}, {"nombre": "Otro", "cuit": "30-1"},
                 {"nombre": "Otro", "codigo": "PRV-0001"}):
        response = client.post("/proveedores", json=body)
        assert response.status_code == 409, body
    assert len(client.get("/proveedores").json()) == 1


def test_list_search_and_active_filter(env):
    client, _, _ = env
    supplier(client, "Rouez", cuit="30-111")
    supplier(client, "Acropol", contacto="María")
    supplier(client, "Cueros del Sur")
    client.post("/proveedores/PRV-0003/activo", json={"activo": False})
    assert [p["nombre"] for p in client.get("/proveedores").json()] == ["Rouez", "Acropol", "Cueros del Sur"]
    assert [p["nombre"] for p in client.get("/proveedores", params={"q": "ROU"}).json()] == ["Rouez"]
    assert [p["nombre"] for p in client.get("/proveedores", params={"q": "30-111"}).json()] == ["Rouez"]
    assert [p["nombre"] for p in client.get("/proveedores", params={"q": "mar"}).json()] == ["Acropol"]
    assert client.get("/proveedores", params={"q": "%"}).json() == []  # a wildcard is text, not a pattern
    assert [p["codigo"] for p in client.get("/proveedores", params={"activo": "false"}).json()] == ["PRV-0003"]
    assert [p["codigo"] for p in client.get("/proveedores", params={"activo": "true"}).json()] == ["PRV-0001", "PRV-0002"]


def test_edit_changes_the_data_but_never_the_code_and_archiving_keeps_the_history(env):
    client, _, _ = env
    supplier(client, "Rouez")
    upload(client)
    edited = client.post("/proveedores/PRV-0001", json={"nombre": "Rouez SA", "telefono": "11 5555", "cuit": "30-9"})
    assert edited.status_code == 200 and edited.json()["codigo"] == "PRV-0001"
    assert edited.json()["nombre"] == "Rouez SA" and edited.json()["telefono"] == "11 5555"
    archived = client.post("/proveedores/PRV-0001/activo", json={"activo": False}).json()
    assert archived["activo"] is False and archived["documentos"] == 1
    assert len(client.get("/proveedores/PRV-0001/documentos").json()) == 1  # nothing is deleted
    assert client.post("/proveedores/PRV-0001/activo", json={"activo": True}).json()["activo"] is True


def test_editing_into_another_suppliers_name_or_cuit_is_409(env):
    client, _, _ = env
    supplier(client, "Rouez", cuit="30-1")
    supplier(client, "Acropol", cuit="30-2")
    assert client.post("/proveedores/PRV-0002", json={"nombre": "rouez"}).status_code == 409
    assert client.post("/proveedores/PRV-0002", json={"nombre": "Acropol", "cuit": "30-1"}).status_code == 409
    assert client.post("/proveedores/PRV-0002", json={"nombre": "Acropol", "cuit": "30-2"}).status_code == 200


def test_unknown_supplier_is_404_everywhere(env):
    client, _, _ = env
    assert client.get("/proveedores/PRV-9999").status_code == 404
    assert client.post("/proveedores/PRV-9999", json={"nombre": "X"}).status_code == 404
    assert client.post("/proveedores/PRV-9999/activo", json={"activo": True}).status_code == 404
    assert client.get("/proveedores/PRV-9999/documentos").status_code == 404
    assert upload(client, "PRV-9999").status_code == 404


# --- upload and storage -------------------------------------------------------------------------------------------

def test_an_upload_stores_the_file_in_the_database_and_runs_the_ocr(env):
    client, session, holder = env
    supplier(client)
    response = upload(client, filename="../../Factura Rouez.png", numero=" 0001-1 ", fecha_documento="2026-09-03",
                      total="1234.5", moneda="ARS")
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["proveedor"] == "PRV-0001" and body["tipo"] == "FACTURA" and body["mime"] == "image/png"
    assert body["nombre_archivo"] == "Factura Rouez.png"  # sanitized: a label, never a path
    assert body["tamano_bytes"] == len(PNG) and body["sha256"] == hashlib.sha256(PNG).hexdigest()
    assert body["numero"] == "0001-1" and body["fecha_documento"] == "2026-09-03"
    assert body["total"] == "1234.5000" and body["moneda"] == "ARS" and body["subido_por"] == "usuario-de-prueba"
    assert body["ocr_estado"] == "LISTO" and "Rouez" in body["ocr_texto"] and body["ocr_error"] is None
    assert body["ocr_sugerencia"] == {"numero": "0001-00001234", "fecha": "2026-09-03", "total": "1234.50", "moneda": "ARS"}
    assert "contenido" not in body and holder["ocr"].calls == 1
    stored = session.execute(text("select contenido, mime from costos.documento_proveedor")).one()
    assert bytes(stored.contenido) == PNG and stored.mime == "image/png"


def test_the_type_comes_from_the_bytes_not_from_the_declared_mime_or_extension(env):
    client, session, _ = env
    supplier(client)
    response = upload(client, content=JPEG, filename="foto.pdf")  # a JPEG that claims to be a PDF
    assert response.status_code == 201 and response.json()["mime"] == "image/jpeg"
    assert upload(client, content=b"MZ\x90\x00 an executable", filename="x.pdf").status_code == 422
    assert upload(client, content=b"<html><script>1</script></html>", filename="x.png").status_code == 422
    assert upload(client, content=b"", filename="x.png").status_code == 422
    assert count(session, "documento_proveedor") == 1  # the refused files left nothing behind


def test_a_file_over_10_mb_is_413_and_stores_nothing(env):
    client, session, holder = env
    supplier(client)
    response = upload(client, content=PNG + b"\x00" * proveedores.MAX_FILE_BYTES)
    assert response.status_code == 413 and "10 MB" in response.json()["detail"]
    assert count(session, "documento_proveedor") == 0 and holder["ocr"].calls == 0


def test_the_same_file_twice_for_a_supplier_is_409_but_another_supplier_may_have_it(env):
    client, session, _ = env
    supplier(client, "Rouez")
    supplier(client, "Acropol")
    assert upload(client, "PRV-0001").status_code == 201
    again = upload(client, "PRV-0001", filename="otro-nombre.png")
    assert again.status_code == 409 and "ya está cargado" in again.json()["detail"]
    assert upload(client, "PRV-0002").status_code == 201
    assert upload(client, "PRV-0001", content=PNG_2).status_code == 201
    assert count(session, "documento_proveedor") == 3


def test_a_total_without_currency_is_422_and_stores_nothing(env):
    client, session, _ = env
    supplier(client)
    response = upload(client, total="10")
    assert response.status_code == 422 and "moneda" in response.json()["detail"]
    assert count(session, "documento_proveedor") == 0


# --- OCR states ---------------------------------------------------------------------------------------------------

def test_without_a_key_the_upload_works_and_the_state_is_no_configurado_then_a_retry_reads_it(env):
    client, _, holder = env
    supplier(client)
    holder["ocr"] = None
    body = upload(client).json()
    assert body["ocr_estado"] == "NO_CONFIGURADO" and body["ocr_texto"] is None and body["ocr_sugerencia"] is None
    still = client.post(f"/documentos-proveedor/{body['id']}/ocr").json()
    assert still["ocr_estado"] == "NO_CONFIGURADO"
    holder["ocr"] = FakeOcr()
    retried = client.post(f"/documentos-proveedor/{body['id']}/ocr").json()
    assert retried["ocr_estado"] == "LISTO" and "Rouez" in retried["ocr_texto"]
    assert client.get(f"/documentos-proveedor/{body['id']}/archivo").content == PNG


def test_an_ocr_failure_keeps_the_file_with_a_safe_message_and_can_be_retried(env):
    client, _, holder = env
    supplier(client)
    holder["ocr"].error = OcrError("El OCR tardó demasiado en responder. Probá de nuevo más tarde.", "timeout")
    body = upload(client).json()
    assert body["ocr_estado"] == "ERROR" and body["ocr_error"].startswith("El OCR tardó")
    assert client.get(f"/documentos-proveedor/{body['id']}/archivo").content == PNG
    holder["ocr"].error = RuntimeError(f"boom {SECRET}")
    again = client.post(f"/documentos-proveedor/{body['id']}/ocr")
    assert again.status_code == 200 and again.json()["ocr_estado"] == "ERROR" and SECRET not in again.text
    holder["ocr"].error = None
    ok = client.post(f"/documentos-proveedor/{body['id']}/ocr").json()
    assert ok["ocr_estado"] == "LISTO" and ok["ocr_error"] is None


def test_the_ocr_never_overwrites_what_a_person_typed(env):
    client, _, _ = env
    supplier(client)
    body = upload(client, numero="MIO-1", total="5", moneda="USD").json()
    assert body["numero"] == "MIO-1" and body["total"] == "5.0000" and body["moneda"] == "USD"
    assert body["ocr_sugerencia"]["numero"] == "0001-00001234"  # only a suggestion
    retried = client.post(f"/documentos-proveedor/{body['id']}/ocr").json()
    assert (retried["numero"], retried["total"], retried["moneda"]) == ("MIO-1", "5.0000", "USD")


def test_ocr_text_with_html_or_sql_is_stored_and_returned_as_plain_text(env):
    client, _, holder = env
    supplier(client)
    attack = "<script>alert(1)</script> '); DROP TABLE costos.proveedor;-- %_"
    holder["ocr"].result = OcrResult(text=attack, suggestion=OcrSuggestion())
    body = upload(client).json()
    assert body["ocr_texto"] == attack
    assert client.get("/proveedores/PRV-0001").status_code == 200  # the table is still there


# --- list, search, download ---------------------------------------------------------------------------------------

def test_the_list_never_contains_the_bytes_and_orders_newest_first(env):
    client, _, _ = env
    supplier(client)
    first = upload(client, filename="a.png").json()
    second = upload(client, content=PNG_2, filename="b.png").json()
    items = client.get("/proveedores/PRV-0001/documentos").json()
    assert [item["id"] for item in items] == [second["id"], first["id"]]
    assert all("contenido" not in item for item in items)
    assert "pixels" not in client.get("/proveedores/PRV-0001/documentos").text


def test_search_q_looks_in_file_name_number_and_ocr_text_ignoring_case(env):
    client, _, holder = env
    supplier(client)
    holder["ocr"].result = OcrResult(text="Cuero ESTÁNDAR anilina", suggestion=OcrSuggestion())
    by_text = upload(client, filename="uno.png").json()
    holder["ocr"].result = OcrResult(text="nada", suggestion=OcrSuggestion())
    by_name = upload(client, content=PNG_2, filename="Remito-Setiembre.png").json()
    by_number = upload(client, content=JPEG, filename="tres.jpg", numero="FC-A-0007").json()
    ids = lambda q: sorted(i["id"] for i in client.get("/proveedores/PRV-0001/documentos", params={"q": q}).json())
    assert ids("anilina") == [by_text["id"]] and ids("ANILINA") == [by_text["id"]]
    assert ids("setiembre") == [by_name["id"]]
    assert ids("fc-a-0007") == [by_number["id"]] and ids("0007") == [by_number["id"]]
    assert ids("no-existe") == []
    assert ids("") == sorted([by_text["id"], by_name["id"], by_number["id"]])
    assert ids("%") == [] and ids("_") == []  # wildcards are plain text


def test_search_is_scoped_to_the_supplier(env):
    client, _, _ = env
    supplier(client, "Rouez")
    supplier(client, "Acropol")
    upload(client, "PRV-0001", filename="rouez.png")
    upload(client, "PRV-0002", filename="acropol.png")
    names = [i["nombre_archivo"] for i in client.get("/proveedores/PRV-0001/documentos", params={"q": "png"}).json()]
    assert names == ["rouez.png"]


@pytest.mark.parametrize("content, filename, disposition", [
    (PNG, "f.png", "inline"), (JPEG, "f.jpg", "inline"), (PDF, "f.pdf", "attachment"),
])
def test_download_returns_the_exact_bytes_with_safe_headers(env, content, filename, disposition):
    client, _, _ = env
    supplier(client)
    doc = upload(client, content=content, filename=filename).json()
    response = client.get(f"/documentos-proveedor/{doc['id']}/archivo")
    assert response.status_code == 200 and response.content == content
    assert response.headers["content-type"] == doc["mime"]
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["content-disposition"].startswith(disposition)


def test_unknown_document_is_404_on_every_document_route(env):
    client, _, _ = env
    assert client.get("/documentos-proveedor/99999/archivo").status_code == 404
    assert client.post("/documentos-proveedor/99999/ocr").status_code == 404
    assert client.post("/documentos-proveedor/99999/datos", json={"tipo": "FACTURA"}).status_code == 404


# --- confirm data -------------------------------------------------------------------------------------------------

def test_confirm_sets_only_the_person_confirmed_fields(env):
    client, _, _ = env
    supplier(client)
    doc = upload(client).json()
    response = client.post(f"/documentos-proveedor/{doc['id']}/datos", json={
        "tipo": "OTRO", "numero": " 0001-00001234 ", "fecha_documento": "2026-09-03", "total": "1234.50", "moneda": "ARS"})
    assert response.status_code == 200, response.text
    body = response.json()
    assert (body["tipo"], body["numero"], body["fecha_documento"], body["total"], body["moneda"]) == (
        "OTRO", "0001-00001234", "2026-09-03", "1234.5000", "ARS")
    for untouched in ("nombre_archivo", "mime", "tamano_bytes", "sha256", "ocr_estado", "ocr_texto", "ocr_sugerencia",
                      "subido_por", "created_at"):
        assert body[untouched] == doc[untouched], untouched


def test_confirm_can_clear_a_value_and_needs_a_currency_for_a_total(env):
    client, _, _ = env
    supplier(client)
    doc = upload(client, numero="X", total="5", moneda="USD").json()
    cleared = client.post(f"/documentos-proveedor/{doc['id']}/datos", json={"tipo": "FACTURA"}).json()
    assert cleared["numero"] is None and cleared["total"] is None and cleared["moneda"] is None
    bad = client.post(f"/documentos-proveedor/{doc['id']}/datos", json={"tipo": "FACTURA", "total": "5"})
    assert bad.status_code == 422 and "moneda" in bad.json()["detail"]
    assert client.get("/proveedores/PRV-0001/documentos").json()[0]["total"] is None


def test_confirm_refuses_to_touch_anything_else(env):
    client, _, _ = env
    supplier(client)
    doc = upload(client).json()
    for field in ("ocr_texto", "contenido", "sha256", "ocr_estado", "nombre_archivo", "mime"):
        response = client.post(f"/documentos-proveedor/{doc['id']}/datos", json={"tipo": "FACTURA", field: "x"})
        assert response.status_code == 422, field


# --- database rules -----------------------------------------------------------------------------------------------

def insert_supplier(session, **values):
    values = {"codigo": "PRV-0900", "nombre": "Directo", **values}
    return session.execute(insert(Proveedor).values(**values).returning(Proveedor.id)).scalar_one()


def insert_document(session, supplier_id, **values):
    values = {"proveedor_id": supplier_id, "tipo": "FACTURA", "nombre_archivo": "a.png", "mime": "image/png",
              "tamano_bytes": 3, "sha256": "a" * 64, "contenido": b"abc", "ocr_estado": "PENDIENTE",
              "subido_por": "u", **values}
    return session.execute(insert(DocumentoProveedor).values(**values).returning(DocumentoProveedor.id)).scalar_one()


@pytest.mark.parametrize("changes", [
    {"tipo": "FOTO"}, {"mime": "text/html"}, {"mime": "image/svg+xml"}, {"moneda": "EUR", "total": D("1")},
    {"ocr_estado": "HECHO"}, {"total": D("-1"), "moneda": "ARS"}, {"tamano_bytes": 0},
])
def test_the_database_itself_rejects_values_outside_the_closed_lists(env, changes):
    _, session, _ = env
    supplier_id = insert_supplier(session)
    with pytest.raises(IntegrityError):
        with session.begin_nested():
            insert_document(session, supplier_id, **changes)


def test_the_database_rejects_a_duplicate_hash_per_supplier_and_a_name_that_differs_only_in_case(env):
    _, session, _ = env
    supplier_id = insert_supplier(session)
    insert_document(session, supplier_id)
    with pytest.raises(IntegrityError):
        with session.begin_nested():
            insert_document(session, supplier_id)
    other = insert_supplier(session, codigo="PRV-0901", nombre="Otro")
    insert_document(session, other)  # the same bytes under another supplier is fine
    with pytest.raises(IntegrityError):
        with session.begin_nested():
            insert_supplier(session, codigo="PRV-0902", nombre="DIRECTO")


def test_the_content_column_is_deferred_so_an_orm_read_does_not_load_it(env):
    _, session, _ = env
    insert_document(session, insert_supplier(session))
    session.expire_all()
    document = session.query(DocumentoProveedor).one()
    assert "contenido" not in document.__dict__
