"""Supplies per model (`modelo_insumo`, MIN-nnnn): the table, the name match, the saving on validation and the costing.

The first block needs no database (pure rules, the model, migration 0019). The second runs against disposable PostgreSQL
(skipped without TEST_DATABASE_URL), inside a transaction that is rolled back. The engine rules live in test_receta.py.
"""

import runpy
from datetime import date
from decimal import Decimal as D
from pathlib import Path

import pytest
from sqlalchemy import CheckConstraint, UniqueConstraint, select
from sqlalchemy.exc import IntegrityError

from backend import formulario, servicios
from backend.auth import Usuario, get_verifier
from backend.main import app
from backend.models import Etapa, Material, Modelo, ModeloInsumo

from test_costos_fijos_correccion_integration import api  # noqa: E402,F401  (fixture; its client also carries `.session`)

VERSIONS = Path(__file__).parents[1] / "migrations" / "versions"


# --- No database --------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("a, b", [
    ("CARTÓN FIBRA", "carton fibra"), ("  Cartón   Fibra ", "CARTON FIBRA"), ("Moiré", "moire"), ("Imán", "IMAN"),
])
def test_names_match_ignoring_case_accents_and_repeated_spaces(a, b):
    assert formulario.normalizar_para_comparar(a) == formulario.normalizar_para_comparar(b)


def test_different_names_do_not_match():
    assert formulario.normalizar_para_comparar("CIERRE N5") != formulario.normalizar_para_comparar("CIERRE N3")
    assert formulario.normalizar_para_comparar(None) == ""


MATERIALES = [(1, "Cierre N5 metálico", "Cierre N5"), (2, "Friselina", None), (3, "Cartón fibra", "carton  fibra"),
              (4, "Hebilla chica", "Hebilla"), (5, "Hebilla grande", "hebilla")]


def test_herraje_rows_with_a_quantity_match_by_nombre_or_nombre_corto():
    cantidades, sin = formulario.separar_insumos([
        ("HERRAJE", "CIERRE N5", D("2")), ("HERRAJE", "cierre  n5 metálico", D("1")),
    ], MATERIALES)
    assert cantidades == {1: D("3")} and sin == []  # both rows are material 1: they add up


def test_only_the_four_consumo_rows_are_supplies_and_the_others_are_ignored():
    cantidades, sin = formulario.separar_insumos([
        ("CONSUMO", "FRISELINA", D("0.5")), ("CONSUMO", "CARTÓN FIBRA", D("0.2")), ("CONSUMO", "CUERO", D("1")),
        ("CONSUMO", "MOIRE", D("0.1")), ("CONSUMO", "CARTULINA", D("0.3")),
    ], MATERIALES)
    assert cantidades == {2: D("0.5"), 3: D("0.2")}
    assert sin == ["MOIRE", "CARTULINA"]  # they have a quantity and no material: reported, not saved


def test_rows_without_quantity_or_with_zero_are_neither_saved_nor_reported():
    cantidades, sin = formulario.separar_insumos([
        ("HERRAJE", "CIERRE N5", None), ("HERRAJE", "HEBILLA", D("0")), ("HERRAJE", "MOSQUETÓN", None),
    ], MATERIALES)
    assert (cantidades, sin) == ({}, [])


def test_unmatched_herrajes_are_reported_by_name_without_repeats():
    _, sin = formulario.separar_insumos([
        ("HERRAJE", "MOSQUETÓN", D("1")), ("HERRAJE", "mosquetón", D("2")), ("HERRAJE", "IMÁN", D("1")),
    ], MATERIALES)
    assert sin == ["MOSQUETÓN", "IMÁN"]


def test_a_name_that_fits_two_materials_is_not_guessed():
    cantidades, sin = formulario.separar_insumos([("HERRAJE", "HEBILLA", D("1"))], MATERIALES)
    assert cantidades == {} and sin == ["HEBILLA"]


def test_the_model_declares_the_supply_rules():
    tabla = ModeloInsumo.__table__
    assert tabla.schema == "costos" and tabla.c.codigo.unique
    assert (tabla.c.cantidad_por_unidad.type.precision, tabla.c.cantidad_por_unidad.type.scale) == (12, 6)
    assert not tabla.c.modelo_id.nullable and not tabla.c.material_id.nullable and not tabla.c.cantidad_por_unidad.nullable
    checks = {c.name: str(c.sqltext) for c in tabla.constraints if isinstance(c, CheckConstraint)}
    assert checks == {"ck_modelo_insumo_cantidad_positiva": "cantidad_por_unidad > 0"}
    assert ("modelo_id", "material_id") in [tuple(c.columns.keys()) for c in tabla.constraints if isinstance(c, UniqueConstraint)]


def test_revision_0019_creates_the_table_and_the_downgrade_drops_it_and_warns(monkeypatch):
    from test_migrations import load_revision
    operations, base = load_revision(monkeypatch, "0003_der_v3.py")
    base["upgrade"]()
    revision = runpy.run_path(str(VERSIONS / "0019_modelo_insumo.py"))
    assert revision["revision"] == "0019_modelo_insumo" and revision["down_revision"] == "0018_pedidos_proveedor"
    revision["upgrade"]()
    creada = operations.metadata.tables["costos.modelo_insumo"]
    assert {fk.target_fullname for fk in creada.foreign_keys} == {"costos.modelo.id", "costos.material.id"}
    revision["downgrade"]()
    assert operations.dropped[-1] == "modelo_insumo"
    assert "lost" in revision["__doc__"]


