"""Consumption form of a new article (S1-S3, S5, S8 of odd/tasks/formulario-consumos.md): rows, state machine, roles, API.

The pure rules run with no database; the service functions run against a stubbed loader; the HTTP gate and the error
mapping against a stubbed service layer. The PostgreSQL tests at the bottom are skipped without TEST_DATABASE_URL.
"""

import runpy
from datetime import datetime, timezone
from decimal import Decimal as D
from itertools import product as producto_cartesiano
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import CheckConstraint, UniqueConstraint
from sqlalchemy.exc import IntegrityError

from backend import formulario
from backend.auth import Usuario, get_verifier
from backend.database import get_session
from backend.formulario import (
    ACCIONES, LINEAS_PRECARGADAS, MENSAJE_VALIDADO, SinPermiso, armar_lineas, comprobar_edicion, es_visible,
    lineas_precargadas, siguiente_estado,
)
from backend.main import app
from backend.models import Base, FormularioConsumo, FormularioConsumoLinea
from backend.servicios import Conflicto, DatosInvalidos, NoEncontrado

ESTADOS = ("BORRADOR", "ENVIADO", "COMPLETADO", "VALIDADO")
ADMIN, GERENTE, TALLER = frozenset({"admin"}), frozenset({"gerente"}), frozenset({"taller"})
OTRO = frozenset()

CONSUMOS_DE_LA_HOJA = [
    "CUERO", "FORRO / TELA", "FORRO / POTRO", "GOMA EVA", "FRISELINA", "CARTÓN FIBRA", "FLEX", "CARTULINA", "MOIRE",
    "HS. DE TRABAJO", "Y/O MANO DE OBRA TALLER", "DESPERDICIO 30%", "CORTE MANO DE OBRA", "EMPAQUE",
]
HERRAJES_DE_LA_HOJA = [
    "CIERRE N5", "CIERRE N3", "DESLIZADOR N5", "DESLIZADOR N3", "HEBILLA", "MOSQUETÓN", "MEDIA LUNA", "ARGOLLA 10MM",
    "IMÁN", "TORNIQUETE", "CADENA", "REMACHES", "SPAGUETTI", "TRENCILLA", "MANGUERA", "OJALILLO",
]


