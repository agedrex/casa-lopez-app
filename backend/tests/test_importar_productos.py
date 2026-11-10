"""Pure part of the product importer (scripts/importar_productos.py): the plan, its notes, the refusals and the summary.

No database and no openpyxl here: the plan is a function of the rows already read from the Excel.
"""

import importlib.util
from datetime import datetime
from pathlib import Path

import pytest

RUTA = Path(__file__).parents[1] / "scripts" / "importar_productos.py"
_spec = importlib.util.spec_from_file_location("importar_productos", RUTA)
ip = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ip)

ESTANDAR = "Estandar (Anilina Fina Lisa - C Arena)"


def fila(**cambios):
    """A healthy row 22 (Portafolio Simple Ch.) as the reader returns it; tests override what they exercise."""
    base = {
        "fila": 22, "nombre": "Portafolio Simple Ch.", "modelo": 6, "tipo_cuero": 1, "cuero": ESTANDAR,
        "b": None, "c": None, "d": None, "e": None, "errores": [], "comentarios": [],
    }
    return {**base, **cambios}


def una(**cambios):
    return ip.planificar([fila(**cambios)]).filas[0]


def partes(nota):
    return nota.split(" | ")


# --- S7: the name is the original text of column F, stripped and nothing else -------------------------------

def test_the_name_is_stripped_but_never_corrected_or_split():
    original = "Mantel Individual 48 x 33  (0,35 x 0,50 - 30/07/19 se toma para costo) Cratera "
    assert una(nombre=original).nombre_propio == original.strip()
    assert una(nombre="  Billetera de hombre 2681:         0,19 ").nombre_propio == "Billetera de hombre 2681:         0,19"


def test_a_row_without_a_name_gets_a_null_name_and_a_review_mark():
    plan = una(fila=94, nombre=None, modelo=1915, tipo_cuero="#VALUE!", cuero="#VALUE!", errores=["I", "K"])
    assert plan.nombre_propio is None
    assert "REVISAR: sin nombre" in partes(plan.nota)
    assert una(nombre="   ").nombre_propio is None


# --- S6: leather by type -------------------------------------------------------------------------------------

@pytest.mark.parametrize("tipo, codigo", [(1, "MAT-CU01"), (2, "MAT-CU02"), (5, "MAT-CU05"), (6, "MAT-CU06")])
def test_quotable_leathers_map_to_their_material(tipo, codigo):
    plan = una(tipo_cuero=tipo)
    assert plan.cuero == codigo and plan.cuero_nulo is None
    assert not any("cuero" in parte for parte in partes(plan.nota)[1:])


def test_a_float_type_from_the_workbook_is_read_as_the_same_number():
    assert una(tipo_cuero=2.0).cuero == "MAT-CU02"


@pytest.mark.parametrize("tipo, nombre", [(3, "lagarto"), (4, "yacaré")])
def test_lagarto_and_yacare_are_imported_without_leather_and_flagged(tipo, nombre):
    plan = una(tipo_cuero=tipo)
    assert plan.cuero is None
    assert plan.cuero_nulo == "cuero no cotizable"
    assert f"REVISAR: cuero {nombre} no cotizable (pendiente Gerardo)" in partes(plan.nota)


@pytest.mark.parametrize("tipo", [None, "", "#VALUE!"])
def test_an_empty_or_failed_leather_type_is_null_and_flagged(tipo):
    plan = una(tipo_cuero=tipo)
    assert plan.cuero is None and plan.cuero_nulo == "sin tipo de cuero"
    assert "REVISAR: sin tipo de cuero" in partes(plan.nota)


def test_an_unknown_leather_type_is_null_and_flagged_instead_of_guessed():
    plan = una(tipo_cuero=7)
    assert plan.cuero is None and plan.cuero_nulo == "tipo de cuero desconocido"
    assert "REVISAR: tipo de cuero desconocido (7)" in partes(plan.nota)


