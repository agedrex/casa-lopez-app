"""Last lot code per workshop (Talleres grid, column "Último lote").

Pure checks first (no database); the HTTP flow runs against the disposable local PostgreSQL
(skipped without TEST_DATABASE_URL, like test_fabricacion.py).
"""

from decimal import Decimal as D
from types import SimpleNamespace

from test_api_integration import api, dolar_nuevo, producto  # noqa: F401  (fixture and helpers)
from test_fabricacion import lote_nuevo, taller_nuevo

from backend import servicios

ZERO = D("0")


def test_last_lot_code_is_the_first_one_seen_per_workshop_in_newest_first_order():
    filas = [(2, "LOT-0005"), (1, "LOT-0003"), (2, "LOT-0004"), (1, "LOT-0001")]
    assert servicios._ultimo_lote_por_taller(filas) == {1: "LOT-0003", 2: "LOT-0005"}
    assert servicios._ultimo_lote_por_taller([]) == {}


def test_workshop_dict_exposes_the_last_lot_code_and_keeps_the_existing_keys():
    taller = SimpleNamespace(
        id=7, codigo="TAL-0007", nombre="Taller", cuit=None, telefono=None, direccion=None, contacto=None,
        activo=True, nota=None,
    )
    con_lotes = servicios._taller_a_dict(taller, {7: (2, D("12"), D("13000"), None, "LOT-0002")})
    assert con_lotes["ultimo_lote_codigo"] == "LOT-0002"
    assert {"lotes", "unidades", "ultimo_lote", "cobro_total_ars"} <= con_lotes.keys()
    assert con_lotes["lotes"] == 2 and con_lotes["cobro_total_ars"] == D("13000")
    sin_lotes = servicios._taller_a_dict(taller, {})
    assert sin_lotes["ultimo_lote_codigo"] is None and sin_lotes["lotes"] == 0 and sin_lotes["ultimo_lote"] is None


def test_the_grid_shows_the_code_of_the_most_recent_lot_of_each_workshop(api):  # noqa: F811
    codigo = producto(api, quien_lo_confecciona="EXTERNA")["codigo"]
    taller_nuevo(api)
    lote_nuevo(api, codigo, taller="TAL-0004", fecha_de_envio="2026-10-08")  # LOT-0001: newest by date
    lote_nuevo(api, codigo, taller="TAL-0004", fecha_de_envio="2026-10-01")  # LOT-0002: newer id, older date
    lote_nuevo(api, codigo, taller="TAL-0004", fecha_de_envio="2026-10-08")  # LOT-0003: same date, newest id
    lote_nuevo(api, codigo, taller="TAL-0001", fecha_de_envio="2026-09-01")  # LOT-0004
    lista = {t["codigo"]: t for t in api.get("/talleres").json()}
    assert lista["TAL-0004"]["ultimo_lote_codigo"] == "LOT-0003" and lista["TAL-0004"]["ultimo_lote"] == "2026-10-08"
    assert lista["TAL-0001"]["ultimo_lote_codigo"] == "LOT-0004"
    assert lista["TAL-0002"]["ultimo_lote_codigo"] is None and lista["TAL-0002"]["lotes"] == 0
    assert api.get("/talleres/TAL-0004").json()["ultimo_lote_codigo"] == "LOT-0003"
