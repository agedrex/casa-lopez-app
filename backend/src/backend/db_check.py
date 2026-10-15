"""Internal, read-only connection check: python -m backend.db_check."""

import sys

from sqlalchemy import text

from backend.database import DatabaseConfigurationError, create_database_engine


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