# --- S3: color by product, only from a clear pattern ---------------------------------------------------------

def test_the_color_comes_from_the_dash_c_pattern_of_the_leather_text():
    assert una().color == "Arena"
    assert una(cuero="Estandar (Anilina Fina Lisa - C  Negro )").color == "Negro"
    assert una(cuero="Estandar (Anilina Fina Lisa - C Azul Marino)").color == "Azul Marino"


@pytest.mark.parametrize("texto", [
    "Carpincho", "yacaré overo", "lagarto", "Camuflado/cuero vaca con pelo", "#VALUE!", None,
    "Estandar (Anilina Fina Lisa)", "Estandar (Anilina Fina Lisa - Arena)", "Cuadro C Arena",
])
def test_without_the_pattern_there_is_no_color(texto):
    assert una(cuero=texto).color is None


# --- S2: rows with errors are imported, flagged and never dropped --------------------------------------------

def test_error_columns_are_found_by_text_starting_with_hash_in_sheet_order():
    celdas = [("A", 1), ("I", "#VALUE!"), ("J", 0.5), ("K", "#VALUE!"), ("X", "#REF!"), ("Y", "no es #error"), ("Z", None)]
    assert ip.columnas_con_error(celdas) == ["I", "K", "X"]


def test_a_row_with_errors_is_planned_with_a_review_mark_naming_the_columns():
    plan = ip.planificar([fila(fila=31, nombre="Cartera Peter CH.", tipo_cuero=4, errores=["K", "L", "AF"])])
    assert [f.fila for f in plan.filas] == [31]
    assert "REVISAR: error en origen (K, L, AF)" in partes(plan.filas[0].nota)
    assert ip.planificar([fila()]).filas[0].revisar == ()


# --- S8: notes, in order, as text ----------------------------------------------------------------------------

def test_the_note_starts_with_the_idempotency_mark():
    assert partes(una(fila=22).nota)[0] == "IMPORTADO-EXCEL fila 22"
    assert una(fila=22).nota == "IMPORTADO-EXCEL fila 22"  # a healthy row has nothing else to say


def test_the_note_orders_mark_review_b_d_c_e_and_comments():
    plan = una(
        fila=53, tipo_cuero=4, errores=["K"], b="Fabian, Adrián", d="barba", c="esta", e=datetime(2024, 11, 4),
        comentarios=[("AE53", "Usuario de Windows:\n02/02/2017\nSanchez\n$ 1,000 pidió\npagamos $ 750")],
    )
    assert partes(plan.nota) == [
        "IMPORTADO-EXCEL fila 53",
        "REVISAR: error en origen (K)",
        "REVISAR: cuero yacaré no cotizable (pendiente Gerardo)",
        "B=Fabian, Adrián", "D=barba", "C=esta", "E=2024-11-04",
        "Comentario AE53: Usuario de Windows: 02/02/2017 Sanchez $ 1,000 pidió pagamos $ 750",
    ]


def test_empty_b_d_c_are_left_out_and_values_are_kept_as_they_are():
    assert una(b="  ", c=None, d="").nota == "IMPORTADO-EXCEL fila 22"
    assert partes(una(b="lucio   5/1/23 ").nota)[1] == "B=lucio 5/1/23"  # only spaces are normalized
    assert partes(una(d=0).nota)[1] == "D=0"


def test_column_e_is_an_iso_date_when_it_is_a_date_and_the_raw_value_when_it_is_not():
    assert partes(una(e=datetime(2026, 8, 25, 0, 0)).nota)[-1] == "E=2026-08-25"
    assert partes(una(fila=204, e=1).nota)[-1] == "E=1"
    assert partes(una(fila=205, e=2.0).nota)[-1] == "E=2"
    assert partes(una(e="sin fecha").nota)[-1] == "E=sin fecha"
    assert una(e=None).nota == "IMPORTADO-EXCEL fila 22"


