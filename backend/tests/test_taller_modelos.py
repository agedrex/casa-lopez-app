"""Only the admin creates a model; the taller receives the sent sheet and fills it (S3 and S4 of odd/tasks/modelo-taller-foto.md, task T4).

No database: the session is a mock, so what is checked is what the service adds to it and the statement it asks for. The
same flow against PostgreSQL was not run here (the matching `test_pg_*` live in test_formulario.py and are skipped without
TEST_DATABASE_URL).

Rules covered:
  R1  only the admin may create a model (`POST /productos/nuevo`); the taller, the gerente and unknown roles get a 403.
  R2  the model starts `validado = False`, its name is normalized, a repeated name is a 409, the category must exist, and the
      sheet records who created it and starts ENVIADO.
  R3  a taller sees the sheets it created in ANY state (to follow them to VALIDADO); what it sees of the others and what it may
      edit stay as before.
  R4  a taller may add a photo only to a model that has a sheet in ENVIADO or that it created; admin has no restriction.
"""

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.dialects import postgresql

from backend import formulario, modelos_foto
from backend.auth import Usuario, get_verifier
from backend.database import get_session
from backend.formulario import SinPermiso, comprobar_edicion, es_visible
from backend.main import app
from backend.models import FormularioConsumo, Modelo
from backend.servicios import Conflicto, DatosInvalidos, NoEncontrado

ADMIN, GERENTE, TALLER = frozenset({"admin"}), frozenset({"gerente"}), frozenset({"taller"})
ESTADOS = ("BORRADOR", "ENVIADO", "COMPLETADO", "VALIDADO")
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 20
RESPUESTA_ALTA = {"modelo": "MOD-0001", "formulario": "FCO-0001", "nombre": "CARTERA LUCÍA"}


@pytest.fixture(autouse=True)
def limpiar(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    yield
    app.dependency_overrides.clear()


def cliente(role, usuario="taller-1", session=None):
    session = session or MagicMock()
    app.dependency_overrides[get_session] = lambda: session
    app.dependency_overrides[get_verifier] = lambda: (lambda request: Usuario(id=usuario, role=role))
    return TestClient(app, raise_server_exceptions=False)


def sql(consulta) -> str:
    return str(consulta.compile(dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True}))


# --- R1: who may create a model (HTTP gate) ---------------------------------------------------------------------------

def test_r1_admin_creates_a_model_and_the_service_gets_the_creator(monkeypatch):
    visto = {}
    monkeypatch.setattr(formulario, "alta_rapida", lambda session, **k: visto.update(k) or RESPUESTA_ALTA)
    respuesta = cliente("admin", usuario="u-9").post(
        "/productos/nuevo", json={"nombre": "cartera lucía", "categoria": "Carteras", "tamano": "CHICO", "nota": "con fuelle"})
    assert respuesta.status_code == 201 and respuesta.json() == RESPUESTA_ALTA
    assert visto == {"nombre": "cartera lucía", "categoria": "Carteras", "tamano": "CHICO", "nota": "con fuelle", "quien": "u-9"}


@pytest.mark.parametrize("role", ["taller", "corte", "gerente", "consulta", "otro", None])
def test_r1_taller_gerente_and_unknown_roles_cannot_create_a_model_and_the_service_is_not_called(monkeypatch, role):
    monkeypatch.setattr(formulario, "alta_rapida", lambda *a, **k: pytest.fail("the service must not be called"))
    respuesta = cliente(role).post("/productos/nuevo", json={"nombre": "X", "categoria": "Carteras"})
    assert respuesta.status_code == 403 and respuesta.json() == {"detail": "No tenés permiso para esta acción."}


