"""Supplier endpoints without a database and without a model: the HTTP contract (roles, multipart, limits, headers,
error mapping, money as strings). The services are replaced; their rules are tested in test_proveedores.py and, against
PostgreSQL, in test_proveedores_integration.py. The OCR client is a fake injected through `get_ocr_llm`."""

from datetime import date, datetime, timezone
from decimal import Decimal as D
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from backend import api as api_module
from backend import proveedores, servicios
from backend.auth import Usuario, get_verifier
from backend.database import get_session
from backend.main import app

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 20
PDF = b"%PDF-1.7\n" + b"\x00" * 20
SECRET = "sk-ant-api03-SECRET-THAT-MUST-NOT-LEAK"
NOW = datetime(2026, 11, 5, 10, 0, tzinfo=timezone.utc)

SUPPLIER = {"codigo": "PRV-0001", "nombre": "Rouez", "cuit": None, "contacto": None, "telefono": None,
            "direccion": None, "nota": None, "activo": True, "documentos": 0}


def document(**changes):
    base = {"id": 7, "proveedor": "PRV-0001", "tipo": "FACTURA", "nombre_archivo": "f.png", "mime": "image/png",
            "tamano_bytes": len(PNG), "sha256": "a" * 64, "numero": None, "fecha_documento": None, "total": None,
            "moneda": None, "ocr_estado": "LISTO", "ocr_texto": "Total $ 10", "ocr_sugerencia": None, "ocr_error": None,
            "subido_por": "u1", "created_at": NOW}
    return {**base, **changes}


class FakeOcr:
    def read(self, content, mime):  # never reached: the services are replaced
        raise AssertionError("the OCR must not run in these tests")


