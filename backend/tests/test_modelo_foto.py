"""Model photo: storage rules (magic bytes, size, append-only), the two endpoints and their roles, and the `tiene_foto` flag.

No database: the session is a mock, so what is checked is what the service adds to it (or does not) and the statement it
asks for. The same flow against PostgreSQL (bytea, the FK, the CHECKs) was not run here.
"""

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.dialects import postgresql

from backend import modelos_foto, proveedores, servicios
from backend.auth import Usuario, get_verifier
from backend.database import get_session
from backend.main import app
from backend.models import ModeloFoto

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 20
JPEG = b"\xff\xd8\xff\xe0" + b"\x00" * 20
WEBP = b"RIFF\x24\x00\x00\x00WEBPVP8 " + b"\x00" * 20
PDF = b"%PDF-1.7\n" + b"\x00" * 20
GIF = b"GIF89a" + b"\x00" * 20
SVG = b"<svg xmlns='http://www.w3.org/2000/svg'><script>alert(1)</script></svg>"
NOW = datetime(2026, 11, 16, 12, 0, tzinfo=timezone.utc)
RESPUESTA = {"codigo": "MFO-0001", "modelo": "MOD-0001", "tipo_mime": "image/png", "tamano_bytes": len(PNG), "created_at": NOW}


@pytest.fixture(autouse=True)
def limpiar(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    yield
    app.dependency_overrides.clear()


def _sesion(modelo=SimpleNamespace(id=7, codigo="MOD-0001"), ultimo=None):
    """A session whose model lookup and photo-number lookup are answered in the order the service asks for them."""
    session = MagicMock()
    session.scalar.side_effect = [modelo, ultimo]
    return session


def _cliente(role="admin", session=None):
    session = session or MagicMock()
    app.dependency_overrides[get_session] = lambda: session
    app.dependency_overrides[get_verifier] = lambda: (lambda request: Usuario(id="u1", role=role))
    return TestClient(app)


def _subir(cliente, contenido=PNG, nombre="foto.png", tipo="image/png"):
    return cliente.post("/modelos/MOD-0001/foto", files={"archivo": (nombre, contenido, tipo)})


# --- storage rules -------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("contenido, mime", [(PNG, "image/png"), (JPEG, "image/jpeg"), (WEBP, "image/webp")])
def test_a_valid_image_is_stored_with_the_type_its_bytes_say(contenido, mime):
    session = _sesion(ultimo=3)
    resultado = modelos_foto.add_photo(session, "MOD-0001", contenido=contenido, subido_por="u1", roles=frozenset({"admin"}))
    fila = session.add.call_args.args[0]
    assert isinstance(fila, ModeloFoto)
    assert (fila.codigo, fila.modelo_id, fila.tipo_mime, fila.tamano_bytes, fila.subido_por) == (
        "MFO-0004", 7, mime, len(contenido), "u1")
    assert fila.contenido == contenido and len(fila.sha256) == 64
    session.commit.assert_called_once()
    assert resultado["codigo"] == "MFO-0004" and resultado["modelo"] == "MOD-0001" and resultado["tipo_mime"] == mime


@pytest.mark.parametrize("contenido, mensaje", [
    (PDF, modelos_foto.MESSAGE_FILE_TYPE), (GIF, modelos_foto.MESSAGE_FILE_TYPE), (SVG, modelos_foto.MESSAGE_FILE_TYPE),
    (b"hola, no soy una foto", modelos_foto.MESSAGE_FILE_TYPE), (b"", "La foto está vacía."),
])
def test_anything_that_is_not_jpeg_png_or_webp_is_refused_and_nothing_is_stored(contenido, mensaje):
    session = _sesion()
    with pytest.raises(servicios.DatosInvalidos) as error:
        modelos_foto.add_photo(session, "MOD-0001", contenido=contenido, subido_por="u1", roles=frozenset({"admin"}))
    assert str(error.value) == mensaje
    session.add.assert_not_called()
    session.commit.assert_not_called()


def test_the_declared_type_and_the_file_name_do_not_decide_a_script_posing_as_png_is_refused_with_422():
    session = _sesion()
    respuesta = _subir(_cliente(session=session), contenido=SVG, nombre="logo.png", tipo="image/png")
    assert respuesta.status_code == 422 and respuesta.json() == {"detail": modelos_foto.MESSAGE_FILE_TYPE}
    session.add.assert_not_called()


def test_a_photo_over_the_limit_is_refused_with_413_and_nothing_is_stored():
    session = _sesion()
    grande = PNG + b"\x00" * (modelos_foto.MAX_FOTO_BYTES - len(PNG) + 1)
    respuesta = _subir(_cliente(session=session), contenido=grande)
    assert respuesta.status_code == 413 and respuesta.json() == {"detail": "La foto supera el máximo de 5 MB."}
    session.add.assert_not_called()
    session.commit.assert_not_called()


def test_a_photo_exactly_at_the_limit_is_accepted():
    justo = PNG + b"\x00" * (modelos_foto.MAX_FOTO_BYTES - len(PNG))
    session = _sesion()
    modelos_foto.add_photo(session, "MOD-0001", contenido=justo, subido_por="u1", roles=frozenset({"admin"}))
    session.add.assert_called_once()


def test_the_limit_is_5_mb_and_never_above_the_one_of_the_supplier_documents():
    assert modelos_foto.MAX_FOTO_BYTES == 5 * 1024 * 1024 <= proveedores.MAX_FILE_BYTES


def test_a_photo_for_a_model_that_does_not_exist_is_a_404_and_nothing_is_stored():
    session = _sesion(modelo=None)
    with pytest.raises(servicios.NoEncontrado):
        modelos_foto.add_photo(session, "MOD-9999", contenido=PNG, subido_por="u1", roles=frozenset({"admin"}))
    session.add.assert_not_called()


def test_the_first_photo_of_the_table_is_mfo_0001():
    session = _sesion(ultimo=None)
    assert modelos_foto.add_photo(session, "MOD-0001", contenido=PNG, subido_por="u1", roles=frozenset({"admin"}))["codigo"] == "MFO-0001"


def test_a_new_upload_is_a_new_row_and_never_updates_or_deletes_the_previous_one():
    session = MagicMock()
    for numero in (None, 1):
        session.scalar.side_effect = [SimpleNamespace(id=7, codigo="MOD-0001"), numero]
        modelos_foto.add_photo(session, "MOD-0001", contenido=PNG, subido_por="u1", roles=frozenset({"admin"}))
    assert [c.args[0].codigo for c in session.add.call_args_list] == ["MFO-0001", "MFO-0002"]
    session.delete.assert_not_called()
    session.merge.assert_not_called()


def test_the_current_photo_is_the_newest_row_of_that_model_and_its_bytes_are_loaded():
    session = MagicMock()
    session.scalar.return_value = SimpleNamespace(contenido=memoryview(PNG), tipo_mime="image/png")
    assert modelos_foto.get_photo(session, "MOD-0001") == (PNG, "image/png")
    sql = str(session.scalar.call_args.args[0].compile(dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True}))
    assert "ORDER BY costos.modelo_foto.id DESC" in sql and "LIMIT 1" in sql and "'MOD-0001'" in sql
    assert "costos.modelo_foto.contenido" in sql  # undeferred: this is the one read that needs the bytes