@pytest.mark.parametrize("metodo, ruta, cuerpo", [
    ("POST", "/formularios", {"articulo": "A"}), ("POST", "/productos/nuevo", {"nombre": "X", "categoria": "Carteras"}), ("POST", "/formularios/FCO-0001/validar", None),
    ("POST", "/formularios/FCO-0001/devolver", {"comentario": "x"}), ("POST", "/formularios/FCO-0001/enviar", None),
    ("POST", "/formularios/FCO-0001/duplicar", {"articulo": "A"}), ("POST", "/modelos", {"nombre_del_modelo": "X"}),
    ("POST", "/modelos/MOD-0001/validado", {"validado": True}), ("POST", "/categorias", {"nombre": "Nueva", "nota": None}),
])
def test_r1_the_taller_cannot_reach_the_admin_routes_next_to_the_creation(monkeypatch, metodo, ruta, cuerpo):
    for nombre in ("crear_formulario", "cambiar_estado", "duplicar_formulario", "alta_rapida"):
        monkeypatch.setattr(formulario, nombre, lambda *a, **k: pytest.fail("the service must not be called"))
    respuesta = cliente("taller").request(metodo, ruta, json=cuerpo)
    assert respuesta.status_code == 403 and respuesta.json() == {"detail": "No tenés permiso para esta acción."}


# --- R2: what the creation does (service) -----------------------------------------------------------------------------

@pytest.fixture
def alta(monkeypatch):
    """The service with its code generators replaced; returns (session, rows added through `_insertar`)."""
    session = MagicMock()
    session.scalars.return_value = ["BILLETERA ROJA"]  # the names of the existing models
    session.scalar.return_value = SimpleNamespace(id=3, nombre="Carteras")  # the category lookup
    filas = []
    monkeypatch.setattr(formulario, "_siguiente_numero", lambda s, columna, prefijo: 1)

    def insertar(session, fila, conflicto):
        fila.id = len(filas) + 10
        filas.append(fila)
    monkeypatch.setattr(formulario, "_insertar", insertar)
    return session, filas


def test_r2_the_model_starts_without_validation_the_name_is_normalized_and_the_sheet_remembers_its_creator(alta):
    session, filas = alta
    resultado = formulario.alta_rapida(session, nombre="  cartera   lucía ", categoria="Carteras", quien="taller-1", tamano="CHICO", nota=" con fuelle ")
    modelo = next(f for f in filas if isinstance(f, Modelo))
    hoja = next(f for f in filas if isinstance(f, FormularioConsumo))
    assert (modelo.nombre_del_modelo, modelo.validado, modelo.tamano, modelo.categoria_id, modelo.nota) == (
        "CARTERA LUCÍA", False, "CHICO", 3, "con fuelle")
    assert modelo.cuero_m2_por_unidad is None  # consumptions stay missing data until the sheet is validated
    assert (hoja.creado_por, hoja.estado, hoja.modelo_id, hoja.articulo) == ("taller-1", "ENVIADO", modelo.id, "CARTERA LUCÍA")
    assert hoja.enviado_en is not None
    assert resultado == {"modelo": modelo.codigo, "formulario": hoja.codigo, "nombre": "CARTERA LUCÍA"}
    session.commit.assert_called_once()


def test_r2_a_repeated_name_is_a_409_whatever_the_case_and_nothing_is_written(alta):
    session, filas = alta
    with pytest.raises(Conflicto, match="Ya hay un modelo llamado BILLETERA ROJA"):
        formulario.alta_rapida(session, nombre="billetera   roja", categoria="Carteras", quien="taller-1")
    assert filas == [] and not session.commit.called


def test_r2_an_unknown_category_or_size_is_a_422_and_nothing_is_written(alta):
    session, filas = alta
    session.scalar.return_value = None
    with pytest.raises(DatosInvalidos, match="No existe la categoría Inventada"):
        formulario.alta_rapida(session, nombre="Nueva", categoria="Inventada", quien="taller-1")
    session.scalar.return_value = SimpleNamespace(id=3)
    with pytest.raises(DatosInvalidos, match="tamaño"):
        formulario.alta_rapida(session, nombre="Nueva", categoria="Carteras", quien="taller-1", tamano="ENORME")
    assert filas == [] and not session.commit.called


