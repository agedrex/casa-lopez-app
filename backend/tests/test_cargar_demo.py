"""Demo loader (scripts/cargar_demo.py): pure part (guards, plan) and, against disposable PostgreSQL, the loading.

The pure tests need no database: the plan is a function of (today, workshops). The integration tests skip without
TEST_DATABASE_URL and run inside a transaction that is rolled back.
"""

import importlib.util
import json
from collections import Counter
from datetime import date
from decimal import Decimal as D
from pathlib import Path

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend import formulario, proveedores, servicios
from backend.models import (
    UNITS, Cotizacion, FormularioConsumo, Modelo, OrdenFabricacion, PedidoProveedor, PrecioMaterial, Producto, Proveedor,
    ProveedorProducto,
)

SCRIPTS = Path(__file__).parents[1] / "scripts"


def _cargar_script(nombre):
    spec = importlib.util.spec_from_file_location(nombre, SCRIPTS / f"{nombre}.py")
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


cd = _cargar_script("cargar_demo")
ce = _cargar_script("cargar_ejemplo")

HOY = date(2026, 11, 13)
TALLERES = ["TAL-0001", "TAL-0002", "TAL-0003"]
SEED = json.loads((Path(__file__).parents[1] / "migrations" / "seed_data" / "seed_v3.json").read_text(encoding="utf-8"))


def _tabla(nombre):
    tabla = next(t for t in SEED["tables"] if t["name"] == nombre)
    columnas = [c["name"] for c in tabla["columns"]]
    return [dict(zip(columnas, fila)) for fila in tabla["rows"]]


MATERIALES = {m["codigo"]: m for m in _tabla("material")}
CATEGORIAS = {c["nombre"] for c in _tabla("categoria")}


def plan(hoy=HOY, talleres=TALLERES):
    return cd.planificar(hoy, talleres)


# --- Refusals (exit code 2, Spanish message, nothing touched) ---------------------------------------------------------

@pytest.fixture
def sin_base(monkeypatch):
    """Any attempt to open the database fails the test: a refusal must happen before."""
    def prohibido(*_, **__):
        raise AssertionError("se intentó abrir la base de datos")
    monkeypatch.setattr(cd, "create_database_engine", prohibido)
    monkeypatch.setattr(cd, "correr", prohibido)
    monkeypatch.delenv("RAILWAY_ENVIRONMENT_NAME", raising=False)


@pytest.mark.parametrize("argumentos", [
    [], ["--confirmar"], ["--entorno", "produccion", "--confirmar"], ["--entorno", "production"],
    ["--entorno", "local", "--confirmar"], ["--entorno", "Staging", "--confirmar"],
])
def test_it_refuses_anything_but_the_staging_environment(argumentos, sin_base, capsys):
    assert cd.main(argumentos, hoy=HOY) == 2
    salida = capsys.readouterr()
    assert "staging" in salida.err and salida.out == ""


def test_it_refuses_a_railway_environment_that_is_not_staging(sin_base, monkeypatch, capsys):
    monkeypatch.setenv("RAILWAY_ENVIRONMENT_NAME", "production")
    assert cd.main(["--entorno", "staging", "--confirmar"], hoy=HOY) == 2
    salida = capsys.readouterr()
    assert "production" not in salida.err and salida.out == ""  # arbitrary environment text is never echoed


def test_it_needs_a_valid_database_url(sin_base, monkeypatch, capsys):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    assert cd.main(["--entorno", "staging"], hoy=HOY) == 1
    assert "DATABASE_URL" in capsys.readouterr().err


def test_the_database_is_described_without_the_password():
    texto = cd.describir_base("postgresql://usuario:secreto@db.ejemplo.test:5432/costos")
    assert texto == "db.ejemplo.test:5432/costos"
    assert "secreto" not in texto and "usuario" not in texto


