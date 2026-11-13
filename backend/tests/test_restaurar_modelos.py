import importlib.util
import json
from pathlib import Path

import pytest

RUTA = Path(__file__).resolve().parents[1] / "scripts" / "restaurar_modelos_staging.py"
spec = importlib.util.spec_from_file_location("restaurar_modelos_staging", RUTA)
modulo = importlib.util.module_from_spec(spec)
spec.loader.exec_module(modulo)


def _seed():
    tablas = json.loads(modulo.SEED_FILE.read_text(encoding="utf-8"))["tables"]
    return next(t for t in tablas if t["name"] == "modelo")


def test_only_the_missing_codes_are_returned():
    seed = _seed()
    indice = [c["name"] for c in seed["columns"]].index("codigo")
    todos = {v[indice] for v in seed["rows"]}
    assert len(modulo.faltantes(seed, set())) == len(seed["rows"])
    assert modulo.faltantes(seed, todos) == []
    assert len(modulo.faltantes(seed, {"MOD-0012", "MOD-0070"})) == len(seed["rows"]) - 2


@pytest.mark.parametrize("entorno", [None, "production", "local"])
def test_refuses_anything_but_staging(monkeypatch, entorno):
    if entorno is None:
        monkeypatch.delenv("RAILWAY_ENVIRONMENT_NAME", raising=False)
    else:
        monkeypatch.setenv("RAILWAY_ENVIRONMENT_NAME", entorno)
    assert modulo.main(["--confirmar"]) == 2