@pytest.fixture(autouse=True)
def environment(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("AI_GATEWAY_API_KEY", raising=False)
    yield
    app.dependency_overrides.clear()


def http(role="admin", ocr="default"):
    session = MagicMock()
    app.dependency_overrides[get_session] = lambda: session
    app.dependency_overrides[get_verifier] = lambda: (lambda request: Usuario(id="u1", role=role))
    if ocr != "default":
        app.dependency_overrides[api_module.get_ocr_llm] = lambda: ocr
    return TestClient(app)


def spy(monkeypatch, name, result):
    seen = {}

    def fake(session, *args, **kwargs):
        seen.update(args=args, kwargs=kwargs)
        if isinstance(result, Exception):
            raise result
        return result
    monkeypatch.setattr(proveedores, name, fake)
    return seen


def forbid(monkeypatch, name):
    monkeypatch.setattr(proveedores, name, lambda *a, **k: pytest.fail(f"{name} must not be called"))


# --- roles: admin only ------------------------------------------------------------------------------------------

ROUTES = [
    ("GET", "/proveedores"), ("POST", "/proveedores"), ("GET", "/proveedores/PRV-0001"),
    ("POST", "/proveedores/PRV-0001"), ("POST", "/proveedores/PRV-0001/activo"),
    ("GET", "/proveedores/PRV-0001/documentos"), ("POST", "/proveedores/PRV-0001/documentos"),
    ("GET", "/documentos-proveedor/7/archivo"), ("POST", "/documentos-proveedor/7/ocr"),
    ("POST", "/documentos-proveedor/7/datos"),
]


@pytest.mark.parametrize("method, path", ROUTES)
@pytest.mark.parametrize("role", ["gerente", "taller", "otro", None, "consulta", "corte"])
def test_everyone_but_admin_is_refused_before_any_service_runs(monkeypatch, method, path, role):
    for name in dir(proveedores):
        member = getattr(proveedores, name)
        if callable(member) and getattr(member, "__module__", None) == proveedores.__name__ and not name.startswith("_"):
            forbid(monkeypatch, name)
    client = http(role, ocr=FakeOcr())
    response = client.request(method, path, json={} if method == "POST" else None)
    assert response.status_code == 403 and response.json() == {"detail": "No tenés permiso para esta acción."}


@pytest.mark.parametrize("method, path", ROUTES)
def test_without_a_session_every_route_is_401(method, path):
    app.dependency_overrides[get_verifier] = lambda: (lambda request: None)
    response = TestClient(app).request(method, path, json={} if method == "POST" else None)
    assert response.status_code == 401


# --- suppliers --------------------------------------------------------------------------------------------------

def test_list_passes_q_and_activo_to_the_service(monkeypatch):
    seen = spy(monkeypatch, "list_suppliers", [SUPPLIER])
    response = http().get("/proveedores", params={"q": "rou", "activo": "true"})
    assert response.status_code == 200 and response.json()[0]["codigo"] == "PRV-0001"
    assert seen["kwargs"] == {"q": "rou", "activo": True}
    http().get("/proveedores")
    assert seen["kwargs"] == {"q": None, "activo": None}


def test_create_returns_201_and_forwards_the_fields(monkeypatch):
    seen = spy(monkeypatch, "create_supplier", SUPPLIER)
    body = {"nombre": "Rouez", "cuit": "30-1-2", "telefono": "11", "direccion": "x", "contacto": "y", "nota": "z"}
    response = http().post("/proveedores", json=body)
    assert response.status_code == 201
    assert seen["kwargs"] == {"codigo": None, **body}


@pytest.mark.parametrize("body", [
    {}, {"nombre": ""}, {"nombre": "   "}, {"nombre": "X", "codigo": "PRV-12"}, {"nombre": "X", "codigo": "TAL-0001"},
    {"nombre": "X", "activo": False}, {"nombre": "X", "documentos": 3}, {"nombre": "X", "id": 4},
])
def test_create_rejects_bad_or_unknown_fields_before_the_service(monkeypatch, body):
    forbid(monkeypatch, "create_supplier")
    assert http().post("/proveedores", json=body).status_code == 422


def test_create_accepts_an_explicit_code_with_the_prv_pattern(monkeypatch):
    seen = spy(monkeypatch, "create_supplier", SUPPLIER)
    assert http().post("/proveedores", json={"nombre": "X", "codigo": "PRV-0123"}).status_code == 201
    assert seen["kwargs"]["codigo"] == "PRV-0123"


def test_detail_edit_and_active_map_to_their_services(monkeypatch):
    seen = spy(monkeypatch, "get_supplier", SUPPLIER)
    assert http().get("/proveedores/PRV-0001").json()["nombre"] == "Rouez" and seen["args"] == ("PRV-0001",)
    seen = spy(monkeypatch, "update_supplier", {**SUPPLIER, "nombre": "Rouez SA"})
    response = http().post("/proveedores/PRV-0001", json={"nombre": "Rouez SA"})
    assert response.status_code == 200 and seen["args"] == ("PRV-0001",) and seen["kwargs"]["nombre"] == "Rouez SA"
    seen = spy(monkeypatch, "set_supplier_active", {**SUPPLIER, "activo": False})
    response = http().post("/proveedores/PRV-0001/activo", json={"activo": False})
    assert response.json()["activo"] is False and seen["args"] == ("PRV-0001", False)
    assert http().post("/proveedores/PRV-0001/activo", json={}).status_code == 422


@pytest.mark.parametrize("name, method, path, body", [
    ("get_supplier", "GET", "/proveedores/PRV-9999", None),
    ("update_supplier", "POST", "/proveedores/PRV-9999", {"nombre": "X"}),
    ("set_supplier_active", "POST", "/proveedores/PRV-9999/activo", {"activo": True}),
    ("list_documents", "GET", "/proveedores/PRV-9999/documentos", None),
    ("get_file", "GET", "/documentos-proveedor/99/archivo", None),
    ("retry_ocr", "POST", "/documentos-proveedor/99/ocr", {}),
    ("confirm_document_data", "POST", "/documentos-proveedor/99/datos", {"tipo": "FACTURA"}),
])
def test_missing_resources_are_404_with_the_service_message(monkeypatch, name, method, path, body):
    spy(monkeypatch, name, servicios.NoEncontrado("No existe el recurso."))
    response = http(ocr=FakeOcr()).request(method, path, json=body)
    assert response.status_code == 404 and response.json() == {"detail": "No existe el recurso."}


def test_a_duplicate_supplier_is_409(monkeypatch):
    spy(monkeypatch, "create_supplier", servicios.Conflicto("Ya hay un proveedor con el nombre Rouez."))
    response = http().post("/proveedores", json={"nombre": "Rouez"})
    assert response.status_code == 409 and "Rouez" in response.json()["detail"]


# --- documents: upload --------------------------------------------------------------------------------------------

def upload(client, content=PNG, filename="factura.png", mime="image/png", **fields):
    data = {"tipo": "FACTURA", **fields}
    return client.post("/proveedores/PRV-0001/documentos", data=data, files={"archivo": (filename, content, mime)})


def test_upload_forwards_bytes_filename_typed_data_the_user_and_the_ocr_client(monkeypatch):
    seen = spy(monkeypatch, "add_document", document(numero="0001-5", total=D("1234.5"), moneda="ARS"))
    ocr = FakeOcr()
    response = upload(http(ocr=ocr), numero="0001-5", fecha_documento="2026-09-03", total="1234.5", moneda="ARS")
    assert response.status_code == 201, response.text
    kwargs = seen["kwargs"]
    assert seen["args"] == ("PRV-0001",)
    assert kwargs["contenido"] == PNG and kwargs["nombre_archivo"] == "factura.png" and kwargs["tipo"] == "FACTURA"
    assert kwargs["numero"] == "0001-5" and kwargs["fecha_documento"] == date(2026, 9, 3)
    assert kwargs["total"] == D("1234.5") and isinstance(kwargs["total"], D) and kwargs["moneda"] == "ARS"
    assert kwargs["subido_por"] == "u1" and kwargs["ocr"] is ocr


def test_upload_without_the_optional_fields_sends_none(monkeypatch):
    seen = spy(monkeypatch, "add_document", document())
    assert upload(http(ocr=None)).status_code == 201
    kwargs = seen["kwargs"]
    assert (kwargs["numero"], kwargs["fecha_documento"], kwargs["total"], kwargs["moneda"], kwargs["ocr"]) == (
        None, None, None, None, None)


def test_the_response_shows_the_stored_document_and_its_ocr_state_but_never_the_bytes(monkeypatch):
    spy(monkeypatch, "add_document", document(contenido=PNG, ocr_estado="NO_CONFIGURADO", total=D("1234.5000"),
                                              moneda="ARS", ocr_texto=None))
    body = upload(http(ocr=None)).json()
    assert body["ocr_estado"] == "NO_CONFIGURADO" and body["id"] == 7 and body["sha256"] == "a" * 64
    assert "contenido" not in body
    assert body["total"] == "1234.5000" and isinstance(body["total"], str)  # money leaves as a string
    assert body["created_at"].startswith("2026-11-05")


@pytest.mark.parametrize("fields", [
    {"tipo": "FOTO"}, {"tipo": ""}, {"moneda": "EUR"}, {"total": "abc"}, {"total": "-1", "moneda": "ARS"},
    {"total": "1" * 20, "moneda": "ARS"}, {"fecha_documento": "03/09/2026"}, {"numero": "x" * 100},
])
def test_upload_rejects_invalid_typed_fields_before_the_service(monkeypatch, fields):
    forbid(monkeypatch, "add_document")
    assert upload(http(ocr=None), **fields).status_code == 422


def test_upload_without_the_file_is_422(monkeypatch):
    forbid(monkeypatch, "add_document")
    response = http(ocr=None).post("/proveedores/PRV-0001/documentos", data={"tipo": "FACTURA"})
    assert response.status_code == 422


def test_a_file_over_10_mb_is_413_and_never_reaches_the_service(monkeypatch):
    forbid(monkeypatch, "add_document")
    response = upload(http(ocr=None), content=PNG + b"\x00" * proveedores.MAX_FILE_BYTES)
    assert response.status_code == 413
    assert "10 MB" in response.json()["detail"]


def test_a_file_of_exactly_10_mb_is_not_refused_by_size(monkeypatch):
    spy(monkeypatch, "add_document", document())
    content = PNG + b"\x00" * (proveedores.MAX_FILE_BYTES - len(PNG))
    assert upload(http(ocr=None), content=content).status_code == 201


def test_a_refused_file_type_is_422_in_spanish(monkeypatch):
    spy(monkeypatch, "add_document", servicios.DatosInvalidos("El archivo no es una foto (JPG, PNG, WebP o PDF)."))
    response = upload(http(ocr=None), content=b"MZ-exe", filename="factura.pdf", mime="application/pdf")
    assert response.status_code == 422 and "JPG, PNG, WebP o PDF" in response.json()["detail"]


def test_a_duplicate_file_is_409_with_a_plain_message(monkeypatch):
    spy(monkeypatch, "add_document", servicios.Conflicto("Ese archivo ya está cargado para este proveedor."))
    response = upload(http(ocr=None))
    assert response.status_code == 409 and response.json() == {"detail": "Ese archivo ya está cargado para este proveedor."}


def test_the_default_ocr_dependency_is_none_without_a_key_and_a_client_with_one(monkeypatch):
    from backend import ocr_llm
    ocr_llm._client_for.cache_clear()
    assert api_module.get_ocr_llm() is None
    monkeypatch.setenv("ANTHROPIC_API_KEY", SECRET)
    assert api_module.get_ocr_llm() is not None
    ocr_llm._client_for.cache_clear()


# --- documents: list, download, retry, confirm --------------------------------------------------------------------

def test_the_list_passes_q_and_never_returns_the_bytes_even_if_the_service_leaked_them(monkeypatch):
    seen = spy(monkeypatch, "list_documents", [document(contenido=PNG, total=D("10"))])
    response = http().get("/proveedores/PRV-0001/documentos", params={"q": "rouez"})
    assert response.status_code == 200 and seen["args"] == ("PRV-0001",) and seen["kwargs"] == {"q": "rouez"}
    item = response.json()[0]
    assert "contenido" not in item and item["total"] == "10"
    assert item["ocr_texto"] == "Total $ 10"  # plain text in JSON: the front shows it as text


def test_the_ocr_text_is_returned_verbatim_as_json_text(monkeypatch):
    attack = "<script>alert(1)</script>'; DROP TABLE x;--"
    spy(monkeypatch, "list_documents", [document(ocr_texto=attack)])
    response = http().get("/proveedores/PRV-0001/documentos")
    assert response.headers["content-type"].startswith("application/json")
    assert response.json()[0]["ocr_texto"] == attack


@pytest.mark.parametrize("mime, disposition", [
    ("image/png", "inline"), ("image/jpeg", "inline"), ("image/webp", "inline"), ("application/pdf", "attachment"),
])
def test_the_file_download_headers(monkeypatch, mime, disposition):
    spy(monkeypatch, "get_file", (PNG, mime, "ñandú.png"))
    response = http().get("/documentos-proveedor/7/archivo")
    assert response.status_code == 200 and response.content == PNG
    assert response.headers["content-type"] == mime
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["content-disposition"].startswith(f"{disposition};")
    assert "filename*=UTF-8''%C3%B1and%C3%BA.png" in response.headers["content-disposition"]
    assert "private" in response.headers["cache-control"]


def test_a_non_numeric_document_id_is_422():
    assert http().get("/documentos-proveedor/abc/archivo").status_code == 422


def test_retry_runs_the_service_with_the_injected_client(monkeypatch):
    ocr = FakeOcr()
    seen = spy(monkeypatch, "retry_ocr", document(ocr_estado="LISTO"))
    response = http(ocr=ocr).post("/documentos-proveedor/7/ocr")
    assert response.status_code == 200 and response.json()["ocr_estado"] == "LISTO"
    assert seen["args"] == (7,) and seen["kwargs"] == {"ocr": ocr}


def test_confirm_data_forwards_only_the_person_confirmed_fields(monkeypatch):
    seen = spy(monkeypatch, "confirm_document_data", document(numero="A-1", total=D("99.5"), moneda="USD"))
    body = {"tipo": "FACTURA", "numero": "A-1", "fecha_documento": "2026-09-03", "total": "99.5", "moneda": "USD"}
    response = http().post("/documentos-proveedor/7/datos", json=body)
    assert response.status_code == 200 and response.json()["total"] == "99.5"
    assert seen["args"] == (7,)
    assert seen["kwargs"] == {"tipo": "FACTURA", "numero": "A-1", "fecha_documento": date(2026, 9, 3),
                              "total": D("99.5"), "moneda": "USD"}


@pytest.mark.parametrize("body", [
    {}, {"tipo": "FOTO"}, {"tipo": "FACTURA", "ocr_texto": "inventado"}, {"tipo": "FACTURA", "contenido": "x"},
    {"tipo": "FACTURA", "ocr_estado": "LISTO"}, {"tipo": "FACTURA", "nombre_archivo": "x"}, {"tipo": "FACTURA", "sha256": "x"},
    {"tipo": "FACTURA", "moneda": "EUR"}, {"tipo": "FACTURA", "total": "-1", "moneda": "ARS"},
    {"tipo": "FACTURA", "fecha_documento": "ayer"},
])
def test_confirm_data_rejects_anything_that_is_not_a_person_confirmed_field(monkeypatch, body):
    forbid(monkeypatch, "confirm_document_data")
    assert http().post("/documentos-proveedor/7/datos", json=body).status_code == 422


def test_a_business_rule_failure_in_confirm_is_422(monkeypatch):
    spy(monkeypatch, "confirm_document_data", servicios.DatosInvalidos("Si cargás un total, indicá la moneda."))
    response = http().post("/documentos-proveedor/7/datos", json={"tipo": "FACTURA", "total": "5"})
    assert response.status_code == 422 and "moneda" in response.json()["detail"]