@pytest.mark.parametrize("argumentos, escribe", [(["--entorno", "staging"], False), (["--entorno", "staging", "--confirmar"], True)])
def test_it_is_a_dry_run_unless_confirmed_and_never_prints_the_credentials(argumentos, escribe, monkeypatch, capsys):
    monkeypatch.delenv("RAILWAY_ENVIRONMENT_NAME", raising=False)
    monkeypatch.setenv("DATABASE_URL", "postgresql://usuario:secreto@db.ejemplo.test:5432/costos")
    visto = []

    def falso(hoy, escribir):
        visto.append((hoy, escribir))
        return cd.Resumen(plan(), escribir, Counter({"proveedores": 5}), Counter(), [])
    monkeypatch.setattr(cd, "correr", falso)
    assert cd.main(argumentos, hoy=HOY) == 0
    assert visto == [(HOY, escribe)]
    salida = capsys.readouterr()
    assert "db.ejemplo.test:5432/costos" in salida.out
    assert "secreto" not in salida.out + salida.err and "usuario" not in salida.out + salida.err
    assert ("Filas creadas" in salida.out) == escribe and ("Filas que se crearían" in salida.out) == (not escribe)


def test_an_unexpected_error_only_shows_its_class(monkeypatch, capsys):
    monkeypatch.delenv("RAILWAY_ENVIRONMENT_NAME", raising=False)
    monkeypatch.setenv("DATABASE_URL", "postgresql://usuario:secreto@db.ejemplo.test:5432/costos")

    def roto(hoy, escribir):
        raise RuntimeError("conexión a postgresql://usuario:secreto@db.ejemplo.test falló")
    monkeypatch.setattr(cd, "correr", roto)
    assert cd.main(["--entorno", "staging", "--confirmar"], hoy=HOY) == 1
    salida = capsys.readouterr()
    assert "RuntimeError" in salida.err and "secreto" not in salida.out + salida.err


# --- The plan ----------------------------------------------------------------------------------------------------

def test_the_plan_is_deterministic():
    assert plan() == plan()


def test_every_planned_row_carries_the_marker_and_keys_are_unique():
    filas = list(plan().filas())
    assert len(filas) > 50
    assert all(fila.marca.startswith("EJEMPLO") for fila in filas)
    claves = [(type(f).__name__, f.clave) for f in filas]
    assert len(claves) == len(set(claves))
    marcas = [f.marca for f in filas if type(f).__name__ != "CotizacionPlan"]
    assert len(marcas) == len(set(marcas))  # the marker is the key a second run recognizes a row by


def test_five_suppliers_with_four_to_eight_products_each():
    p = plan()
    assert len(p.proveedores) == 5
    assert {x.codigo for x in p.proveedores if x.codigo} == {"PRV-0001", "PRV-0002"}  # the codes the seeded prices already name
    for proveedor in p.proveedores:
        nombres = {x.nombre.casefold() for x in proveedor.productos}
        assert 4 <= len(nombres) <= 8, proveedor.nombre
        assert all("ejemplo" not in x.nombre.lower() for x in proveedor.productos) and "ejemplo" not in proveedor.nombre.lower()
    assert len({x.nombre for x in p.proveedores}) == 5


def test_supplier_products_use_valid_units_currencies_and_seeded_materials_with_their_own_unit():
    for proveedor in plan().proveedores:
        for x in proveedor.productos:
            assert x.unidad in UNITS and x.moneda in ("ARS", "USD")
            assert x.precio > 0 and (x.cantidad is None or x.cantidad > 0)
            assert x.desde <= HOY
            if x.material:
                assert x.material in MATERIALES, x
                assert MATERIALES[x.material]["unidad_de_consumo"] == x.unidad, x  # linked only when it is the same unit


def test_some_products_keep_an_older_price_row_that_is_older_and_different():
    p = plan()
    anteriores = [x for pr in p.proveedores for x in pr.productos if x.marca.endswith("(precio anterior)")]
    assert len(anteriores) >= 6
    for viejo in anteriores:
        actual = next(x for x in p.proveedores[int(viejo.proveedor) - 1].productos
                      if x.nombre == viejo.nombre and x.clave != viejo.clave)
        assert viejo.desde < actual.desde and viejo.precio != actual.precio and viejo.marca != actual.marca


