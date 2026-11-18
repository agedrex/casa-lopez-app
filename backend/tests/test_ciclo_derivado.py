"""S8 (flujo-modelos-lotes-precio): the lifecycle label is derived at read time, never written. Pure tests."""

import pytest
from sqlalchemy import select
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import aliased

from backend import servicios
from backend.models import LOT_STATES, Material, Producto

CICLO = ["EN_DEFINICION", "COTIZADO", "EN_PRODUCCION", "PRODUCIDO"]
efectivo = servicios.estado_del_ciclo_efectivo


def test_the_cycle_is_ranked_from_definition_to_produced():
    assert list(servicios.CICLO_DE_VIDA) == CICLO


def test_without_facts_the_stored_value_stays():
    for guardado in CICLO:
        assert efectivo(guardado, con_precio=False, en_lote_abierto=False, en_lote_terminado=False) == guardado


def test_a_saved_sale_price_makes_it_quoted():
    assert efectivo("EN_DEFINICION", con_precio=True, en_lote_abierto=False, en_lote_terminado=False) == "COTIZADO"


def test_a_line_in_an_open_lot_makes_it_in_production_even_without_a_price():
    assert efectivo("EN_DEFINICION", con_precio=False, en_lote_abierto=True, en_lote_terminado=False) == "EN_PRODUCCION"


def test_a_line_in_a_finished_lot_makes_it_produced():
    assert efectivo("EN_DEFINICION", con_precio=False, en_lote_abierto=False, en_lote_terminado=True) == "PRODUCIDO"


def test_the_highest_fact_wins_when_several_hold():
    assert efectivo("EN_DEFINICION", con_precio=True, en_lote_abierto=True, en_lote_terminado=False) == "EN_PRODUCCION"
    assert efectivo("EN_DEFINICION", con_precio=True, en_lote_abierto=True, en_lote_terminado=True) == "PRODUCIDO"


def test_the_stored_value_wins_when_it_is_higher_than_the_derived_one():
    assert efectivo("PRODUCIDO", con_precio=True, en_lote_abierto=False, en_lote_terminado=False) == "PRODUCIDO"
    assert efectivo("EN_PRODUCCION", con_precio=True, en_lote_abierto=False, en_lote_terminado=False) == "EN_PRODUCCION"


def test_an_unknown_stored_value_is_kept_when_nothing_is_derived():
    assert efectivo("ACTIVO", con_precio=False, en_lote_abierto=False, en_lote_terminado=False) == "ACTIVO"


def test_the_finished_states_are_the_ones_of_the_variable_cost_criterion():
    assert servicios.ESTADOS_TERMINADOS == ("LISTA", "CERRADA") and set(servicios.ESTADOS_TERMINADOS) <= set(LOT_STATES)


def _sql(**filtros):
    cuero = aliased(Material)
    consulta = servicios._filtrar_productos(select(Producto.id).select_from(Producto), cuero, q=None, categoria=None, **filtros)
    compilada = consulta.compile(dialect=postgresql.dialect())
    return str(compilada), compilada.params


@pytest.mark.parametrize("estado", CICLO)
def test_the_state_filter_uses_the_shared_exists_expressions(estado):
    sql, params = _sql(estado=estado)
    assert "EXISTS" in sql and "precio_venta" in sql and "orden_item" in sql and "orden_fabricacion" in sql
    assert estado in params.values()


def test_without_the_state_filter_the_query_does_not_read_prices_nor_lots():
    sql, _ = _sql()
    assert "EXISTS" not in sql and "precio_venta" not in sql and "orden_item" not in sql