# --- PostgreSQL ---------------------------------------------------------------------------------------------------

DIA = "2026-09-01"  # the seeded dollar (1545) is dated this day


def como(role, usuario="admin-1"):
    app.dependency_overrides[get_verifier] = lambda: (lambda request: Usuario(id=usuario, role=role))


def material(api, codigo, nombre, etapa, unidad, nombre_corto=None, **extra):
    fila = Material(codigo=codigo, nombre=nombre, nombre_corto=nombre_corto, unidad_de_consumo=unidad, **extra,
                    etapa_id=api.session.scalar(select(Etapa.id).where(Etapa.codigo == etapa)))
    api.session.add(fila)
    api.session.flush()
    return fila


def precio(api, codigo, valor, moneda, unidad):
    servicios.crear_precio(
        api.session, material=codigo, color=None, proveedor=None, precio=D(valor), moneda=moneda, unidad_del_precio=unidad,
        iva_incluido=False, vigente_desde=date.fromisoformat(DIA), commit=False)


def completar_hoja(api, cantidades, nombre="Zz Cartera insumos"):
    """Quick-create a model, let the taller fill `cantidades` ({row name: quantity}) and complete it; return (model, form)."""
    como("admin")
    datos = api.post("/productos/nuevo", json={"nombre": nombre}).json()
    como("taller")
    hoja = api.get(f"/formularios/{datos['formulario']}").json()
    for l in hoja["lineas"]:
        if l["nombre"] in cantidades:
            l["cantidad"] = cantidades[l["nombre"]]
    cuerpo = {"articulo": hoja["articulo"], "nota": hoja["nota"],
              "lineas": [{k: l[k] for k in ("seccion", "nombre", "cantidad", "comentario")} for l in hoja["lineas"]]}
    assert api.put(f"/formularios/{datos['formulario']}", json=cuerpo).status_code == 200
    assert api.post(f"/formularios/{datos['formulario']}/completar").status_code == 200
    como("admin")
    return datos["modelo"], datos["formulario"]


def insumos_de(api, modelo):
    return api.get(f"/modelos/{modelo}").json()["insumos"]


def test_pg_validating_saves_matching_rows_as_insumos_and_reports_the_rest_in_sin_material(api):
    material(api, "MAT-IN01", "Cierre N5 metálico", "HERRAJES", "unidad", nombre_corto="Cierre N5")
    material(api, "MAT-IN02", "Friselina", "FLEX", "m2")
    precio(api, "MAT-IN01", "1.5", "USD", "unidad")
    modelo, codigo = completar_hoja(api, {"CIERRE N5": "2", "FRISELINA": "0.5", "HEBILLA": "1", "MOIRE": "0.2", "CUERO": "0.4"})
    respuesta = api.post(f"/formularios/{codigo}/validar")
    assert respuesta.status_code == 200, respuesta.text
    assert respuesta.json()["sin_material"] == ["MOIRE", "HEBILLA"]  # in the order of the sheet: CONSUMO rows, then HERRAJE rows
    insumos = {i["material"]: i for i in insumos_de(api, modelo)}
    assert set(insumos) == {"MAT-IN01", "MAT-IN02"}
    assert insumos["MAT-IN01"]["codigo"].startswith("MIN-")
    assert D(insumos["MAT-IN01"]["cantidad_por_unidad"]) == D("2") and insumos["MAT-IN01"]["etapa"] == "HERRAJES"
    assert (D(insumos["MAT-IN01"]["precio_unitario"]), insumos["MAT-IN01"]["moneda"]) == (D("1.5"), "USD")
    assert insumos["MAT-IN02"]["precio_unitario"] is None and insumos["MAT-IN02"]["unidad_de_consumo"] == "m2"
    assert api.get(f"/formularios/{codigo}").json()["sin_material"] is None  # only the answer of `validar` carries it


def test_pg_codes_are_consecutive_and_the_pair_modelo_material_is_unique(api):
    material(api, "MAT-IN01", "Cierre N5", "HERRAJES", "unidad")
    material(api, "MAT-IN02", "Friselina", "FLEX", "m2")
    modelo, codigo = completar_hoja(api, {"CIERRE N5": "2", "FRISELINA": "1"})
    api.post(f"/formularios/{codigo}/validar")
    assert [i["codigo"] for i in insumos_de(api, modelo)] == ["MIN-0001", "MIN-0002"]
    fila = api.session.scalar(select(ModeloInsumo))
    with pytest.raises(IntegrityError):
        with api.session.begin_nested():
            api.session.add(ModeloInsumo(codigo="MIN-9999", modelo_id=fila.modelo_id, material_id=fila.material_id,
                                         cantidad_por_unidad=D("1")))
            api.session.flush()
    for malo in (D("0"), D("-1")):
        with pytest.raises(IntegrityError):
            with api.session.begin_nested():
                api.session.add(ModeloInsumo(codigo="MIN-9998", modelo_id=fila.modelo_id, cantidad_por_unidad=malo,
                                             material_id=api.session.scalar(select(Material.id).where(Material.codigo == "MAT-FL01"))))
                api.session.flush()