def test_a_model_without_photo_is_a_404_in_spanish():
    session = MagicMock()
    session.scalar.return_value = None
    with pytest.raises(servicios.NoEncontrado, match="no tiene foto"):
        modelos_foto.get_photo(session, "MOD-0001")


# --- endpoints and roles -------------------------------------------------------------------------------------------

@pytest.mark.parametrize("role", ["admin", "taller"])
def test_admin_and_taller_can_upload(monkeypatch, role):
    vistos = {}
    monkeypatch.setattr(modelos_foto, "add_photo", lambda session, codigo, **k: vistos.update(codigo=codigo, **k) or RESPUESTA)
    respuesta = _subir(_cliente(role))
    assert respuesta.status_code == 201 and respuesta.json()["codigo"] == "MFO-0001"
    assert vistos == {"codigo": "MOD-0001", "contenido": PNG, "subido_por": "u1", "roles": frozenset({role})}


@pytest.mark.parametrize("role", ["gerente", "consulta", "otro", None])
def test_gerente_and_unknown_roles_cannot_upload_and_no_service_runs(monkeypatch, role):
    monkeypatch.setattr(modelos_foto, "add_photo", lambda *a, **k: pytest.fail("must not run"))
    respuesta = _subir(_cliente(role))
    assert respuesta.status_code == 403 and respuesta.json() == {"detail": "No tenés permiso para esta acción."}


@pytest.mark.parametrize("role", ["admin", "gerente", "taller"])
def test_the_three_roles_can_read_the_photo(monkeypatch, role):
    monkeypatch.setattr(modelos_foto, "get_photo", lambda session, codigo: (PNG, "image/png"))
    respuesta = _cliente(role).get("/modelos/MOD-0001/foto")
    assert respuesta.status_code == 200 and respuesta.content == PNG


def test_without_a_session_both_routes_answer_401():
    app.dependency_overrides[get_verifier] = lambda: (lambda request: None)
    cliente = TestClient(app)
    assert cliente.get("/modelos/MOD-0001/foto").status_code == 401
    assert _subir(cliente).status_code == 401