def test_cell_comments_become_one_text_each_in_the_given_order():
    plan = una(fila=140, comentarios=[("R140", "GERARDO:\n2016-03-21\nMica:  ,07 x 012 a u$ \n"), ("AE140", "otro")])
    assert partes(plan.nota)[1:] == ["Comentario R140: GERARDO: 2016-03-21 Mica: ,07 x 012 a u$", "Comentario AE140: otro"]


def test_a_repeated_model_is_flagged_on_every_row_that_shares_it():
    plan = ip.planificar([fila(fila=10, modelo=514), fila(fila=31, modelo="514"), fila(fila=40, modelo=515)])
    marcadas = ["REVISAR: modelo repetido" in partes(f.nota) for f in plan.filas]
    assert marcadas == [True, True, False]


def test_a_variant_code_is_read_as_text_and_is_not_the_base_model():
    plan = ip.planificar([fila(fila=10, modelo="514/1"), fila(fila=11, modelo=514)])
    assert not any("modelo repetido" in f.nota for f in plan.filas)


# --- S9: kits and several units are flagged, not built -------------------------------------------------------

@pytest.mark.parametrize("nombre", ["Kit Monederos (2) y Portaanteojos (1)", "Señalador (costo x 5 unidades)", "KIT escritorio"])
def test_names_with_kit_or_costo_x_are_flagged(nombre):
    plan = una(nombre=nombre)
    assert "REVISAR: posible kit o costeo por varias unidades" in partes(plan.nota)


def test_other_names_are_not_flagged_as_kits():
    assert not una(nombre="Cartera Kitty Hawk").revisar
    assert not una(nombre="Cartera costo").revisar


def test_the_fixed_fields_of_the_product_are_the_ones_the_user_decided():
    assert ip.ESTADO_DEL_CICLO == "EN_DEFINICION"
    assert (ip.QUIEN_LO_CONFECCIONA, ip.FECHA_DE_ALTA, ip.ES_KIT) == (None, None, False)


# --- S10: idempotence ----------------------------------------------------------------------------------------

def test_already_imported_rows_are_read_from_the_notes_by_exact_row_number():
    notas = ["IMPORTADO-EXCEL fila 22 | B=Fabián", "IMPORTADO-EXCEL fila 2", None, "nota a mano", "x | IMPORTADO-EXCEL fila 140 | y"]
    assert ip.filas_importadas(notas) == {22, 2, 140}
    assert 2 not in ip.filas_importadas(["IMPORTADO-EXCEL fila 22"])  # "fila 2" is not a prefix match of "fila 22"
    assert 22 not in ip.filas_importadas(["IMPORTADO-EXCEL fila 2"])


# --- S1/S12: the plan and its summary ------------------------------------------------------------------------

def test_the_summary_counts_leather_color_review_reasons_and_null_leather_reasons():
    plan = ip.planificar([
        fila(fila=22, modelo=1),
        fila(fila=23, modelo=2, tipo_cuero=2, cuero="Carpincho"),
        fila(fila=24, modelo=3, tipo_cuero=3, cuero="lagarto", errores=["K"]),
        fila(fila=25, modelo=4, tipo_cuero=None, cuero="#VALUE!", errores=["I", "K"]),
        fila(fila=26, nombre="Kit chico", modelo=514), fila(fila=27, modelo=514),
    ])
    assert plan.por_cuero == {"MAT-CU01": 3, "MAT-CU02": 1, "(sin cuero)": 2}
    assert plan.por_color == {"Arena": 3, "(sin color)": 3}
    assert plan.por_revisar == {
        "error en origen": 2, "cuero no cotizable": 1, "sin tipo de cuero": 1, "modelo repetido": 2,
        "posible kit o costeo por varias unidades": 1,
    }
    assert plan.por_cuero_nulo == {"cuero no cotizable": 1, "sin tipo de cuero": 1}
    assert plan.con_nombre == 6


