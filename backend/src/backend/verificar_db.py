"""Safe staging inspection; optional writes are always rolled back."""

import argparse
import os

from backend.database import create_database_engine
from backend.db_verification import DOMAIN_TABLES, SEED_COUNTS, inspect_database, run_write_probes


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prueba-escritura", action="store_true", help="Run constraint probes with a final rollback.")
    options = parser.parse_args(argv)
    environment = os.environ.get("RAILWAY_ENVIRONMENT_NAME")
    if environment is not None and environment != "staging":
        # Do not echo arbitrary environment content supplied to the process.
        print("Environment: refused")
        print("FALLA: staging environment required.")
        return 1
    print(f"Environment: {'staging' if environment == 'staging' else 'local'}")
    engine = None
    exit_code = 1
    try:
        engine = create_database_engine()
        with engine.connect() as connection:
            transaction = connection.begin()
            try:
                result = inspect_database(connection)
                # Inspection data is bounded to known schema names and revision syntax.
                revision = result["revision"]
                if not isinstance(revision, str) or not revision.replace("_", "").isalnum():
                    raise ValueError("Unexpected revision.")
                tables = result["tables"]
                if any(name not in DOMAIN_TABLES | {"alembic_version"} for name in tables):
                    print("FALLA: unexpected application tables.")
                    return 1
                print(f"Alembic revision: {revision}")
                print("Tables: " + ", ".join(tables))
                checks = [("revision", revision == "0004_semillas_v3"),
                          ("tables", set(tables) - {"alembic_version"} == DOMAIN_TABLES)]
                for name, expected in SEED_COUNTS.items():
                    actual = result["counts"][name]
                    print(f"Seed count {name}: {actual}")
                    checks.append((name, actual == expected))
                checks.append(("seed_codes_and_blocked_exotics", result["seeds_valid"]))
                if options.prueba_escritura:
                    checks.extend(run_write_probes(connection))
                for name, passed in checks:
                    print(f"{'OK' if passed else 'FALLA'}: {name}")
                exit_code = 0 if all(passed for _, passed in checks) else 1
            finally:
                transaction.rollback()
    except Exception:
        print("FALLA: database verification failed. Connection details are hidden.")
    finally:
        if engine is not None:
            try:
                engine.dispose()
            except Exception:
                # A failed cleanup must never expose driver exceptions.
                print("FALLA: database cleanup failed.")
                exit_code = 1
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