def test_the_photo_is_served_with_its_type_nosniff_and_a_short_private_cache(monkeypatch):
    monkeypatch.setattr(modelos_foto, "get_photo", lambda session, codigo: (JPEG, "image/jpeg"))
    respuesta = _cliente("gerente").get("/modelos/MOD-0001/foto")
    assert respuesta.headers["content-type"] == "image/jpeg"
    assert respuesta.headers["x-content-type-options"] == "nosniff"
    assert respuesta.headers["cache-control"] == "private, max-age=60"
    assert respuesta.headers["content-security-policy"] == "default-src 'none'; sandbox"
    assert respuesta.headers["content-disposition"].startswith("inline;")


def test_reading_a_model_without_photo_answers_404(monkeypatch):
    def sin_foto(session, codigo):
        raise servicios.NoEncontrado("Este modelo no tiene foto.")
    monkeypatch.setattr(modelos_foto, "get_photo", sin_foto)
    respuesta = _cliente().get("/modelos/MOD-0001/foto")
    assert respuesta.status_code == 404 and respuesta.json() == {"detail": "Este modelo no tiene foto."}


def test_the_upload_needs_the_file_field():
    assert _cliente().post("/modelos/MOD-0001/foto").status_code == 422


# --- tiene_foto ----------------------------------------------------------------------------------------------------

def _modelo(codigo="MOD-0001"):
    return SimpleNamespace(
        codigo=codigo, nombre_del_modelo="Cartera", tamano=None, cuero_m2_por_unidad=None, forro_m2_por_unidad=None,
        flex_m2_por_unidad=None, goma_eva_m2_por_unidad=None, herrajes_usd_por_unidad=None, hilo_y_cemento=None,
        confeccion_estimada_ars=None, horas_de_confeccion=None, origen_de_los_consumos=None, validado=False,
        nota=None, modelo_excel_viejo=None, fila_excel_viejo=None, id=7)


def test_the_list_carries_tiene_foto_per_model_with_an_exists_and_never_loads_the_bytes():
    session = MagicMock()
    session.execute.return_value.all.return_value = [
        (_modelo("MOD-0001"), None, None, True, None, None), (_modelo("MOD-0002"), None, None, False, None, None)]
    filas = servicios.listar_modelos(session)
    assert [(f["codigo"], f["tiene_foto"]) for f in filas] == [("MOD-0001", True), ("MOD-0002", False)]
    sql = str(session.execute.call_args.args[0].compile(dialect=postgresql.dialect()))
    assert "EXISTS (SELECT costos.modelo_foto.id" in sql and "tiene_foto" in sql
    assert "modelo_foto.contenido" not in sql
    assert session.execute.call_count == 1  # one query for the whole list, not one per model


def test_the_detail_carries_tiene_foto(monkeypatch):
    session = MagicMock()
    session.execute.return_value.one_or_none.return_value = (_modelo(), None, None, True)
    session.scalar.return_value = 0
    monkeypatch.setattr(servicios, "_insumos_del_modelo", lambda s, modelo_id: [])
    assert servicios.detalle_modelo(session, "MOD-0001")["tiene_foto"] is True
    sql = str(session.execute.call_args_list[0].args[0].compile(dialect=postgresql.dialect()))
    assert "EXISTS" in sql and "modelo_foto.contenido" not in sql


def test_the_api_exposes_tiene_foto_in_the_list_and_the_detail(monkeypatch):
    claves = (
        "categoria", "tamano", "cuero_m2_por_unidad", "forro", "forro_m2_por_unidad", "flex_m2_por_unidad",
        "goma_eva_m2_por_unidad", "herrajes_usd_por_unidad", "hilo_y_cemento", "confeccion_estimada_ars",
        "horas_de_confeccion", "origen_de_los_consumos")
    fila = {**dict.fromkeys(claves), "codigo": "MOD-0001", "nombre_del_modelo": "Cartera", "validado": False, "tiene_foto": True}
    monkeypatch.setattr(servicios, "listar_modelos", lambda *a, **k: [fila])
    monkeypatch.setattr(servicios, "detalle_modelo", lambda *a, **k: {
        **fila, "nota": None, "modelo_excel_viejo": None, "fila_excel_viejo": None, "productos": 0, "insumos": []})
    cliente = _cliente("gerente")
    assert cliente.get("/modelos").json()[0]["tiene_foto"] is True
    assert cliente.get("/modelos/MOD-0001").json()["tiene_foto"] is True


def test_the_orm_model_defers_the_bytes_and_indexes_the_model():
    tabla = ModeloFoto.__table__
    assert tabla.c.modelo_id.index and {fk.target_fullname for fk in tabla.foreign_keys} == {"costos.modelo.id"}
    diferidas = [propiedad.key for propiedad in ModeloFoto.__mapper__.column_attrs if propiedad.deferred]
    assert diferidas == ["contenido"]
