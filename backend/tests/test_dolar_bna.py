"""BNA dollar scraping: pure parser, download wrapper, service (idempotent) and endpoint. No real network."""

from datetime import date
from decimal import Decimal as D
from pathlib import Path
from unittest.mock import MagicMock

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend import actualizar_dolar, dolar_bna, servicios
from backend.auth import Usuario, get_verifier
from backend.database import get_session
from backend.dolar_bna import BnaError, CotizacionBna, descargar_bna, parse_bna
from backend.main import app
from backend.models import TipoCambio

HTML = (Path(__file__).parent / "fixtures" / "bna_personas.html").read_text(encoding="utf-8")


def pagina(fecha="28/10/2026", fila='<td class="tit">Dolar U.S.A</td><td>1510,00</td><td>1560,00</td>'):
    return (
        '<div class="tab-content"><div class="tab-pane fade in active" id="billetes">'
        f'<table class="table cotizacion"><thead><tr><th class="fechaCot">{fecha}</th><th>Compra</th><th>Venta</th></tr></thead>'
        f"<tbody><tr>{fila}</tr></tbody></table></div></div>"
    )


@pytest.fixture(autouse=True)
def limpio(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    yield
    app.dependency_overrides.clear()


# --- parse_bna -------------------------------------------------------------------------------------------

def test_parse_the_real_fixture():
    cotizacion = parse_bna(HTML)
    assert cotizacion == CotizacionBna(fecha=date(2026, 10, 28), compra=D("1510.00"), venta=D("1560.00"))
    assert isinstance(cotizacion.venta, D) and isinstance(cotizacion.compra, D)


def test_parse_ignores_the_divisas_pane():
    # the divisas pane of the fixture says 27/10/2026 and 1538.0000: only `billetes` counts
    assert parse_bna(HTML).fecha == date(2026, 10, 28)


@pytest.mark.parametrize("compra, venta, esperado_compra, esperado_venta", [
    ("1.510,25", "1.560,50", D("1510.25"), D("1560.50")),
    ("1510,00", "1560,00", D("1510.00"), D("1560.00")),
    ("1510", "1560", D("1510"), D("1560")),
    ("1510.5", "1560.75", D("1510.5"), D("1560.75")),
    ("1.510", "1.560", D("1510"), D("1560")),
    (" 1510,00 ", "\n1560,00\n", D("1510.00"), D("1560.00")),
])
def test_parse_number_formats(compra, venta, esperado_compra, esperado_venta):
    cotizacion = parse_bna(pagina(fila=f'<td class="tit">Dolar U.S.A</td><td>{compra}</td><td>{venta}</td>'))
    assert (cotizacion.compra, cotizacion.venta) == (esperado_compra, esperado_venta)


def test_parse_finds_the_dollar_row_among_others():
    fila = ('<td class="tit">Euro</td><td>1680,00</td><td>1780,00</td></tr><tr>'
            '<td class="tit"> Dolar  U.S.A </td><td>1510,00</td><td>1560,00</td>')
    assert parse_bna(pagina(fila=fila)).venta == D("1560.00")


@pytest.mark.parametrize("html", [
    "",
    "<html><body><p>mantenimiento</p></body></html>",
    '<div id="billetes"><p>sin tabla</p></div>',
    '<div id="divisas"><table><tr><th class="fechaCot">28/10/2026</th></tr>'
    '<tr><td>Dolar U.S.A</td><td>1510,00</td><td>1560,00</td></tr></table></div>',
    pagina(fila='<td class="tit">Euro</td><td>1680,00</td><td>1780,00</td>'),
    pagina(fila='<td class="tit">Dolar U.S.A</td><td>1510,00</td>'),
    '<div id="billetes"><table><tr><td>Dolar U.S.A</td><td>1510,00</td><td>1560,00</td></tr></table></div>',
])
def test_parse_without_the_expected_structure_raises(html):
    with pytest.raises(BnaError) as error:
        parse_bna(html)
    assert str(error.value) and "<" not in str(error.value)


@pytest.mark.parametrize("fecha", ["", "31/02/2026", "2026-10-28", "28/13/2026", "ayer"])
def test_parse_with_a_bad_date_raises(fecha):
    with pytest.raises(BnaError):
        parse_bna(pagina(fecha=fecha))


@pytest.mark.parametrize("compra, venta", [
    ("1510,00", "0,00"), ("1510,00", "-5"), ("0", "1560,00"), ("abc", "1560,00"), ("1510,00", ""),
    ("1510,00", "NaN"), ("1510,00", "Infinity"), ("1510,00", "1e9"), ("1,5,0", "1560,00"),
])
def test_parse_with_values_that_are_not_positive_numbers_raises(compra, venta):
    with pytest.raises(BnaError):
        parse_bna(pagina(fila=f'<td class="tit">Dolar U.S.A</td><td>{compra}</td><td>{venta}</td>'))


# --- descargar_bna ---------------------------------------------------------------------------------------

def cliente_con(handler):
    return httpx.Client(transport=httpx.MockTransport(handler))


def test_download_returns_the_text_and_sends_a_user_agent():
    vistos = []

    def handler(request):
        vistos.append(request)
        return httpx.Response(200, text=HTML)

    assert descargar_bna(cliente_con(handler)) == HTML
    assert str(vistos[0].url) == "https://www.bna.com.ar/Personas"
    assert vistos[0].headers["user-agent"]


@pytest.mark.parametrize("falla", [
    httpx.ConnectError("secreto interno"), httpx.ReadTimeout("secreto interno"), httpx.RemoteProtocolError("secreto interno"),
])
def test_download_network_failures_become_a_safe_error(falla):
    def handler(request):
        raise falla

    with pytest.raises(BnaError) as error:
        descargar_bna(cliente_con(handler))
    assert "secreto" not in str(error.value) and "bna.com.ar" not in str(error.value).replace("Banco Nación", "")


@pytest.mark.parametrize("estado", [403, 404, 500, 503])
def test_download_http_errors_become_a_safe_error(estado):
    with pytest.raises(BnaError) as error:
        descargar_bna(cliente_con(lambda request: httpx.Response(estado, text="<h1>detalle interno</h1>")))
    assert "detalle interno" not in str(error.value)


# --- service ---------------------------------------------------------------------------------------------

def test_service_maps_a_parser_error_to_the_external_source_error():
    with pytest.raises(servicios.FuenteNoDisponible) as error:
        servicios.actualizar_dolar_bna(MagicMock(), html="<html>cambió la página</html>")
    assert "cambió la página" not in str(error.value)


def test_service_maps_a_download_error_to_the_external_source_error(monkeypatch):
    def caido(client=None):
        raise BnaError("No se pudo consultar al Banco Nación.")

    monkeypatch.setattr(dolar_bna, "descargar_bna", caido)
    session = MagicMock()
    with pytest.raises(servicios.FuenteNoDisponible, match="No se pudo consultar"):
        servicios.actualizar_dolar_bna(session)
    session.add.assert_not_called()
    session.commit.assert_not_called()


def test_service_downloads_when_no_html_is_injected(monkeypatch):
    monkeypatch.setattr(dolar_bna, "descargar_bna", lambda client=None: HTML)
    session = MagicMock()
    session.scalars.return_value.first.return_value = None
    resultado = servicios.actualizar_dolar_bna(session)
    assert resultado["estado"] == "creado" and resultado["ars_por_usd"] == D("1560.00")


@pytest.fixture
def sesion(local_postgres):
    connection = local_postgres.connect()
    outer = connection.begin()
    session = Session(bind=connection, join_transaction_mode="create_savepoint")
    try:
        yield session
    finally:
        session.close()
        outer.rollback()
        connection.close()


def filas_bna(session):
    return session.scalar(select(func.count()).select_from(TipoCambio).where(TipoCambio.fuente == "BNA"))


def test_service_creates_once_then_reports_it_already_existed(sesion):
    antes = filas_bna(sesion)
    primero = servicios.actualizar_dolar_bna(sesion, html=HTML)
    assert primero["estado"] == "creado"
    assert primero["fecha"] == date(2026, 10, 28) and primero["ars_por_usd"] == D("1560.00")
    assert (primero["fuente"], primero["tipo"]) == ("BNA", "VENDEDOR")
    assert primero["nota"] == "Scrapeado de bna.com.ar"
    assert filas_bna(sesion) == antes + 1

    segundo = servicios.actualizar_dolar_bna(sesion, html=HTML)
    assert segundo["estado"] == "ya_existia"
    assert segundo["fecha"] == date(2026, 10, 28) and segundo["ars_por_usd"] == D("1560.00")
    assert filas_bna(sesion) == antes + 1


def test_service_never_updates_an_existing_row(sesion):
    servicios.actualizar_dolar_bna(sesion, html=HTML)
    cambiado = pagina(fila='<td class="tit">Dolar U.S.A</td><td>1500,00</td><td>1599,00</td>')
    resultado = servicios.actualizar_dolar_bna(sesion, html=cambiado)
    assert resultado["estado"] == "ya_existia" and resultado["ars_por_usd"] == D("1560.00")
    fila = sesion.scalars(select(TipoCambio).where(TipoCambio.fuente == "BNA")).one()
    assert fila.ars_por_usd == D("1560.00")


def test_service_does_not_clash_with_a_manual_dollar_of_the_same_day(sesion):
    servicios.crear_dolar(sesion, fecha=date(2026, 10, 28), ars_por_usd=D("1555"), fuente="MANUAL", tipo="VENDEDOR")
    assert servicios.actualizar_dolar_bna(sesion, html=HTML)["estado"] == "creado"


# --- endpoint --------------------------------------------------------------------------------------------

def con_usuario(role="cotizador"):
    session = MagicMock()
    app.dependency_overrides[get_session] = lambda: session
    app.dependency_overrides[get_verifier] = lambda: (lambda request: Usuario(id="usuario-de-prueba", role=role))
    return TestClient(app), session


@pytest.mark.parametrize("role", ["consulta", None, "otro"])
def test_the_endpoint_requires_a_writing_role(monkeypatch, role):
    client, session = con_usuario(role)
    monkeypatch.setattr(servicios, "actualizar_dolar_bna", lambda *a, **k: pytest.fail("the service must not be called"))
    response = client.post("/dolar/actualizar-bna")
    assert response.status_code == 403
    assert response.json() == {"detail": "No tenés permiso para esta acción."}
    session.commit.assert_not_called()


def test_the_endpoint_needs_a_session():
    app.dependency_overrides[get_verifier] = lambda: (lambda request: None)
    assert TestClient(app).post("/dolar/actualizar-bna").status_code == 401


@pytest.mark.parametrize("role", ["admin", "cotizador"])
def test_the_endpoint_answers_the_service_result(monkeypatch, role):
    client, _ = con_usuario(role)
    visto = {}

    def actualizar(session, *, html=None):
        visto["html"] = html
        return {"estado": "creado", "fecha": date(2026, 10, 28), "ars_por_usd": D("1560.00"), "fuente": "BNA",
                "tipo": "VENDEDOR", "nota": "Scrapeado de bna.com.ar"}

    monkeypatch.setattr(servicios, "actualizar_dolar_bna", actualizar)
    response = client.post("/dolar/actualizar-bna")
    assert response.status_code == 200
    assert response.json() == {"estado": "creado", "fecha": "2026-10-28", "ars_por_usd": "1560.00", "fuente": "BNA",
                               "tipo": "VENDEDOR", "nota": "Scrapeado de bna.com.ar"}
    assert visto["html"] is None  # the client never supplies the page


def test_the_endpoint_ignores_a_body_with_html(monkeypatch):
    client, _ = con_usuario()
    visto = {}
    monkeypatch.setattr(servicios, "actualizar_dolar_bna", lambda session, *, html=None: visto.update(html=html) or {
        "estado": "ya_existia", "fecha": date(2026, 10, 28), "ars_por_usd": D("1560"), "fuente": "BNA",
        "tipo": "VENDEDOR", "nota": None})
    assert client.post("/dolar/actualizar-bna", json={"html": "<div id='billetes'>"}).status_code == 200
    assert visto["html"] is None


def test_the_endpoint_answers_502_without_leaking_details(monkeypatch):
    client, _ = con_usuario()

    def caido(session, *, html=None):
        raise servicios.FuenteNoDisponible("No se pudo consultar al Banco Nación. Probá de nuevo en un rato.")

    monkeypatch.setattr(servicios, "actualizar_dolar_bna", caido)
    response = client.post("/dolar/actualizar-bna")
    assert response.status_code == 502
    assert response.json() == {"detail": "No se pudo consultar al Banco Nación. Probá de nuevo en un rato."}


def test_the_endpoint_502_on_a_real_parser_failure_does_not_echo_the_page(monkeypatch):
    client, _ = con_usuario()
    monkeypatch.setattr(dolar_bna, "descargar_bna", lambda client=None: "<html>SECRETO-DEL-UPSTREAM</html>")
    response = client.post("/dolar/actualizar-bna")
    assert response.status_code == 502
    assert "SECRETO" not in response.text and "<html>" not in response.text


def test_existing_dolar_routes_keep_their_behaviour(monkeypatch):
    client, session = con_usuario()
    monkeypatch.setattr(servicios, "listar_dolar", lambda s: [
        {"fecha": date(2026, 9, 1), "ars_por_usd": D("1545"), "fuente": "MANUAL", "tipo": "VENDEDOR", "nota": None}])
    assert client.get("/dolar").json() == [
        {"fecha": "2026-09-01", "ars_por_usd": "1545", "fuente": "MANUAL", "tipo": "VENDEDOR", "nota": None}]
    visto = {}
    monkeypatch.setattr(servicios, "crear_dolar", lambda s, **k: visto.update(k) or {
        "fecha": k["fecha"], "ars_por_usd": k["ars_por_usd"], "fuente": k["fuente"], "tipo": k["tipo"], "nota": k["nota"]})
    response = client.post("/dolar", json={"fecha": "2026-10-01", "ars_por_usd": "1700"})
    assert response.status_code == 201 and visto["fuente"] == "MANUAL"
    assert client.post("/dolar", json={"fecha": "2026-10-01", "ars_por_usd": "0"}).status_code == 422


# --- CLI -------------------------------------------------------------------------------------------------

class SesionFalsa:
    def __init__(self):
        self.cerrada = False

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.cerrada = True


def preparar_cli(monkeypatch, resultado=None, error=None):
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@localhost/db")
    motor = MagicMock()
    monkeypatch.setattr(actualizar_dolar.database, "create_database_engine", lambda: motor)
    monkeypatch.setattr(actualizar_dolar, "Session", lambda engine: SesionFalsa())

    def servicio(session, *, html=None):
        if error is not None:
            raise error
        return resultado

    monkeypatch.setattr(actualizar_dolar.servicios, "actualizar_dolar_bna", servicio)
    return motor


@pytest.mark.parametrize("estado, texto", [("creado", "cargado"), ("ya_existia", "ya estaba")])
def test_cli_exits_zero_on_created_or_already_present(monkeypatch, capsys, estado, texto):
    motor = preparar_cli(monkeypatch, resultado={"estado": estado, "fecha": date(2026, 10, 28), "ars_por_usd": D("1560.00")})
    assert actualizar_dolar.main() == 0
    salida = capsys.readouterr()
    assert texto in salida.out and "1560" in salida.out and salida.err == ""
    motor.dispose.assert_called_once()


def test_cli_exits_non_zero_with_a_clear_message_when_bna_fails(monkeypatch, capsys):
    motor = preparar_cli(monkeypatch, error=servicios.FuenteNoDisponible("No se pudo consultar al Banco Nación."))
    assert actualizar_dolar.main() == 1
    salida = capsys.readouterr()
    assert "No se pudo consultar al Banco Nación." in salida.err and salida.out == ""
    motor.dispose.assert_called_once()


def test_cli_exits_non_zero_without_database_url(monkeypatch, capsys):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    assert actualizar_dolar.main() == 1
    assert "DATABASE_URL" in capsys.readouterr().err


def test_cli_does_not_leak_unexpected_errors(monkeypatch, capsys):
    preparar_cli(monkeypatch, error=RuntimeError("postgresql://u:clave-secreta@host/db"))
    assert actualizar_dolar.main() == 1
    assert "clave-secreta" not in capsys.readouterr().err
