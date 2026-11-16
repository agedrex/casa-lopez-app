"""The materials of the grid that a supplier really provides (`proveedor_material`): set as a whole, never deleted."""

from sqlalchemy import func, select

from backend.models import ProveedorMaterial

from test_proveedor_productos import como, make_supplier  # noqa: F401
from test_costos_fijos_correccion_integration import api  # noqa: E402,F401

TELA = "MAT-FO02"
FLEX = "MAT-FL01"


def test_pg_a_supplier_starts_without_materials_and_the_list_is_set_as_a_whole(api):
    como("admin")
    code = make_supplier(api)
    assert api.get(f"/proveedores/{code}/provee").json() == []
    response = api.post(f"/proveedores/{code}/provee", json={"materiales": [TELA]})
    assert response.status_code == 200, response.text
    assert response.json() == [TELA]
    assert api.get(f"/proveedores/{code}/provee").json() == [TELA]


def test_pg_taking_a_material_off_marks_it_inactive_and_deletes_nothing(api):
    como("admin")
    code = make_supplier(api)
    api.post(f"/proveedores/{code}/provee", json={"materiales": [TELA]})
    assert api.post(f"/proveedores/{code}/provee", json={"materiales": []}).json() == []
    assert api.session.scalar(select(func.count()).select_from(ProveedorMaterial)) == 1
    assert api.post(f"/proveedores/{code}/provee", json={"materiales": [TELA]}).json() == [TELA]
    assert api.session.scalar(select(func.count()).select_from(ProveedorMaterial)) == 1


def test_pg_an_unknown_material_is_refused_and_nothing_changes(api):
    como("admin")
    code = make_supplier(api)
    response = api.post(f"/proveedores/{code}/provee", json={"materiales": [TELA, "MAT-NOPE"]})
    assert response.status_code == 422 and "MAT-NOPE" in response.text
    assert api.get(f"/proveedores/{code}/provee").json() == []


def test_pg_only_the_admin_reads_and_writes(api):
    como("admin")
    code = make_supplier(api)
    for role in ("gerente", "taller"):
        como(role)
        assert api.get(f"/proveedores/{code}/provee").status_code == 403
        assert api.post(f"/proveedores/{code}/provee", json={"materiales": []}).status_code == 403