def test_the_plan_links_the_seeded_materials_of_flex_eva_leather_and_lining():
    enlazados = {x.material for pr in plan().proveedores for x in pr.productos if x.material}
    assert {"MAT-FL01", "MAT-GE01", "MAT-CU01", "MAT-CU02", "MAT-FO02", "MAT-HC01"} <= enlazados


def test_two_supplier_orders_for_materials_the_plan_links():
    p = plan()
    assert len(p.pedidos) == 2 and all(x.fecha == HOY for x in p.pedidos)
    for pedido in p.pedidos:
        linkeados = {x.material for x in next(pr for pr in p.proveedores if pr.clave == pedido.proveedor).productos}
        assert pedido.lineas and all(l.material in linkeados and l.cantidad > 0 and l.contenido > 0 for l in pedido.lineas)


def test_quotes_include_an_initial_and_a_recotizacion_of_one_product_on_different_dates():
    cotizaciones = plan().cotizaciones
    assert len(cotizaciones) >= 6
    por_producto = {}
    for c in cotizaciones:
        por_producto.setdefault(c.producto, {})[c.tipo] = c.fecha
    assert any({"INICIAL", "RECOTIZACION"} <= set(t) and t["INICIAL"] < t["RECOTIZACION"] for t in por_producto.values())
    assert all(cd.FECHA_MINIMA_COTIZACION <= c.fecha <= HOY for c in cotizaciones)
    assert len({(c.producto, c.tipo) for c in cotizaciones}) == len(cotizaciones)
    assert len({c.fecha for c in cotizaciones}) >= 6
    assert not ({7, 8} & set(por_producto))  # two products stay unquoted: the grid falls back to today's cost for them


def test_quote_dates_never_go_before_the_first_seeded_price():
    cotizaciones = plan(hoy=date(2026, 9, 10)).cotizaciones
    assert all(c.fecha >= cd.FECHA_MINIMA_COTIZACION for c in cotizaciones)


def test_at_least_three_lots_in_several_states_and_one_with_several_products():
    lotes = plan().lotes
    assert len(lotes) >= 3
    finales = [lote.pasos[-1][0] if lote.pasos else "PLANIFICADA" for lote in lotes]
    assert {"PLANIFICADA", "EN_CORTE", "EN_CONFECCION"} <= set(finales)
    assert any(len(l.renglones) >= 3 for l in lotes if l.pasos and l.pasos[-1][0] == "EN_CONFECCION")
    for lote in lotes:
        fechas = [f for _, f in lote.pasos]
        assert fechas == sorted(fechas) and all(lote.envio <= f <= HOY for f in fechas) and lote.envio <= HOY
        assert [e for e, _ in lote.pasos] == list(cd.CAMINO[:len(lote.pasos)])
        assert all(r.cantidad > 0 for r in lote.renglones) and len({r.producto for r in lote.renglones}) == len(lote.renglones)
        assert (lote.taller in TALLERES) == (lote.donde == "EXTERNA")
        assert all((r.cotizado is not None and r.cotizado > 0) == (lote.donde == "EXTERNA") for r in lote.renglones)


def test_without_workshops_every_lot_is_made_in_house():
    lotes = plan(talleres=[]).lotes
    assert lotes and all(l.donde == "INTERNA" and l.taller is None for l in lotes)
    assert all(r.cotizado is None for l in lotes for r in l.renglones)


def test_the_quantity_table_covers_exactly_the_rows_the_sheet_preloads():
    assert set(cd.MEDIDAS) == {l["nombre"] for l in formulario.lineas_precargadas()}


def test_five_forms_in_the_states_the_demo_needs():
    formularios = plan().formularios
    assert len(formularios) == 5
    assert len({f.articulo.casefold() for f in formularios}) == 5 and all("ejemplo" not in f.articulo.lower() for f in formularios)
    assert all(f.categoria in CATEGORIAS for f in formularios)
    final = {}
    for f in formularios:
        estado = "BORRADOR" if f.tipo == "SUELTO" else "ENVIADO"
        for paso in f.pasos:
            estado = {"llenar": estado, "completar": "COMPLETADO", "devolver": "ENVIADO", "validar": "VALIDADO"}[paso]
        final[f.clave] = estado
    assert sorted(final.values()) == ["BORRADOR", "COMPLETADO", "ENVIADO", "ENVIADO", "VALIDADO"]


