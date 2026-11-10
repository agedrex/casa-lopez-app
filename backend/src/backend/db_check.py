"""Internal, read-only connection check: python -m backend.db_check."""

import sys
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError

from sqlalchemy import Engine, text

from backend.database import DatabaseConfigurationError, create_database_engine

# The health check answers within this budget even if the database hangs (Railway waits 120 s, a load balancer less).
HEALTH_TIMEOUT_SECONDS = 2.0
# Probes run off the request thread so a hung connect cannot hold the request; the driver's own connect_timeout
# (database.py) and the statement_timeout below bound how long a probe thread lives.
_probes = ThreadPoolExecutor(max_workers=4, thread_name_prefix="health-probe")


def _probe(engine: Engine) -> bool:
    with engine.connect() as connection:  # the context manager returns the connection even if the query fails
        connection.execute(text(f"SET LOCAL statement_timeout = {int(HEALTH_TIMEOUT_SECONDS * 1000)}"))
        return connection.execute(text("SELECT 1")).scalar_one() == 1


def database_responds(engine: Engine | None) -> bool:
    """True only if `SELECT 1` succeeds within HEALTH_TIMEOUT_SECONDS. Never raises and never reports why it failed."""
    if engine is None:
        return False
    try:
        return _probes.submit(_probe, engine).result(timeout=HEALTH_TIMEOUT_SECONDS)
    except (FutureTimeoutError, Exception):
        return False


def main() -> int:
    engine = None
    error_message = None
    try:
        engine = create_database_engine()
        with engine.connect() as connection:
            if connection.execute(text("SELECT 1")).scalar_one() != 1:
                raise RuntimeError
    except DatabaseConfigurationError as error:
        error_message = str(error)
    except Exception:
        error_message = "Database connection check failed."
    finally:
        if engine is not None:
            try:
                engine.dispose()
            except Exception:
                error_message = "Database connection check failed."
    if error_message:
        print(error_message, file=sys.stderr)
        return 1
    print("Database connection check succeeded.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