def test_r2_the_api_maps_the_duplicate_to_409_for_the_admin(monkeypatch):
    def repetido(session, **k):
        raise Conflicto("Ya hay un modelo llamado CARTERA LUCÍA: agregá algo que lo distinga.")
    monkeypatch.setattr(formulario, "alta_rapida", repetido)
    respuesta = cliente("admin").post("/productos/nuevo", json={"nombre": "cartera lucía", "categoria": "Carteras"})
    assert respuesta.status_code == 409 and "Ya hay un modelo llamado" in respuesta.json()["detail"]


# --- R3: what a taller sees and edits ---------------------------------------------------------------------------------

@pytest.mark.parametrize("estado", ESTADOS)
def test_r3_a_taller_sees_its_own_sheets_in_every_state_and_the_others_as_before(estado):
    assert es_visible(estado, TALLER, propio=True) is True
    assert es_visible(estado, TALLER) is (estado in ("ENVIADO", "COMPLETADO"))
    assert es_visible(estado, TALLER, propio=False) is (estado in ("ENVIADO", "COMPLETADO"))
    assert es_visible(estado, ADMIN) and es_visible(estado, ADMIN, propio=True)  # admin unchanged
    assert es_visible(estado, GERENTE, propio=True) is False and es_visible(estado, frozenset(), propio=True) is False


def test_r3_what_a_taller_may_edit_is_unchanged_only_the_rows_and_only_while_enviado():
    assert comprobar_edicion("ENVIADO", TALLER) is True
    for estado in ("BORRADOR", "COMPLETADO", "VALIDADO"):
        with pytest.raises(Conflicto):
            comprobar_edicion(estado, TALLER)


def hoja(estado, creado_por):
    return SimpleNamespace(estado=estado, creado_por=creado_por, id=5, codigo="FCO-0005")


def cargar_con(estado, creado_por, roles, quien):
    session = MagicMock()
    session.execute.return_value.one_or_none.return_value = (hoja(estado, creado_por), None, None, "MOD-0005")
    return formulario._cargar(session, "FCO-0005", roles, quien=quien)


def test_r3_loading_a_validated_sheet_works_for_its_creator_only():
    assert cargar_con("VALIDADO", "taller-1", TALLER, "taller-1")[0].estado == "VALIDADO"
    for quien in ("taller-2", None):
        with pytest.raises(NoEncontrado):
            cargar_con("VALIDADO", "taller-1", TALLER, quien)
    assert cargar_con("VALIDADO", "taller-1", ADMIN, "admin-1")[0].estado == "VALIDADO"
    assert cargar_con("ENVIADO", "taller-1", TALLER, "taller-2")[0].estado == "ENVIADO"  # as before: any taller
    with pytest.raises(NoEncontrado):
        cargar_con("BORRADOR", "admin-1", TALLER, "taller-1")  # a draft the admin made is not the taller's


def listar(roles, quien):
    session = MagicMock()
    session.execute.return_value.all.return_value = []
    formulario.listar_formularios(session, q=None, estado=None, roles=roles, quien=quien)
    return sql(session.execute.call_args.args[0])


def test_r3_the_list_of_a_taller_adds_its_own_sheets_and_the_others_do_not_change():
    propio = listar(TALLER, "taller-1")
    assert "formulario_consumo.estado IN ('COMPLETADO', 'ENVIADO')" in propio and "creado_por = 'taller-1'" in propio
    assert " OR " in propio
    sin_quien = listar(TALLER, None)
    assert "formulario_consumo.estado IN ('COMPLETADO', 'ENVIADO')" in sin_quien and "creado_por =" not in sin_quien
    admin = listar(ADMIN, "admin-1")
    assert "formulario_consumo.estado IN" not in admin and "creado_por =" not in admin