def test_the_practice_form_is_a_new_model_sent_empty_and_the_completed_one_is_fully_filled():
    practica, completada, devuelta, borrador, validada = plan().formularios
    assert practica.tipo == "MODELO" and practica.pasos == () and all(c is None for _, _, c in practica.lineas)
    assert len(completada.lineas) == 30 and all(c is not None and c >= 0 for _, _, c in completada.lineas)
    assert completada.pasos == ("llenar", "completar") and validada.pasos == ("llenar", "completar", "validar")
    assert devuelta.pasos[-1] == "devolver" and devuelta.comentario
    assert 0 < sum(c is not None for _, _, c in devuelta.lineas) < 30  # partly filled
    assert borrador.tipo == "SUELTO" and borrador.pasos == ()
    assert {(s, n) for s, n, _ in practica.lineas} == {(l["seccion"], l["nombre"]) for l in formulario.lineas_precargadas()}


# --- Loading (disposable PostgreSQL) ------------------------------------------------------------------------------------

TABLAS = (Proveedor, ProveedorProducto, PedidoProveedor, Cotizacion, OrdenFabricacion, FormularioConsumo, Modelo, PrecioMaterial, Producto)


@pytest.fixture
def session(local_postgres):
    connection = local_postgres.connect()
    outer = connection.begin()
    session = Session(bind=connection, join_transaction_mode="create_savepoint")
    try:
        yield session
    finally:
        session.close()
        outer.rollback()
        connection.close()


def conteos(session):
    return {tabla.__tablename__: session.scalar(select(func.count()).select_from(tabla)) for tabla in TABLAS}


def con_ejemplo(session):
    hoy = date.today()
    ce.cargar_ejemplo(session, servicios.mes_de(hoy), hoy)
    return hoy


def test_a_second_run_creates_nothing_and_a_dry_run_writes_nothing_and_predicts_the_real_one(session):
    hoy = con_ejemplo(session)
    antes = conteos(session)
    simulada = cd.cargar_demo(session, hoy, escribir=False)
    assert conteos(session) == antes
    real = cd.cargar_demo(session, hoy)
    assert real.avisos == [] and real.total_creado > 80
    assert simulada.creados == real.creados
    despues = conteos(session)
    assert all(despues[t] >= antes[t] for t in antes)
    segunda = cd.cargar_demo(session, hoy)
    assert segunda.total_creado == 0 and segunda.creados == {} and segunda.avisos == []
    assert conteos(session) == despues


def test_the_new_rows_of_every_marked_table_all_carry_the_marker(session):
    hoy = con_ejemplo(session)
    antes = conteos(session)
    cd.cargar_demo(session, hoy)
    despues = conteos(session)
    for tabla, columna in ((Proveedor, Proveedor.nota), (ProveedorProducto, ProveedorProducto.nota),
                           (PedidoProveedor, PedidoProveedor.nota), (OrdenFabricacion, OrdenFabricacion.nota),
                           (FormularioConsumo, FormularioConsumo.nota), (Modelo, Modelo.nota)):
        nombre = tabla.__tablename__
        nuevos = despues[nombre] - antes[nombre]
        marcados = session.scalar(select(func.count()).select_from(tabla).where(columna.like("EJEMPLO%")))
        assert nuevos > 0 and marcados >= nuevos, nombre


