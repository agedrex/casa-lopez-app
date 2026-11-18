"""Every field a request body accepts has a human name in the front (`front/lib/errores-campos.ts`).

A 422 is turned into Spanish there, with the name of the field as a person says it. A new field of a body without its label
would show up as «dato nuevo raro»: this test fails first.
"""

import inspect
import re
from pathlib import Path

from backend import api as api_module

from test_costos_fijos_correccion_integration import api  # noqa: E402,F401  (fixture)

LABELS = Path(__file__).parents[2] / "front" / "lib" / "errores-campos.ts"


def labelled_fields() -> set[str]:
    source = LABELS.read_text(encoding="utf-8")
    block = source.split("export const FIELD_LABELS", 1)[1].split("};", 1)[0]
    return set(re.findall(r"^\s+(\w+):", block, flags=re.MULTILINE))


def body_fields() -> dict[str, set[str]]:
    found: dict[str, set[str]] = {}
    for name, model in inspect.getmembers(api_module, inspect.isclass):
        if issubclass(model, api_module.Entrada) and model is not api_module.Entrada and model.__module__ == api_module.__name__:
            for field in model.model_fields:
                found.setdefault(field, set()).add(name)
    return found


def test_every_field_of_a_request_body_has_a_human_label_in_the_front():
    missing = {field: sorted(models) for field, models in body_fields().items() if field not in labelled_fields()}
    assert missing == {}, f"Add them to FIELD_LABELS in front/lib/errores-campos.ts: {missing}"


def test_the_label_table_is_not_empty_and_has_no_internal_names_as_text():
    source = LABELS.read_text(encoding="utf-8")
    block = source.split("export const FIELD_LABELS", 1)[1].split("};", 1)[0]
    texts = re.findall(r':\s*"([^"]+)"', block)
    assert len(texts) > 100 and not [text for text in texts if "_" in text]


def test_pg_a_422_from_the_api_has_the_shape_the_front_reads(api):
    from backend.auth import Usuario, get_verifier
    from backend.main import app

    app.dependency_overrides[get_verifier] = lambda: (lambda request: Usuario(id="a", role="admin"))
    issues = api.post("/modelos", json={"cuero_m2_por_unidad": "-1"}).json()["detail"]
    negative = next(i for i in issues if i["loc"][-1] == "cuero_m2_por_unidad")
    assert negative["loc"][0] == "body" and negative["type"] == "greater_than_equal" and negative["ctx"] == {"ge": 0}
    assert all({"loc", "type", "msg"} <= set(i) for i in issues)
