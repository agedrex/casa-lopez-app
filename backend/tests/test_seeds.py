"""Offline checks of the DER v3 reference seeds (seed_v3.json and revision 0004)."""

import json
import runpy
import sys
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

import pytest
from sqlalchemy.dialects import postgresql

from backend.models import Base


BACKEND = Path(__file__).parents[1]
SEED_FILE = BACKEND / "migrations" / "seed_data" / "seed_v3.json"
EXPECTED_COUNTS = {
    "etapa": 8, "categoria": 16, "material": 13, "persona": 7, "taller": 3, "impuesto": 3,
    "parametro": 8, "tipo_cambio": 1, "precio_material": 11, "modelo": 325, "gasto_periodo": 15,
}


@pytest.fixture(scope="module")
def seed():
    return {table["name"]: table for table in json.loads(SEED_FILE.read_text(encoding="utf-8"))["tables"]}


def records(table):
    names = [column["name"] for column in table["columns"]]
    return [dict(zip(names, row)) for row in table["rows"]]


def test_seed_counts_match_the_filled_in_rows_of_the_plantilla(seed):
    assert {name: len(table["rows"]) for name, table in seed.items()} == EXPECTED_COUNTS
    # The Colores sheet only has empty coded rows: nothing to seed.
    assert "color" not in seed


def test_seed_columns_exist_in_the_models_and_rows_are_rectangular(seed):
    for name, table in seed.items():
        model = Base.metadata.tables[f"costos.{name}"]
        assert {column["name"] for column in table["columns"]} <= set(model.c.keys())
        assert all(len(row) == len(table["columns"]) for row in table["rows"])


def test_money_is_stored_as_strings_never_floats(seed):
    for table in seed.values():
        decimal_positions = [i for i, column in enumerate(table["columns"]) if column["tag"] == "decimal"]
        for row in table["rows"]:
            assert not any(isinstance(value, float) for value in row)
            for position in decimal_positions:
                if row[position] is not None:
                    assert isinstance(row[position], str)
                    Decimal(row[position])


def test_stages_and_materials_are_the_ones_in_the_dictionary(seed):
    stages = records(seed["etapa"])
    assert [stage["codigo"] for stage in stages] == [
        "CUERO", "FORRO", "FLEX", "GOMA_EVA", "HERRAJES", "HILO_CEMENTO", "CORTE", "CONFECCION"]
    assert [stage["orden"] for stage in stages] == list(range(1, 9))
    materials = {material["codigo"]: material for material in records(seed["material"])}
    assert len(materials) == 13
    assert {code for code, material in materials.items() if material["cotizable"] is False} == {"MAT-CU03", "MAT-CU04"}
    assert all(material["etapa_id"] in {stage["codigo"] for stage in stages} for material in materials.values())


def test_business_keys_are_unique_and_foreign_references_resolve(seed):
    for name, table in seed.items():
        if "codigo" in {column["name"] for column in table["columns"]}:
            codes = [record["codigo"] for record in records(table)]
            assert len(codes) == len(set(codes)), name
    available = {name: records(table) for name, table in seed.items()}
    for name, table in seed.items():
        for index, column in enumerate(table["columns"]):
            if column["tag"] != "fk":
                continue
            ref_table, ref_column = column["ref"]
            valid = {record[ref_column] for record in available.get(ref_table, [])}
            for row in table["rows"]:
                assert row[index] is None or row[index] in valid, (name, column["name"], row[index])


def test_parameters_keep_the_sheet_values_and_skip_the_calculated_ones(seed):
    parameters = {record["codigo"]: record for record in records(seed["parametro"])}
    assert "DOLAR_VIGENTE" not in parameters and "FECHA_DOLAR_VIGENTE" not in parameters
    assert parameters["DOLAR_PARIDAD"]["valor"] == "1545"
    assert parameters["GG_PCT_EXCEL"]["valor"] == "0.11"
    assert parameters["PERIODO_VIGENTE"]["valor"] is None and parameters["PERIODO_VIGENTE"]["valor_texto"] == "2026-10"
    assert parameters["UMBRAL_RETAZO_M2"]["valor"] is None
    assert all(record["fuente_estado"] for record in parameters.values())


def test_exchange_rate_prices_and_example_workshops(seed):
    assert records(seed["tipo_cambio"]) == [{
        "fecha": "2026-09-01", "ars_por_usd": "1545", "fuente": "EXCEL_VIEJO", "tipo": None,
        "nota": records(seed["tipo_cambio"])[0]["nota"]}]
    prices = records(seed["precio_material"])
    assert {price["vigente_desde"] for price in prices} == {"2026-09-01", "2026-09-03"}
    assert {price["material_id"] for price in prices}.isdisjoint({"MAT-CU03", "MAT-CU04"})
    assert all("ejemplo" in workshop["nota"].lower() for workshop in records(seed["taller"]))


def test_models_seed_is_complete_and_flags_nothing_as_validated(seed):
    models = records(seed["modelo"])
    assert len(models) == 325 and len({model["nombre_del_modelo"] for model in models}) == 325
    assert {model["origen_de_los_consumos"] for model in models} == {"EXCEL"}
    assert not any(model["validado"] for model in models)
    first = models[0]
    assert (first["codigo"], first["cuero_m2_por_unidad"], first["forro_id"], first["herrajes_usd_por_unidad"]) == (
        "MOD-0001", "0.25", "MAT-FO02", "2")
    # A missing consumption stays NULL instead of becoming 0 (lagarto/yacaré rows).
    assert sum(model["cuero_m2_por_unidad"] is None for model in models) == 7


def test_seed_revision_renders_valid_postgresql_inserts_and_reverses(monkeypatch, seed):
    executed = []
    monkeypatch.setitem(sys.modules, "alembic", SimpleNamespace(op=SimpleNamespace(execute=executed.append)))
    revision = runpy.run_path(str(BACKEND / "migrations" / "versions" / "0004_semillas_v3.py"))
    assert revision["down_revision"] == "0003_der_v3"
    revision["upgrade"]()
    assert len(executed) == sum(EXPECTED_COUNTS.values())
    dialect = postgresql.dialect()
    sql = [str(statement.compile(dialect=dialect, compile_kwargs={"literal_binds": True})) for statement in executed]
    assert all(statement.startswith("INSERT INTO costos.") for statement in sql)
    assert all("public." not in statement for statement in sql)
    material = next(statement for statement in sql if statement.startswith("INSERT INTO costos.material "))
    assert "(SELECT costos.etapa.id" in material and "= 'CUERO'" in material
    executed.clear()
    revision["downgrade"]()
    assert len(executed) == sum(EXPECTED_COUNTS.values())
    first_deleted = str(executed[0].compile(dialect=dialect, compile_kwargs={"literal_binds": True}))
    last_deleted = str(executed[-1].compile(dialect=dialect, compile_kwargs={"literal_binds": True}))
    assert first_deleted.startswith("DELETE FROM costos.gasto_periodo")
    assert last_deleted.startswith("DELETE FROM costos.etapa")
