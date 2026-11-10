"""Pin the Railway config-as-code file: migrate before each deploy, check health, never override the start command."""

import tomllib
from pathlib import Path


RAILWAY_TOML = Path(__file__).parents[1] / "railway.toml"


def load_deploy_section():
    with RAILWAY_TOML.open("rb") as handle:
        return tomllib.load(handle)["deploy"]


def test_pre_deploy_command_upgrades_the_database_to_head():
    commands = load_deploy_section()["preDeployCommand"]
    assert isinstance(commands, list) and len(commands) == 1
    assert commands[0].split() == ["uv", "run", "alembic", "upgrade", "head"]


def test_healthcheck_targets_the_api_health_route_with_a_timeout():
    deploy = load_deploy_section()
    assert deploy["healthcheckPath"] == "/api/health"
    assert isinstance(deploy["healthcheckTimeout"], int) and 0 < deploy["healthcheckTimeout"] <= 600


def test_start_command_stays_in_the_dashboard():
    with RAILWAY_TOML.open("rb") as handle:
        config = tomllib.load(handle)
    assert "startCommand" not in config.get("deploy", {})
    assert "startCommand" not in config.get("build", {})
    for overrides in config.get("environments", {}).values():
        assert "startCommand" not in overrides.get("deploy", {})