@pytest.fixture(autouse=True)
def limpiar(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    yield
    app.dependency_overrides.clear()


def linea(nombre="CUERO", seccion="CONSUMO", cantidad=None, comentario=None):
    return {"seccion": seccion, "nombre": nombre, "cantidad": cantidad, "comentario": comentario}


# --- S2 / S3: the preloaded rows ------------------------------------------------------------------------------------

def test_s2_the_preloaded_consumos_are_the_14_rows_of_the_sheet_in_order():
    assert list(LINEAS_PRECARGADAS["CONSUMO"]) == CONSUMOS_DE_LA_HOJA and len(CONSUMOS_DE_LA_HOJA) == 14


def test_s3_the_preloaded_herrajes_are_the_16_rows_of_the_sheet_in_order():
    assert list(LINEAS_PRECARGADAS["HERRAJE"]) == HERRAJES_DE_LA_HOJA and len(HERRAJES_DE_LA_HOJA) == 16


def test_s5_a_new_form_copies_the_constant_with_empty_quantities_comments_and_consecutive_order():
    lineas = lineas_precargadas()
    assert [(l["seccion"], l["orden"], l["nombre"]) for l in lineas] == (
        [("CONSUMO", i, n) for i, n in enumerate(CONSUMOS_DE_LA_HOJA, 1)]
        + [("HERRAJE", i, n) for i, n in enumerate(HERRAJES_DE_LA_HOJA, 1)])
    assert all(l["cantidad"] is None and l["comentario"] is None for l in lineas)
    lineas[0]["nombre"] = "OTRO"  # a form's rows never write back into the constant
    assert LINEAS_PRECARGADAS["CONSUMO"][0] == "CUERO" and lineas_precargadas()[0]["nombre"] == "CUERO"


# --- S8: the state machine (pure) -----------------------------------------------------------------------------------

PERMITIDAS = {  # (action, from) -> to
    ("enviar", "BORRADOR"): "ENVIADO", ("enviar", "ENVIADO"): "ENVIADO",
    ("completar", "ENVIADO"): "COMPLETADO",
    ("devolver", "COMPLETADO"): "ENVIADO",
    ("validar", "COMPLETADO"): "VALIDADO",
}
QUIENES = {"enviar": ADMIN, "completar": ADMIN | TALLER, "devolver": ADMIN, "validar": ADMIN}


@pytest.mark.parametrize("accion, estado", list(producto_cartesiano(ACCIONES, ESTADOS)))
def test_s8_every_transition_is_allowed_or_a_409_with_a_spanish_message(accion, estado):
    if (accion, estado) in PERMITIDAS:
        assert siguiente_estado(accion, estado, ADMIN) == PERMITIDAS[(accion, estado)]
        return
    with pytest.raises(Conflicto) as error:
        siguiente_estado(accion, estado, ADMIN)
    if estado == "VALIDADO":
        assert str(error.value) == MENSAJE_VALIDADO
    else:
        assert estado.lower() in str(error.value) and str(error.value).startswith("Solo se puede")


@pytest.mark.parametrize("accion, roles", list(producto_cartesiano(ACCIONES, (ADMIN, TALLER, GERENTE, OTRO, ADMIN | TALLER))))
def test_s8_each_action_belongs_to_its_roles_and_gerente_never_acts(accion, roles):
    estado_valido = next(desde for (a, desde) in PERMITIDAS if a == accion)
    if roles & QUIENES[accion]:
        assert siguiente_estado(accion, estado_valido, roles) == PERMITIDAS[(accion, estado_valido)]
    else:
        with pytest.raises(SinPermiso):
            siguiente_estado(accion, estado_valido, roles)


def test_s8_the_taller_can_complete_but_cannot_validate_send_or_return():
    assert siguiente_estado("completar", "ENVIADO", TALLER) == "COMPLETADO"
    for accion, estado in (("validar", "COMPLETADO"), ("enviar", "BORRADOR"), ("devolver", "COMPLETADO")):
        with pytest.raises(SinPermiso):
            siguiente_estado(accion, estado, TALLER)


def test_s8_a_validated_form_accepts_no_action_at_all():
    for accion in ACCIONES:
        with pytest.raises(Conflicto, match="duplicalo"):
            siguiente_estado(accion, "VALIDADO", ADMIN)


@pytest.mark.parametrize("estado", ESTADOS)
def test_s8_who_may_edit_in_each_state(estado):
    if estado == "VALIDADO":
        for roles in (ADMIN, TALLER, ADMIN | TALLER):
            with pytest.raises(Conflicto, match="duplicalo"):
                comprobar_edicion(estado, roles)
        return
    assert comprobar_edicion(estado, ADMIN) is False  # False: the admin may change more than the rows
    assert comprobar_edicion(estado, ADMIN | TALLER) is False
    if estado == "ENVIADO":
        assert comprobar_edicion(estado, TALLER) is True  # True: only the rows
    else:
        with pytest.raises(Conflicto):
            comprobar_edicion(estado, TALLER)


def test_s8_gerente_and_unknown_roles_cannot_edit():
    for roles in (GERENTE, OTRO):
        with pytest.raises(SinPermiso):
            comprobar_edicion("ENVIADO", roles)


@pytest.mark.parametrize("estado", ESTADOS)
def test_s8_visibility_admin_sees_everything_taller_only_enviado_and_completado_gerente_nothing(estado):
    assert es_visible(estado, ADMIN) and es_visible(estado, ADMIN | TALLER)
    assert es_visible(estado, GERENTE) is False  # the Formularios module is closed to the gerente
    assert es_visible(estado, TALLER) is (estado in ("ENVIADO", "COMPLETADO"))
    assert es_visible(estado, OTRO) is False


# --- The rows: validation and numbering (pure) ----------------------------------------------------------------------

def test_the_order_of_each_row_is_its_position_inside_its_section_and_names_are_trimmed():
    armadas = armar_lineas([
        linea(" A "), linea("H1", "HERRAJE"), linea("B"), linea("H2", "HERRAJE", D("2.5"), "  obs  "), linea("C")])
    assert [(l["seccion"], l["orden"], l["nombre"]) for l in armadas] == [
        ("CONSUMO", 1, "A"), ("CONSUMO", 2, "B"), ("CONSUMO", 3, "C"), ("HERRAJE", 1, "H1"), ("HERRAJE", 2, "H2")]
    assert armadas[-1]["cantidad"] == D("2.5") and armadas[-1]["comentario"] == "obs"


def test_zero_and_null_quantities_are_valid_and_an_empty_comment_becomes_null():
    armadas = armar_lineas([linea("A", cantidad=D("0"), comentario="   "), linea("B", cantidad=None)])
    assert [l["cantidad"] for l in armadas] == [D("0"), None] and armadas[0]["comentario"] is None


def test_a_negative_quantity_is_rejected_naming_the_row():
    with pytest.raises(DatosInvalidos, match="CUERO"):
        armar_lineas([linea("CUERO", cantidad=D("-0.000001"))])


@pytest.mark.parametrize("malo", [linea("   "), linea(""), linea(None), linea("A", seccion="OTRA"), linea("A", seccion=None)])
def test_a_row_needs_a_name_and_one_of_the_two_sections(malo):
    with pytest.raises(DatosInvalidos):
        armar_lineas([malo])


def test_an_empty_form_and_the_row_limit():
    assert armar_lineas([]) == []  # no row is mandatory
    with pytest.raises(DatosInvalidos):
        armar_lineas([linea(f"N{i}") for i in range(formulario.MAX_LINEAS + 1)])


# --- The service against a stubbed loader --------------------------------------------------------------------------

def fila(estado="ENVIADO", articulo="Cartera Lucía", nota=None):
    return FormularioConsumo(codigo="FCO-0001", articulo=articulo, estado=estado, nota=nota, creado_por="admin-1")


def con_formulario(monkeypatch, instancia):
    """Replace the loader and the serializer; returns the session mock so the test can see what was written."""
    session = MagicMock()
    monkeypatch.setattr(formulario, "_cargar", lambda s, codigo, roles, bloquear=False: (instancia, None, None, None))
    monkeypatch.setattr(formulario, "_detalle", lambda s, f, p, t, m=None: {"estado": f.estado, "articulo": f.articulo, "nota": f.nota})
    return session


def test_the_taller_cannot_change_the_articulo_or_the_nota_only_the_rows(monkeypatch):
    instancia = fila("ENVIADO", nota="vieja")
    session = con_formulario(monkeypatch, instancia)
    for articulo, nota in (("Otro nombre", "vieja"), ("Cartera Lucía", "nueva"), ("Cartera Lucía", None)):
        with pytest.raises(SinPermiso):
            formulario.guardar_formulario(session, "FCO-0001", articulo=articulo, nota=nota, lineas=[linea()], roles=TALLER)
    session.add_all.assert_not_called()
    assert (instancia.articulo, instancia.nota) == ("Cartera Lucía", "vieja")
    # Same articulo and nota (even with stray spaces): the rows are replaced.
    formulario.guardar_formulario(session, "FCO-0001", articulo=" Cartera Lucía ", nota="vieja ", lineas=[linea()], roles=TALLER)
    session.add_all.assert_called_once()


def test_the_admin_replaces_articulo_nota_and_rows_while_not_validated(monkeypatch):
    for estado in ("BORRADOR", "ENVIADO", "COMPLETADO"):
        instancia = fila(estado)
        session = con_formulario(monkeypatch, instancia)
        resultado = formulario.guardar_formulario(
            session, "FCO-0001", articulo=" Billetera ", nota="  ", lineas=[linea("CUERO", cantidad=D("1.5"))], roles=ADMIN)
        assert (instancia.articulo, instancia.nota) == ("Billetera", None) and resultado["articulo"] == "Billetera"
        copiadas = list(session.add_all.call_args.args[0])
        assert [(c.seccion, c.orden, c.nombre, c.cantidad) for c in copiadas] == [("CONSUMO", 1, "CUERO", D("1.5"))]


def test_a_validated_form_cannot_be_saved_by_anyone_and_nothing_is_written(monkeypatch):
    instancia = fila("VALIDADO")
    session = con_formulario(monkeypatch, instancia)
    for roles in (ADMIN, TALLER, ADMIN | TALLER):
        with pytest.raises(Conflicto, match="validado"):
            formulario.guardar_formulario(session, "FCO-0001", articulo="X", nota=None, lineas=[], roles=roles)
    session.execute.assert_not_called()
    session.add_all.assert_not_called()


def test_a_taller_cannot_save_a_completed_form(monkeypatch):
    session = con_formulario(monkeypatch, fila("COMPLETADO"))
    with pytest.raises(Conflicto):
        formulario.guardar_formulario(session, "FCO-0001", articulo="Cartera Lucía", nota=None, lineas=[], roles=TALLER)
    session.execute.assert_not_called()


AHORA = datetime(2026, 11, 12, 15, 0, tzinfo=timezone.utc)


def test_each_transition_stamps_who_and_when_and_clears_nothing(monkeypatch):
    instancia = fila("BORRADOR")
    session = con_formulario(monkeypatch, instancia)
    formulario.cambiar_estado(session, "FCO-0001", "enviar", roles=ADMIN, quien="admin-1", ahora=AHORA)
    assert (instancia.estado, instancia.enviado_en) == ("ENVIADO", AHORA)
    formulario.cambiar_estado(session, "FCO-0001", "completar", roles=TALLER, quien="taller-1", ahora=AHORA)
    assert (instancia.estado, instancia.completado_por, instancia.completado_en) == ("COMPLETADO", "taller-1", AHORA)
    formulario.cambiar_estado(session, "FCO-0001", "devolver", roles=ADMIN, quien="admin-1", comentario=" Falta el flex ", ahora=AHORA)
    assert (instancia.estado, instancia.comentario_revision) == ("ENVIADO", "Falta el flex")
    formulario.cambiar_estado(session, "FCO-0001", "completar", roles=TALLER, quien="taller-2", ahora=AHORA)
    formulario.cambiar_estado(session, "FCO-0001", "validar", roles=ADMIN, quien="admin-9", ahora=AHORA)
    assert (instancia.estado, instancia.validado_por, instancia.validado_en) == ("VALIDADO", "admin-9", AHORA)
    assert instancia.comentario_revision == "Falta el flex" and instancia.completado_por == "taller-2"  # nothing cleared


@pytest.mark.parametrize("comentario", [None, "", "   "])
def test_returning_a_form_needs_a_review_comment_and_changes_nothing_without_it(monkeypatch, comentario):
    instancia = fila("COMPLETADO")
    session = con_formulario(monkeypatch, instancia)
    with pytest.raises(DatosInvalidos, match="comentario"):
        formulario.cambiar_estado(session, "FCO-0001", "devolver", roles=ADMIN, quien="a", comentario=comentario)
    assert instancia.estado == "COMPLETADO" and instancia.comentario_revision is None


def test_a_forbidden_transition_changes_nothing(monkeypatch):
    instancia = fila("ENVIADO")
    session = con_formulario(monkeypatch, instancia)
    with pytest.raises(Conflicto):
        formulario.cambiar_estado(session, "FCO-0001", "validar", roles=ADMIN, quien="a", ahora=AHORA)
    assert (instancia.estado, instancia.validado_por, instancia.validado_en) == ("ENVIADO", None, None)


def test_duplicate_is_admin_only_and_needs_an_articulo(monkeypatch):
    session = con_formulario(monkeypatch, fila("VALIDADO"))
    with pytest.raises(SinPermiso):
        formulario.duplicar_formulario(session, "FCO-0001", articulo="Nueva", quien="t", roles=TALLER)
    with pytest.raises(DatosInvalidos, match="artículo"):
        formulario.duplicar_formulario(session, "FCO-0001", articulo="  ", quien="a", roles=ADMIN)


# --- HTTP: gates, validation and error mapping (stubbed service layer) ------------------------------------------------

def cliente(role):
    app.dependency_overrides[get_session] = lambda: MagicMock()
    app.dependency_overrides[get_verifier] = lambda: (lambda request: Usuario(id="u-1", role=role))
    return TestClient(app, raise_server_exceptions=False)


def sin_servicio(monkeypatch):
    for nombre in ("crear_formulario", "listar_formularios", "obtener_formulario", "guardar_formulario", "cambiar_estado",
                   "duplicar_formulario"):
        monkeypatch.setattr(formulario, nombre, lambda *a, **k: pytest.fail("the service must not be called"))


RUTAS_SOLO_ADMIN = [
    ("POST", "/formularios", {"articulo": "A"}), ("POST", "/formularios/FCO-0001/enviar", None),
    ("POST", "/formularios/FCO-0001/devolver", {"comentario": "x"}), ("POST", "/formularios/FCO-0001/validar", None),
    ("POST", "/formularios/FCO-0001/duplicar", {"articulo": "A"}),
]
CUERPO_GUARDAR = {"articulo": "A", "lineas": [{"seccion": "CONSUMO", "nombre": "CUERO"}]}


@pytest.mark.parametrize("role", ["taller", "gerente", "otro", None])
@pytest.mark.parametrize("metodo, ruta, cuerpo", RUTAS_SOLO_ADMIN)
def test_the_admin_actions_refuse_taller_gerente_and_unknown_roles_before_the_service(monkeypatch, role, metodo, ruta, cuerpo):
    sin_servicio(monkeypatch)
    respuesta = cliente(role).request(metodo, ruta, json=cuerpo)
    assert respuesta.status_code == 403 and respuesta.json() == {"detail": "No tenés permiso para esta acción."}


@pytest.mark.parametrize("role", ["gerente", "otro", None])
@pytest.mark.parametrize("metodo, ruta, cuerpo", [
    ("PUT", "/formularios/FCO-0001", CUERPO_GUARDAR), ("POST", "/formularios/FCO-0001/completar", None)])
def test_gerente_cannot_edit_or_complete(monkeypatch, role, metodo, ruta, cuerpo):
    sin_servicio(monkeypatch)
    assert cliente(role).request(metodo, ruta, json=cuerpo).status_code == 403


@pytest.mark.parametrize("role", ["otro", None])
def test_unknown_roles_cannot_read_the_forms(monkeypatch, role):
    sin_servicio(monkeypatch)
    for ruta in ("/formularios", "/formularios/FCO-0001"):
        assert cliente(role).get(ruta).status_code == 403


def test_a_role_matrix_over_the_routes_that_pass_the_gate(monkeypatch):
    vistos = []
    monkeypatch.setattr(formulario, "listar_formularios", lambda s, **k: vistos.append(("listar", k["roles"])) or [])
    monkeypatch.setattr(formulario, "cambiar_estado", lambda s, codigo, accion, **k: vistos.append((accion, k["roles"])) or None)
    for role, ruta in (("admin", "/formularios"), ("taller", "/formularios")):
        assert cliente(role).get(ruta).status_code == 200
    assert vistos == [("listar", ADMIN), ("listar", TALLER)]  # the service gets the roles to filter
    assert cliente("gerente").get("/formularios").status_code == 403 and len(vistos) == 2  # closed to the gerente


def test_the_taller_hits_the_service_to_complete_with_its_own_roles_and_user(monkeypatch):
    visto = {}
    monkeypatch.setattr(formulario, "cambiar_estado", lambda s, codigo, accion, **k: visto.update(codigo=codigo, accion=accion, **k))
    cliente("taller").post("/formularios/FCO-0007/completar")
    assert visto == {"codigo": "FCO-0007", "accion": "completar", "roles": TALLER, "quien": "u-1"}


def test_a_negative_quantity_is_a_422_and_the_service_is_not_called(monkeypatch):
    sin_servicio(monkeypatch)
    cuerpo = {"articulo": "A", "lineas": [{"seccion": "CONSUMO", "nombre": "CUERO", "cantidad": "-1"}]}
    assert cliente("admin").put("/formularios/FCO-0001", json=cuerpo).status_code == 422


@pytest.mark.parametrize("cuerpo", [
    {"articulo": "A", "lineas": [{"seccion": "OTRA", "nombre": "X"}]},
    {"articulo": "A", "lineas": [{"seccion": "CONSUMO", "nombre": ""}]},
    {"articulo": "A", "lineas": [{"seccion": "CONSUMO", "nombre": "X", "cantidad": "abc"}]},
    {"articulo": "A", "lineas": [{"seccion": "CONSUMO", "nombre": "X", "cantidad": "1.0000001"}]},  # more than 6 decimals
    {"articulo": "A", "lineas": [{"seccion": "CONSUMO", "nombre": "X", "orden": 3}]},  # the order is the list order
    {"articulo": "A", "lineas": [{"seccion": "CONSUMO", "nombre": "X", "total": "1"}]},  # nothing calculated is accepted
    {"articulo": "", "lineas": []}, {"articulo": "A"}, {"articulo": "A", "lineas": [], "estado": "VALIDADO"},
    {"articulo": "A", "lineas": [], "producto": "PRD-0001"},  # producto / taller are fixed at creation
])
def test_invalid_bodies_are_422_without_calling_the_service(monkeypatch, cuerpo):
    sin_servicio(monkeypatch)
    assert cliente("admin").put("/formularios/FCO-0001", json=cuerpo).status_code == 422


def test_quantities_travel_as_exact_decimals_and_come_back_as_strings(monkeypatch):
    visto = {}
    salida = {
        "codigo": "FCO-0001", "articulo": "A", "estado": "ENVIADO", "producto": None, "modelo": None, "taller": None, "creado_por": "u",
        "created_at": AHORA, "enviado_en": AHORA, "completado_en": None, "validado_en": None, "nota": None,
        "comentario_revision": None, "completado_por": None, "validado_por": None,
        "lineas": [{"seccion": "CONSUMO", "orden": 1, "nombre": "CUERO", "cantidad": D("0.250000"), "comentario": None}],
    }
    monkeypatch.setattr(formulario, "guardar_formulario", lambda s, codigo, **k: visto.update(k) or salida)
    cuerpo = {"articulo": "A", "lineas": [{"seccion": "CONSUMO", "nombre": "CUERO", "cantidad": "0.25"}]}
    respuesta = cliente("taller").put("/formularios/FCO-0001", json=cuerpo)
    assert respuesta.status_code == 200, respuesta.text
    assert visto["lineas"][0]["cantidad"] == D("0.25") and visto["roles"] == TALLER
    assert respuesta.json()["lineas"][0]["cantidad"] == "0.250000" and "total" not in str(respuesta.json()).lower()


@pytest.mark.parametrize("error, estado", [
    (Conflicto("x"), 409), (NoEncontrado("x"), 404), (DatosInvalidos("x"), 422), (SinPermiso("x"), 403)])
def test_the_service_errors_map_to_their_http_codes_with_the_message(monkeypatch, error, estado):
    def falla(*a, **k):
        raise error
    monkeypatch.setattr(formulario, "cambiar_estado", falla)
    respuesta = cliente("admin").post("/formularios/FCO-0001/validar")
    assert respuesta.status_code == estado and respuesta.json() == {"detail": "x"}


def test_the_list_filter_only_takes_the_four_states(monkeypatch):
    sin_servicio(monkeypatch)
    assert cliente("admin").get("/formularios", params={"estado": "CERRADO"}).status_code == 422


def test_the_list_passes_the_producto_filter_to_the_service(monkeypatch):
    vistos = []
    monkeypatch.setattr(formulario, "listar_formularios", lambda s, **k: vistos.append(k) or [])
    assert cliente("admin").get("/formularios", params={"producto": "PRD-0001", "estado": "VALIDADO"}).status_code == 200
    assert cliente("admin").get("/formularios").status_code == 200
    assert [(k["producto"], k["estado"]) for k in vistos] == [("PRD-0001", "VALIDADO"), (None, None)]


# --- Model and migration ------------------------------------------------------------------------------------------

def test_the_models_follow_the_conventions_of_the_schema():
    cabecera, linea_tabla = FormularioConsumo.__table__, FormularioConsumoLinea.__table__
    assert cabecera.schema == linea_tabla.schema == "costos"
    assert cabecera.c.codigo.unique and not cabecera.c.articulo.nullable and not cabecera.c.estado.nullable
    for nombre in ("producto_id", "taller_id", "comentario_revision", "nota", "enviado_en", "completado_por", "completado_en",
                   "validado_por", "validado_en"):
        assert cabecera.c[nombre].nullable, nombre
    for nombre in ("enviado_en", "completado_en", "validado_en"):
        assert cabecera.c[nombre].type.timezone
    assert (linea_tabla.c.cantidad.type.precision, linea_tabla.c.cantidad.type.scale) == (12, 6)
    assert linea_tabla.c.cantidad.nullable and not linea_tabla.c.nombre.nullable and linea_tabla.c.comentario.nullable
    checks = {c.name: str(c.sqltext) for t in (cabecera, linea_tabla) for c in t.constraints if isinstance(c, CheckConstraint)}
    assert checks["ck_formulario_consumo_estado"] == "estado IN ('BORRADOR','ENVIADO','COMPLETADO','VALIDADO')"
    assert checks["ck_formulario_consumo_linea_seccion"] == "seccion IN ('CONSUMO','HERRAJE')"
    assert checks["ck_formulario_consumo_linea_cantidad_no_negativa"] == "cantidad IS NULL OR cantidad >= 0"
    unicas = [tuple(c.columns.keys()) for c in linea_tabla.constraints if isinstance(c, UniqueConstraint)]
    assert ("formulario_id", "seccion", "orden") in unicas
    assert {"formulario_consumo", "formulario_consumo_linea"} <= {t.name for t in Base.metadata.tables.values()}


def test_revision_0017_adds_the_nullable_model_link_and_the_downgrade_drops_it(monkeypatch):
    revision = runpy.run_path(str(Path(__file__).parents[1] / "migrations" / "versions" / "0017_formulario_modelo.py"))
    assert revision["revision"] == "0017_formulario_modelo" and revision["down_revision"] == "0016_formulario_consumo"
    assert FormularioConsumo.__table__.c.modelo_id.nullable


def test_revision_0016_creates_the_two_tables_and_the_downgrade_drops_the_child_first(monkeypatch):
    from test_migrations import load_revision
    operations, base = load_revision(monkeypatch, "0003_der_v3.py")
    base["upgrade"]()
    revision = runpy.run_path(str(Path(__file__).parents[1] / "migrations" / "versions" / "0016_formulario_consumo.py"))
    assert revision["revision"] == "0016_formulario_consumo" and revision["down_revision"] == "0015_precio_venta_margen"
    revision["upgrade"]()
    assert {"costos.formulario_consumo", "costos.formulario_consumo_linea"} <= set(operations.metadata.tables)
    operations.dropped.clear()
    revision["downgrade"]()
    assert operations.dropped == ["formulario_consumo_linea", "formulario_consumo"]
    assert "lost" in revision["__doc__"]


# --- PostgreSQL (skipped without TEST_DATABASE_URL) -------------------------------------------------------------------

from test_costos_fijos_correccion_integration import api  # noqa: E402,F401  (fixture; its client also carries `.session`)


def como(role, usuario="usuario-de-prueba"):
    app.dependency_overrides[get_verifier] = lambda: (lambda request: Usuario(id=usuario, role=role))


def crear(api, articulo="Cartera Lucía", **extra):
    como("admin", "admin-1")
    respuesta = api.post("/formularios", json={"articulo": articulo, **extra})
    assert respuesta.status_code == 201, respuesta.text
    return respuesta.json()


def cuerpo_de(formulario_json, **cambios):
    """What the front sends back: the sheet as read, without the computed `orden`."""
    return {
        "articulo": formulario_json["articulo"], "nota": formulario_json["nota"],
        "lineas": [{k: l[k] for k in ("seccion", "nombre", "cantidad", "comentario")} for l in formulario_json["lineas"]],
        **cambios,
    }


def test_pg_create_returns_a_borrador_with_the_preloaded_rows_and_the_next_code(api):
    primero = crear(api)
    assert primero["estado"] == "BORRADOR" and primero["codigo"].startswith("FCO-") and primero["creado_por"] == "admin-1"
    assert [(l["seccion"], l["orden"], l["nombre"]) for l in primero["lineas"]] == (
        [("CONSUMO", i, n) for i, n in enumerate(CONSUMOS_DE_LA_HOJA, 1)]
        + [("HERRAJE", i, n) for i, n in enumerate(HERRAJES_DE_LA_HOJA, 1)])
    assert all(l["cantidad"] is None and l["comentario"] is None for l in primero["lineas"])
    assert (primero["producto"], primero["taller"], primero["enviado_en"], primero["validado_por"]) == (None, None, None, None)
    segundo = crear(api, "Billetera")
    assert int(segundo["codigo"][4:]) == int(primero["codigo"][4:]) + 1


def test_pg_create_links_an_existing_product_and_workshop_and_refuses_unknown_ones(api):
    como("admin")
    taller = api.get("/talleres").json()[0]["codigo"]
    creado = crear(api, taller=taller)
    assert creado["taller"] == taller
    for campo, valor in (("taller", "TAL-9999"), ("producto", "PRD-9999")):
        respuesta = api.post("/formularios", json={"articulo": "X", campo: valor})
        assert respuesta.status_code == 422 and valor in respuesta.json()["detail"]


def test_pg_full_flow_borrador_enviado_completado_devuelto_completado_validado(api):
    creado = crear(api)
    codigo = creado["codigo"]
    como("taller")
    assert api.get(f"/formularios/{codigo}").status_code == 404  # BORRADOR is not visible to the taller
    como("admin", "admin-1")
    enviado = api.post(f"/formularios/{codigo}/enviar").json()
    assert enviado["estado"] == "ENVIADO" and enviado["enviado_en"] is not None
    como("taller", "taller-1")
    visto = api.get(f"/formularios/{codigo}").json()
    lineas = [dict(l) for l in cuerpo_de(visto)["lineas"]]
    lineas[0]["cantidad"], lineas[0]["comentario"] = "0.250000", "con desperdicio"
    lineas.append({"seccion": "HERRAJE", "nombre": "BOTÓN A MEDIDA", "cantidad": "2", "comentario": None})
    guardado = api.put(f"/formularios/{codigo}", json={**cuerpo_de(visto), "lineas": lineas})
    assert guardado.status_code == 200, guardado.text
    assert guardado.json()["lineas"][0]["cantidad"] == "0.250000"
    assert guardado.json()["lineas"][-1]["nombre"] == "BOTÓN A MEDIDA" and guardado.json()["lineas"][-1]["orden"] == 17
    assert api.post(f"/formularios/{codigo}/validar").status_code == 403  # the taller never validates
    completado = api.post(f"/formularios/{codigo}/completar").json()
    assert (completado["estado"], completado["completado_por"]) == ("COMPLETADO", "taller-1")
    assert api.put(f"/formularios/{codigo}", json=cuerpo_de(completado)).status_code == 409  # waits for the review
    como("admin", "admin-1")
    assert api.post(f"/formularios/{codigo}/devolver", json={}).status_code == 422
    devuelto = api.post(f"/formularios/{codigo}/devolver", json={"comentario": "Falta el flex"}).json()
    assert (devuelto["estado"], devuelto["comentario_revision"]) == ("ENVIADO", "Falta el flex")
    como("taller", "taller-1")
    assert api.post(f"/formularios/{codigo}/completar").json()["estado"] == "COMPLETADO"
    como("admin", "admin-1")
    validado = api.post(f"/formularios/{codigo}/validar").json()
    assert (validado["estado"], validado["validado_por"]) == ("VALIDADO", "admin-1") and validado["validado_en"] is not None
    assert validado["comentario_revision"] == "Falta el flex" and validado["completado_por"] == "taller-1"  # nothing cleared
    for ruta in ("enviar", "completar", "validar"):
        assert api.post(f"/formularios/{codigo}/{ruta}").status_code == 409
    assert api.post(f"/formularios/{codigo}/devolver", json={"comentario": "x"}).status_code == 409
    inmutable = api.put(f"/formularios/{codigo}", json=cuerpo_de(validado, articulo="Otro"))
    assert inmutable.status_code == 409 and "duplicalo" in inmutable.json()["detail"]
    assert api.get(f"/formularios/{codigo}").json()["articulo"] == "Cartera Lucía"
    como("taller")
    assert api.get(f"/formularios/{codigo}").status_code == 404  # VALIDADO leaves the taller's view


def test_pg_the_admin_replaces_articulo_nota_and_the_full_set_of_rows(api):
    creado = crear(api)
    cuerpo = {"articulo": "Cartera Lucía Mini", "nota": "primer prototipo", "lineas": [
        {"seccion": "HERRAJE", "nombre": "CIERRE N5", "cantidad": "1", "comentario": None},
        {"seccion": "CONSUMO", "nombre": "CUERO CHIVO", "cantidad": "0.5", "comentario": "c"},
        {"seccion": "CONSUMO", "nombre": "FORRO", "cantidad": None, "comentario": None}]}
    guardado = api.put(f"/formularios/{creado['codigo']}", json=cuerpo).json()
    assert [(l["seccion"], l["orden"], l["nombre"]) for l in guardado["lineas"]] == [
        ("CONSUMO", 1, "CUERO CHIVO"), ("CONSUMO", 2, "FORRO"), ("HERRAJE", 1, "CIERRE N5")]
    assert (guardado["articulo"], guardado["nota"], guardado["estado"]) == ("Cartera Lucía Mini", "primer prototipo", "BORRADOR")
    assert api.get(f"/formularios/{creado['codigo']}").json() == guardado
    vacio = api.put(f"/formularios/{creado['codigo']}", json={"articulo": "Cartera Lucía Mini", "lineas": []}).json()
    assert vacio["lineas"] == [] and vacio["nota"] is None


def test_pg_the_taller_cannot_change_the_articulo_or_the_nota(api):
    creado = crear(api, nota="del admin")
    api.post(f"/formularios/{creado['codigo']}/enviar")
    como("taller")
    visto = api.get(f"/formularios/{creado['codigo']}").json()
    for cambio in ({"articulo": "Otro"}, {"nota": "otra"}, {"nota": None}):
        respuesta = api.put(f"/formularios/{creado['codigo']}", json=cuerpo_de(visto, **cambio))
        assert respuesta.status_code == 403, cambio
    assert api.get(f"/formularios/{creado['codigo']}").json() == visto


def test_pg_a_rejected_edit_leaves_the_stored_rows_untouched(api):
    creado = crear(api)
    malo = api.put(f"/formularios/{creado['codigo']}", json={
        "articulo": "A", "lineas": [{"seccion": "CONSUMO", "nombre": "CUERO", "cantidad": "-3"}]})
    assert malo.status_code == 422
    assert api.get(f"/formularios/{creado['codigo']}").json() == creado


def test_pg_a_forbidden_transition_is_a_409_and_changes_nothing(api):
    creado = crear(api)
    for ruta, cuerpo in (("completar", None), ("validar", None), ("devolver", {"comentario": "x"})):
        respuesta = api.post(f"/formularios/{creado['codigo']}/{ruta}", json=cuerpo)
        assert respuesta.status_code == 409 and "borrador" in respuesta.json()["detail"], ruta
    assert api.get(f"/formularios/{creado['codigo']}").json() == creado
    assert api.post("/formularios/FCO-9999/enviar").status_code == 404


def test_pg_duplicate_copies_names_quantities_and_comments_of_any_state_into_a_new_borrador(api):
    origen = crear(api, nota="no se copia")
    lineas = [{"seccion": "CONSUMO", "nombre": "CUERO", "cantidad": "1.5", "comentario": "ok"},
              {"seccion": "CONSUMO", "nombre": "SIN CANTIDAD", "cantidad": None, "comentario": None},
              {"seccion": "HERRAJE", "nombre": "HEBILLA", "cantidad": "0", "comentario": None}]
    api.put(f"/formularios/{origen['codigo']}", json={"articulo": origen["articulo"], "nota": "no se copia", "lineas": lineas})
    api.post(f"/formularios/{origen['codigo']}/enviar")
    como("taller")
    api.post(f"/formularios/{origen['codigo']}/completar")
    como("admin", "admin-2")
    api.post(f"/formularios/{origen['codigo']}/validar")
    copia = api.post(f"/formularios/{origen['codigo']}/duplicar", json={"articulo": "Cartera Lucía Grande"})
    assert copia.status_code == 201, copia.text
    copia = copia.json()
    assert copia["codigo"] != origen["codigo"] and copia["estado"] == "BORRADOR" and copia["articulo"] == "Cartera Lucía Grande"
    assert copia["creado_por"] == "admin-2" and copia["nota"] is None and copia["validado_por"] is None
    assert [(l["seccion"], l["orden"], l["nombre"], l["cantidad"], l["comentario"]) for l in copia["lineas"]] == [
        ("CONSUMO", 1, "CUERO", "1.500000", "ok"), ("CONSUMO", 2, "SIN CANTIDAD", None, None), ("HERRAJE", 1, "HEBILLA", "0.000000", None)]
    assert api.get(f"/formularios/{origen['codigo']}").json()["estado"] == "VALIDADO"  # the original is untouched
    api.put(f"/formularios/{copia['codigo']}", json={"articulo": "Cartera Lucía Grande", "lineas": []})
    assert len(api.get(f"/formularios/{origen['codigo']}").json()["lineas"]) == 3  # independent sheets
    como("taller")
    assert api.post(f"/formularios/{origen['codigo']}/duplicar", json={"articulo": "X"}).status_code == 403


def test_pg_list_search_and_what_each_role_sees(api):
    uno, dos, tres = crear(api, "Mochila Aventura"), crear(api, "Billetera Zeta"), crear(api, "Cartera 100%")
    api.post(f"/formularios/{dos['codigo']}/enviar")
    api.post(f"/formularios/{tres['codigo']}/enviar")
    como("taller")
    api.post(f"/formularios/{tres['codigo']}/completar")
    como("admin")
    todos = {f["codigo"]: f["estado"] for f in api.get("/formularios").json()}
    assert todos[uno["codigo"]] == "BORRADOR" and todos[dos["codigo"]] == "ENVIADO" and todos[tres["codigo"]] == "COMPLETADO"
    assert list(todos)[:3] == [tres["codigo"], dos["codigo"], uno["codigo"]]  # newest first
    assert [f["codigo"] for f in api.get("/formularios", params={"q": "billetera"}).json()] == [dos["codigo"]]
    assert [f["codigo"] for f in api.get("/formularios", params={"q": "100%"}).json()] == [tres["codigo"]]  # % is not a wildcard
    assert [f["codigo"] for f in api.get("/formularios", params={"q": uno["codigo"].lower()}).json()] == [uno["codigo"]]
    assert [f["codigo"] for f in api.get("/formularios", params={"estado": "ENVIADO", "q": "zeta"}).json()] == [dos["codigo"]]
    como("gerente")
    assert api.get("/formularios").status_code == 403  # the module is closed to the gerente
    assert api.get(f"/formularios/{uno['codigo']}").status_code == 403
    assert api.put(f"/formularios/{uno['codigo']}", json=cuerpo_de(uno)).status_code == 403
    como("taller")
    visibles = {f["codigo"]: f["estado"] for f in api.get("/formularios").json()}
    assert uno["codigo"] not in visibles and visibles[dos["codigo"]] == "ENVIADO" and visibles[tres["codigo"]] == "COMPLETADO"
    assert set(visibles.values()) <= {"ENVIADO", "COMPLETADO"}
    assert api.get("/formularios", params={"estado": "BORRADOR"}).json() == []
    assert api.get(f"/formularios/{uno['codigo']}").status_code == 404


def test_pg_the_database_rejects_negative_quantities_duplicate_rows_and_unknown_states(api):
    from sqlalchemy import select
    creado = crear(api)
    sesion = api.session
    fila_id = sesion.scalar(select(FormularioConsumo.id).where(FormularioConsumo.codigo == creado["codigo"]))
    for fila_mala in (
        FormularioConsumoLinea(formulario_id=fila_id, seccion="CONSUMO", orden=99, nombre="X", cantidad=D("-1")),
        FormularioConsumoLinea(formulario_id=fila_id, seccion="OTRA", orden=99, nombre="X"),
        FormularioConsumoLinea(formulario_id=fila_id, seccion="CONSUMO", orden=1, nombre="REPETIDA"),
    ):
        with pytest.raises(IntegrityError):
            with sesion.begin_nested():
                sesion.add(fila_mala)
                sesion.flush()
    with pytest.raises(IntegrityError):
        with sesion.begin_nested():
            sesion.add(FormularioConsumo(codigo="FCO-8888", articulo="X", estado="CERRADO", creado_por="u"))
            sesion.flush()


def test_pg_a_form_written_through_the_real_session_is_committed(local_postgres, monkeypatch):
    """Every write must survive the request: `get_session` rolls back whatever a service did not commit."""
    from sqlalchemy import text

    monkeypatch.setenv("DATABASE_URL", local_postgres.url.render_as_string(hide_password=False))
    como("admin", "admin-1")
    with TestClient(app) as cliente_real:
        creado = cliente_real.post("/formularios", json={"articulo": "Persistencia"})
        assert creado.status_code == 201
        codigo = creado.json()["codigo"]
        assert cliente_real.get(f"/formularios/{codigo}").status_code == 200
        leido = cliente_real.get(f"/formularios/{codigo}").json()
        guardado = cliente_real.put(f"/formularios/{codigo}", json=cuerpo_de(leido, nota="guardada"))
        assert guardado.status_code == 200
        assert cliente_real.get(f"/formularios/{codigo}").json()["nota"] == "guardada"
        assert cliente_real.post(f"/formularios/{codigo}/enviar").json()["estado"] == "ENVIADO"
        copia = cliente_real.post(f"/formularios/{codigo}/duplicar", json={"articulo": "Persistencia 2"})
        assert copia.status_code == 201
    with local_postgres.connect() as conexion:
        estado = conexion.execute(
            text("select estado from costos.formulario_consumo where codigo = :c"), {"c": codigo}).scalar()
        assert estado == "ENVIADO"
        conexion.execute(text("delete from costos.formulario_consumo_linea"))
        conexion.execute(text("delete from costos.formulario_consumo"))
        conexion.commit()


# --- Alta rápida (S1-S4 of odd/tasks/producto-alta-simple.md) ---------------------------------------------------------

def test_names_are_normalized_to_single_spaces_and_capitals_and_an_empty_one_is_refused():
    assert formulario.normalizar_nombre("  cartera   lucía chica ") == "CARTERA LUCÍA CHICA"
    for vacio in ("", "   ", None):
        with pytest.raises(DatosInvalidos):
            formulario.normalizar_nombre(vacio)


def alta(api, nombre="cartera  lucía"):
    como("admin", "admin-1")
    return api.post("/productos/nuevo", json={"nombre": nombre})


def test_pg_the_quick_create_makes_a_model_and_a_form_already_sent_but_no_product(api):
    respuesta = alta(api)
    assert respuesta.status_code == 201, respuesta.text
    datos = respuesta.json()
    assert datos["nombre"] == "CARTERA LUCÍA" and datos["modelo"].startswith("MOD-") and "producto" not in datos
    form = api.get(f"/formularios/{datos['formulario']}").json()
    assert (form["estado"], form["articulo"], form["modelo"], form["producto"]) == (
        "ENVIADO", "CARTERA LUCÍA", datos["modelo"], None)
    assert form["enviado_en"] is not None and len(form["lineas"]) == 30
    assert api.get(f"/modelos/{datos['modelo']}").json()["nombre_del_modelo"] == "CARTERA LUCÍA"
    como("taller")
    assert api.get(f"/formularios/{datos['formulario']}").status_code == 200  # the taller already sees it


def test_pg_the_quick_create_refuses_a_repeated_name_and_leaves_nothing_behind(api):
    assert alta(api, "Zz Billetera de prueba").status_code == 201
    antes = len(api.get("/formularios").json())
    assert alta(api, " zz billetera  de PRUEBA ").status_code == 409
    assert alta(api, "   ").status_code == 422
    assert len(api.get("/formularios").json()) == antes


def test_pg_only_the_admin_can_use_the_quick_create(api):
    for rol in ("taller", "gerente"):
        como(rol)
        assert api.post("/productos/nuevo", json={"nombre": "X"}).status_code == 403


def test_pg_validating_copies_the_measures_to_the_model_once(api):
    datos = alta(api, "Zz Mochila de prueba").json()
    codigo = datos["formulario"]
    como("taller")
    form = api.get(f"/formularios/{codigo}").json()
    for l in form["lineas"]:
        if l["nombre"] == "CUERO":
            l["cantidad"] = "0.5"
        if l["nombre"] == "FLEX":
            l["cantidad"] = "0.25"
    assert api.put(f"/formularios/{codigo}", json=cuerpo_de(form)).status_code == 200
    assert api.post(f"/formularios/{codigo}/completar").status_code == 200
    como("admin", "admin-1")
    assert api.post(f"/formularios/{codigo}/validar").status_code == 200
    modelo = api.get(f"/modelos/{datos['modelo']}").json()
    assert (D(modelo["cuero_m2_por_unidad"]), D(modelo["flex_m2_por_unidad"])) == (D("0.5"), D("0.25"))
    assert modelo["goma_eva_m2_por_unidad"] is None  # blank row = missing data, not "no lleva"
    assert (modelo["validado"], modelo["origen_de_los_consumos"]) == (True, "MEDIDO")