def test_suppliers_come_with_their_products_and_the_orders_do_not_move_any_price_in_force(session):
    hoy = con_ejemplo(session)
    vigentes = lambda: {p["material"]: p["precio"] for p in servicios.listar_precios(session, a_fecha=hoy) if p["vigente"] and p["color"] is None}
    antes = vigentes()
    cd.cargar_demo(session, hoy)
    assert vigentes() == antes  # an order at today's price leaves every price in force as it was
    lista = proveedores.list_suppliers(session)
    demo = [s for s in lista if (s["nota"] or "").startswith("EJEMPLO")]
    assert len(demo) == 5
    for proveedor in demo:
        productos = proveedores.list_products(session, proveedor["codigo"])
        assert 4 <= len(productos) <= 8, proveedor["nombre"]
    flex = next(p for p in proveedores.list_products(session, "PRV-0001") if p["material"] == "MAT-FL01")
    assert flex["precio_referencial"] == D("14000") and flex["precio_anterior"] == D("12600") and flex["cargas"] == 2
    historial = proveedores.list_products(session, "PRV-0001", historial=True)
    assert sum(1 for p in historial if p["material"] == "MAT-FL01") == 2
    pedidos = proveedores.list_orders(session, "PRV-0001")
    assert len(pedidos) == 1 and pedidos[0]["lineas"][0]["material"] == "MAT-FL01"
    assert pedidos[0]["lineas"][0]["precio_unitario"] == antes["MAT-FL01"]


def test_quotes_are_saved_with_their_own_dollar_and_the_list_shows_them(session):
    hoy = con_ejemplo(session)
    cd.cargar_demo(session, hoy)
    filas = {f["codigo"]: f for f in servicios.listar_productos(session, limit=500)}
    productos = dict(session.execute(select(Producto.nota, Producto.codigo).where(Producto.nota.like("EJEMPLO producto %"))).all())
    uno = filas[productos["EJEMPLO producto 1"]]
    assert uno["cotizacion_fecha"] is not None and uno["cotizacion_dolar"] is not None
    tipos = {c["tipo"]: c for c in servicios.cotizaciones_guardadas(session) if c["producto"] == uno["codigo"]}
    assert set(tipos) == {"INICIAL", "RECOTIZACION"} and tipos["INICIAL"]["dolar"] != tipos["RECOTIZACION"]["dolar"]
    assert uno["cotizacion_dolar"] == tipos["RECOTIZACION"]["dolar"] and uno["costo_cotizado_ars"] == tipos["RECOTIZACION"]["total_ars"]
    assert len({c["dolar"] for c in servicios.cotizaciones_guardadas(session)}) >= 2
    for numero in (7, 8):  # never quoted: the grid shows today's cost
        sin = filas[productos[f"EJEMPLO producto {numero}"]]
        assert sin["cotizacion_fecha"] is None and sin["costo_hoy_ars"] is not None


def test_the_demo_lots_cover_several_states_and_one_has_several_products(session):
    hoy = con_ejemplo(session)
    cd.cargar_demo(session, hoy)
    lotes = [l for l in servicios.listar_ordenes(session) if (l["nota"] or "").startswith("EJEMPLO demo lote")]
    assert len(lotes) == 4
    assert {l["estado"] for l in lotes} == {"PLANIFICADA", "EN_CORTE", "EN_CONFECCION", "LISTA"}
    en_confeccion = next(l for l in lotes if l["estado"] == "EN_CONFECCION")
    assert len(en_confeccion["items"]) >= 3 and all(i["cantidad"] > 0 for i in en_confeccion["items"])
    assert all(l["taller"] is not None for l in lotes if l["donde_se_hace"] == "EXTERNA")


