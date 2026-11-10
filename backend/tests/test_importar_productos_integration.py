"""The product importer against disposable PostgreSQL (skipped without TEST_DATABASE_URL).

Each test runs inside an outer transaction that is rolled back, so the seeded database stays untouched.
The rows are synthetic but use real seed v3 models: the seed links `modelo.fila_excel_viejo` 22 to 347 to the Excel rows.
"""

import importlib.util
from pathlib import Path

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend import servicios
from backend.models import Color, Material, Modelo, Producto

_spec = importlib.util.spec_from_file_location("importar_productos", Path(__file__).parents[1] / "scripts" / "importar_productos.py")
ip = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ip)

ESTANDAR = "Estandar (Anilina Fina Lisa - C Arena)"


def fila(**cambios):
    base = {
        "fila": 22, "nombre": "Portafolio Simple Ch.", "modelo": 6, "tipo_cuero": 1, "cuero": ESTANDAR,
        "b": None, "c": None, "d": None, "e": None, "errores": [], "comentarios": [],
    }
    return {**base, **cambios}


FILAS = [
    fila(fila=22, modelo=6),
    fila(fila=23, modelo=7, nombre="Billetera  doble", tipo_cuero=2, cuero="Carpincho", b="Fabián"),
    fila(fila=24, modelo=8, nombre="Cartera lagarto", tipo_cuero=3, cuero="lagarto", errores=["K", "L"]),
    fila(fila=94, modelo=1915, nombre=None, tipo_cuero="#VALUE!", cuero="#VALUE!", errores=["I", "K"]),  # no model in the seed
    fila(fila=2, modelo=99, nombre="Fila fuera del bloque"),  # "fila 2" must never be confused with "fila 22"
]


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


def importar(session, filas=FILAS, escribir=True):
    return ip.importar(session, ip.planificar(filas), escribir)


def productos(session):
    return {
        int(ip.MARCA_FILA.search(p.nota).group(1)): p
        for p in session.scalars(select(Producto).where(Producto.nota.like(f"{ip.MARCA} fila %")))
    }


def cantidad(session, tabla):
    return session.scalar(select(func.count()).select_from(tabla))


def test_it_creates_one_product_per_row_with_a_model_and_lists_the_rest(session):
    antes = cantidad(session, Producto)
    resumen = importar(session)
    assert [f.fila for f in resumen.a_crear] == [22, 23, 24]
    assert sorted(f.fila for f in resumen.sin_modelo) == [2, 94]
    assert cantidad(session, Producto) == antes + 3
    creados = productos(session)
    assert sorted(creados) == [22, 23, 24]
    for fila_excel, p in creados.items():
        modelo = session.get(Modelo, p.modelo_id)
        assert modelo.fila_excel_viejo == fila_excel
        assert p.estado_del_ciclo == "EN_DEFINICION" and p.es_kit is False
        assert p.quien_lo_confecciona is None and p.fecha_de_alta is None
        assert p.codigo.startswith("PRD-")


def test_leather_color_name_and_note_are_stored_as_decided(session):
    importar(session)
    creados = productos(session)
    estandar = session.scalar(select(Material.id).where(Material.codigo == "MAT-CU01"))
    carpincho = session.scalar(select(Material.id).where(Material.codigo == "MAT-CU02"))
    assert creados[22].cuero_id == estandar and creados[23].cuero_id == carpincho
    assert session.get(Color, creados[22].color_id).nombre == "Arena"
    assert creados[23].color_id is None
    assert creados[23].nombre_propio == "Billetera  doble"  # the original text, inner spaces included
    assert creados[23].nota == "IMPORTADO-EXCEL fila 23 | B=Fabián"
    lagarto = creados[24]
    assert lagarto.cuero_id is None  # crear_producto rejects non quotable leather: the product goes without it
    assert lagarto.nota == (
        "IMPORTADO-EXCEL fila 24 | REVISAR: error en origen (K, L) | REVISAR: cuero lagarto no cotizable (pendiente Gerardo)")


def test_the_color_is_created_once_following_the_repo_pattern(session):
    antes = cantidad(session, Color)
    importar(session, [fila(fila=22), fila(fila=23, modelo=7)])
    assert cantidad(session, Color) == antes + 1
    arena = session.scalar(select(Color).where(Color.nombre == "Arena"))
    assert arena.codigo.startswith("COL-") and arena.nota == "IMPORTADO-EXCEL color"


def test_an_existing_color_is_reused_not_created_again(session):
    servicios.crear_color(session, nombre="Arena", nota=None)
    antes = cantidad(session, Color)
    resumen = importar(session)
    assert resumen.colores_nuevos == [] and cantidad(session, Color) == antes


def test_a_second_run_creates_nothing(session):
    importar(session)
    despues = (cantidad(session, Producto), cantidad(session, Color))
    segunda = importar(session)
    assert segunda.a_crear == [] and sorted(f.fila for f in segunda.existentes) == [22, 23, 24]
    assert sorted(f.fila for f in segunda.sin_modelo) == [2, 94] and segunda.colores_nuevos == []
    assert (cantidad(session, Producto), cantidad(session, Color)) == despues


def test_row_22_is_not_taken_for_row_2_when_deciding_what_exists(session):
    importar(session, [fila(fila=22)])
    resumen = importar(session, [fila(fila=22), fila(fila=23, modelo=7)])
    assert [f.fila for f in resumen.existentes] == [22] and [f.fila for f in resumen.a_crear] == [23]


def test_a_dry_run_counts_but_writes_nothing(session):
    productos_antes, colores_antes = cantidad(session, Producto), cantidad(session, Color)
    simulada = importar(session, escribir=False)
    assert (cantidad(session, Producto), cantidad(session, Color)) == (productos_antes, colores_antes)
    assert not simulada.escribio and simulada.verificado
    assert [f.fila for f in simulada.a_crear] == [22, 23, 24] and simulada.colores_nuevos == ["Arena"]
    real = importar(session)
    assert [f.fila for f in real.a_crear] == [f.fila for f in simulada.a_crear]