def test_the_printed_summary_without_a_database_says_it_is_unverified(capsys):
    plan = ip.planificar([fila(fila=22), fila(fila=24, tipo_cuero=3, cuero="lagarto")])
    ip.imprimir(ip.resumen_sin_base(plan))
    salida = capsys.readouterr().out
    assert "sin verificar contra la base" in salida
    assert "Filas con nombre: 2" in salida
    assert "MAT-CU01: 1" in salida and "Arena: 1" in salida
    assert "cuero no cotizable: 1" in salida
    assert "No se escribió nada" in salida


# --- S11: safety ---------------------------------------------------------------------------------------------

@pytest.fixture
def sin_base(monkeypatch):
    """Any attempt to open the database or the workbook fails the test: a refusal must happen before."""
    def prohibido(*_, **__):
        raise AssertionError("se intentó abrir la base de datos o el Excel")
    monkeypatch.setattr(ip, "create_database_engine", prohibido)
    monkeypatch.setattr(ip, "leer_excel", prohibido)
    monkeypatch.delenv("RAILWAY_ENVIRONMENT_NAME", raising=False)
    monkeypatch.delenv("DATABASE_URL", raising=False)


@pytest.mark.parametrize("argumentos", [
    ["--confirmar"], ["--entorno", "staging"], ["--entorno", "produccion", "--confirmar"],
    ["--entorno", "local", "--confirmar"], ["--entorno", "produccion"],
])
def test_it_refuses_to_write_without_both_flags(argumentos, sin_base, capsys):
    assert ip.main(["libro.xlsx", *argumentos]) == 2
    salida = capsys.readouterr()
    assert "staging" in salida.err and "--confirmar" in salida.err
    assert salida.out == ""


def test_it_refuses_a_railway_environment_that_is_not_staging(sin_base, monkeypatch, capsys):
    monkeypatch.setenv("RAILWAY_ENVIRONMENT_NAME", "production-secreto")
    assert ip.main(["libro.xlsx", "--entorno", "staging", "--confirmar"]) == 2
    assert "production-secreto" not in capsys.readouterr().err  # arbitrary environment text is never echoed


def test_writing_without_database_url_stops_before_reading_anything(sin_base, capsys):
    assert ip.main(["libro.xlsx", "--entorno", "staging", "--confirmar"]) == 1
    assert "DATABASE_URL" in capsys.readouterr().err


def test_the_default_is_a_dry_run_that_reads_the_workbook_without_a_database(sin_base, monkeypatch, capsys):
    monkeypatch.setattr(ip, "leer_excel", lambda ruta: [fila(), fila(fila=24, tipo_cuero=3)])
    assert ip.main(["libro.xlsx"]) == 0
    salida = capsys.readouterr()
    assert "sin verificar contra la base" in salida.out
    assert "Filas con nombre: 2" in salida.out
    assert "postgres" not in salida.out + salida.err  # no URL or credentials, ever


def test_outside_the_backend_project_it_only_offers_the_dry_run(sin_base, monkeypatch, capsys):
    monkeypatch.setattr(ip, "HAY_BACKEND", False)
    assert ip.main(["libro.xlsx", "--entorno", "staging", "--confirmar"]) == 2
    assert "backend/" in capsys.readouterr().err
    monkeypatch.setattr(ip, "leer_excel", lambda ruta: [fila()])
    assert ip.main(["libro.xlsx"]) == 0


def test_a_missing_workbook_is_reported_without_a_traceback(sin_base, monkeypatch, capsys):
    monkeypatch.undo()
    assert ip.main(["no-existe.xlsx"]) == 2
    assert "no-existe.xlsx" in capsys.readouterr().err


def test_openpyxl_is_only_imported_by_the_reader():
    codigo = RUTA.read_text(encoding="utf-8")
    cabecera = codigo.split("def leer_excel", 1)[0]
    assert "import openpyxl" not in cabecera and "from openpyxl" not in cabecera
    assert "import openpyxl" in codigo