def test_forms_are_visible_to_the_taller_only_when_sent_or_completed_and_the_practice_one_is_empty(session):
    hoy = con_ejemplo(session)
    cd.cargar_demo(session, hoy)
    admin, taller = frozenset({"admin"}), frozenset({"taller"})
    demo = {f["articulo"]: f for f in formulario.listar_formularios(session, q=None, estado=None, roles=admin)
            if f["articulo"] in {x.articulo.upper() for x in plan().formularios} | {x.articulo for x in plan().formularios}}
    assert sorted(f["estado"] for f in demo.values()) == ["BORRADOR", "COMPLETADO", "ENVIADO", "ENVIADO", "VALIDADO"]
    vistos = {f["articulo"] for f in formulario.listar_formularios(session, q=None, estado=None, roles=taller)}
    assert vistos & set(demo) == {a for a, f in demo.items() if f["estado"] in ("ENVIADO", "COMPLETADO")}
    practica = formulario.obtener_formulario(session, demo["BANDOLERA MINI NUEVA"]["codigo"], taller)
    assert practica["estado"] == "ENVIADO" and len(practica["lineas"]) == 30
    assert all(l["cantidad"] is None for l in practica["lineas"]) and practica["modelo"] is not None
    modelo = servicios.detalle_modelo(session, practica["modelo"])
    assert modelo["cuero_m2_por_unidad"] is None and modelo["validado"] is False  # a new model with empty consumptions
    completada = formulario.obtener_formulario(session, demo["MOCHILA URBANA NUEVA"]["codigo"], taller)
    assert completada["estado"] == "COMPLETADO" and all(l["cantidad"] is not None for l in completada["lineas"])
    devuelta = formulario.obtener_formulario(session, demo["TARJETERO SLIM NUEVO"]["codigo"], taller)
    assert devuelta["estado"] == "ENVIADO" and devuelta["comentario_revision"]
    validada = formulario.obtener_formulario(session, demo["BILLETERA BIFOLD NUEVA"]["codigo"], admin)
    assert validada["estado"] == "VALIDADO" and validada["validado_por"] == cd.QUIEN
    assert servicios.detalle_modelo(session, validada["modelo"])["validado"] is True
    borrador = demo["CINTURÓN CON HEBILLA NUEVO"] if "CINTURÓN CON HEBILLA NUEVO" in demo else demo["Cinturón con hebilla nuevo"]
    assert borrador["estado"] == "BORRADOR"
    assert borrador["codigo"] not in {f["codigo"] for f in formulario.listar_formularios(session, q=None, estado=None, roles=taller)}


def test_a_run_that_stopped_halfway_continues_each_form_and_lot_from_where_it_was(session):
    hoy = con_ejemplo(session)
    cd.cargar_demo(session, hoy)
    admin = frozenset({"admin"})
    # An admin sends the completed form back: the demo must not complete it again, nor refill it.
    codigo = next(f["codigo"] for f in formulario.listar_formularios(session, q=None, estado="COMPLETADO", roles=admin))
    formulario.cambiar_estado(session, codigo, "devolver", roles=admin, quien="otra-persona", comentario="Revisá el cuero.")
    assert cd.cargar_demo(session, hoy).total_creado == 0
    assert formulario.obtener_formulario(session, codigo, admin)["estado"] == "ENVIADO"


def test_without_the_example_products_it_still_loads_suppliers_and_forms_and_says_what_it_skipped(session):
    resumen = cd.cargar_demo(session, date.today())
    assert resumen.creados["proveedores"] == 5 and resumen.creados["formularios"] == 5
    assert "cotizaciones" not in resumen.creados and "lotes" not in resumen.creados
    assert any("cargar_ejemplo" in aviso for aviso in resumen.avisos)


def test_a_supplier_that_already_exists_without_the_marker_is_left_alone(session):
    proveedores.create_supplier(session, codigo="PRV-0009", nombre="Textil Palermo", cuit=None, contacto=None, telefono=None,
                                direccion=None, nota="real")
    resumen = cd.cargar_demo(session, date.today())
    assert resumen.creados["proveedores"] == 4
    assert any("Textil Palermo" in aviso for aviso in resumen.avisos)
    assert session.scalar(select(func.count()).select_from(Proveedor).where(Proveedor.nombre == "Textil Palermo")) == 1
    assert proveedores.list_suppliers(session, q="Textil")[0]["nota"] == "real"


def test_a_taken_explicit_supplier_code_skips_that_supplier_and_its_products_with_a_warning(session):
    proveedores.create_supplier(session, codigo=None, nombre="Otro proveedor", cuit=None, contacto=None, telefono=None,
                                direccion=None, nota="real")  # takes PRV-0001, which the demo wants for the flex supplier
    resumen = cd.cargar_demo(session, date.today())
    assert resumen.creados["proveedores"] == 4
    assert any("Espumas y Flex del Sur" in aviso for aviso in resumen.avisos)
    assert proveedores.list_products(session, "PRV-0001") == []