def test_pg_saving_the_supplies_twice_updates_the_row_instead_of_duplicating_it(api):
    material(api, "MAT-IN01", "Cierre N5", "HERRAJES", "unidad")
    modelo, codigo = completar_hoja(api, {"CIERRE N5": "2"})
    api.post(f"/formularios/{codigo}/validar")
    form = api.session.scalar(select(formulario.FormularioConsumo).where(formulario.FormularioConsumo.codigo == codigo))
    linea = api.session.scalar(select(formulario.FormularioConsumoLinea).where(
        formulario.FormularioConsumoLinea.formulario_id == form.id, formulario.FormularioConsumoLinea.nombre == "CIERRE N5"))
    modelo_fila = api.session.scalar(select(Modelo).where(Modelo.codigo == modelo))
    assert formulario._guardar_insumos(api.session, modelo_fila, form) == []
    linea.cantidad = D("5")
    assert formulario._guardar_insumos(api.session, modelo_fila, form) == []
    filas = api.session.scalars(select(ModeloInsumo).where(ModeloInsumo.modelo_id == modelo_fila.id)).all()
    assert len(filas) == 1 and filas[0].cantidad_por_unidad == D("5")


def test_pg_an_already_validated_model_is_not_touched_and_nothing_is_reported(api):
    material(api, "MAT-IN01", "Cierre N5", "HERRAJES", "unidad")
    modelo, codigo = completar_hoja(api, {"CIERRE N5": "2", "HEBILLA": "1", "CUERO": "0.4"})
    assert api.post(f"/modelos/{modelo}/validado", json={"validado": True}).status_code == 200
    respuesta = api.post(f"/formularios/{codigo}/validar")
    assert respuesta.status_code == 200
    assert respuesta.json()["sin_material"] is None
    assert insumos_de(api, modelo) == []
    assert api.get(f"/modelos/{modelo}").json()["cuero_m2_por_unidad"] is None  # the measures were not copied either


def test_pg_only_costable_materials_of_a_material_stage_can_be_matched(api):
    material(api, "MAT-IN01", "Cierre N5", "HERRAJES", "unidad", cotizable=False)
    modelo, codigo = completar_hoja(api, {"CIERRE N5": "2"})
    assert api.post(f"/formularios/{codigo}/validar").json()["sin_material"] == ["CIERRE N5"]
    assert insumos_de(api, modelo) == []


def producto_de(api, modelo):
    return servicios.crear_producto(
        api.session, modelo=modelo, cuero="MAT-CU01", color=None, quien_lo_confecciona="INTERNA", fecha_de_alta=None,
        nombre_propio=None, es_kit=False)


def test_pg_the_cost_of_a_product_uses_the_supplies_of_its_model_instead_of_the_herrajes_amount(api):
    material(api, "MAT-IN01", "Cierre N5", "HERRAJES", "unidad")
    precio(api, "MAT-IN01", "1.5", "USD", "unidad")
    modelo, codigo = completar_hoja(api, {"CIERRE N5": "2", "CUERO": "0.4"})
    api.session.scalar(select(Modelo).where(Modelo.codigo == modelo)).herrajes_usd_por_unidad = D("5")
    producto = producto_de(api, modelo)["codigo"]
    assert any(l["material"] == "MAT-HE00" for l in api.get(f"/productos/{producto}").json()["receta"])  # before: the USD 5
    api.post(f"/formularios/{codigo}/validar")
    ficha = api.get(f"/productos/{producto}").json()
    assert [l["material"] for l in ficha["receta"] if l["etapa"] == "HERRAJES"] == ["MAT-IN01"]  # replaced, no double count
    assert D(ficha["costo_hoy"]["etapas"]["HERRAJES"]) == D("2") * D("1.5") * D("1545")  # USD x the dollar of the date


def test_pg_a_supply_without_a_price_makes_the_product_quote_incomplete_with_a_warning(api):
    material(api, "MAT-IN01", "Cierre N5", "HERRAJES", "unidad")
    modelo, codigo = completar_hoja(api, {"CIERRE N5": "2", "CUERO": "0.4"})
    api.post(f"/formularios/{codigo}/validar")
    ficha = producto_de(api, modelo)
    assert ficha["costo_hoy"] is None
    assert "Sin precio para MAT-IN01 a esa fecha" in ficha["avisos"]
    precio(api, "MAT-IN01", "1.5", "USD", "unidad")
    assert producto_de(api, modelo)["costo_hoy"] is not None


def test_pg_a_model_without_supplies_has_an_empty_list_and_keeps_its_cost(api):
    modelo = api.session.scalar(select(Modelo.codigo).where(Modelo.cuero_m2_por_unidad > 0).limit(1))
    assert api.get(f"/modelos/{modelo}").json()["insumos"] == []