def test_r3_the_api_hands_the_user_id_to_the_read_and_save_services(monkeypatch):
    vistos = {}
    monkeypatch.setattr(formulario, "listar_formularios", lambda s, **k: vistos.update(listar=k) or [])
    monkeypatch.setattr(formulario, "obtener_formulario", lambda s, codigo, roles, **k: vistos.update(obtener=(codigo, roles, k)) or pytest.fail("stop"))
    monkeypatch.setattr(formulario, "guardar_formulario", lambda s, codigo, **k: vistos.update(guardar=(codigo, k)) or pytest.fail("stop"))
    c = cliente("taller", usuario="taller-1")
    c.get("/formularios")
    c.get("/formularios/FCO-0001")
    c.put("/formularios/FCO-0001", json={"articulo": "A", "lineas": []})
    assert vistos["listar"]["quien"] == "taller-1" and vistos["listar"]["roles"] == TALLER
    assert vistos["obtener"] == ("FCO-0001", TALLER, {"quien": "taller-1"})
    assert vistos["guardar"][1]["quien"] == "taller-1"


# --- R4: the photo of a model -----------------------------------------------------------------------------------------

def sesion_foto(permiso):
    """Order of the service's lookups: the model, then (taller only) the sheet that allows it, then the photo number."""
    session = MagicMock()
    session.scalar.side_effect = [SimpleNamespace(id=7, codigo="MOD-0001"), *permiso, None]
    return session


def test_r4_a_taller_may_add_a_photo_to_a_model_with_a_sheet_it_may_work_on():
    session = sesion_foto([1])
    resultado = modelos_foto.add_photo(session, "MOD-0001", contenido=PNG, subido_por="taller-1", roles=TALLER)
    assert resultado["codigo"] == "MFO-0001"
    permiso = sql(session.scalar.call_args_list[1].args[0])
    assert "formulario_consumo.modelo_id = 7" in permiso
    assert "formulario_consumo.estado = 'ENVIADO'" in permiso and "formulario_consumo.creado_por = 'taller-1'" in permiso
    session.add.assert_called_once()


def test_r4_a_taller_cannot_add_a_photo_to_any_other_model_and_nothing_is_stored():
    session = sesion_foto([None])
    with pytest.raises(SinPermiso, match="No tenés permiso para subir la foto de este modelo."):
        modelos_foto.add_photo(session, "MOD-0001", contenido=PNG, subido_por="taller-1", roles=TALLER)
    session.add.assert_not_called()
    session.commit.assert_not_called()


def test_r4_the_admin_is_unrestricted_and_does_not_even_look_for_a_sheet():
    session = MagicMock()
    session.scalar.side_effect = [SimpleNamespace(id=7, codigo="MOD-0001"), None]
    modelos_foto.add_photo(session, "MOD-0001", contenido=PNG, subido_por="admin-1", roles=ADMIN)
    assert session.scalar.call_count == 2  # the model and the photo number: no permission query


def test_r4_an_unknown_model_is_still_a_404_for_a_taller():
    session = MagicMock()
    session.scalar.side_effect = [None]
    with pytest.raises(NoEncontrado):
        modelos_foto.add_photo(session, "MOD-9999", contenido=PNG, subido_por="taller-1", roles=TALLER)


def test_r4_the_api_hands_the_roles_to_the_service_and_a_refusal_is_a_403(monkeypatch):
    def rechazar(session, codigo, **k):
        assert k["roles"] == TALLER and k["subido_por"] == "taller-1"
        raise SinPermiso("No tenés permiso para subir la foto de este modelo.")
    monkeypatch.setattr(modelos_foto, "add_photo", rechazar)
    respuesta = cliente("taller").post("/modelos/MOD-0001/foto", files={"archivo": ("f.png", PNG, "image/png")})
    assert respuesta.status_code == 403 and respuesta.json() == {"detail": "No tenés permiso para subir la foto de este modelo."}
