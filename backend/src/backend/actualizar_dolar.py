"""Loads the BNA dollar quote once and exits: `python -m backend.actualizar_dolar`.

Meant for a scheduler (a Railway cron later; none is configured yet). It talks to the database directly through
DATABASE_URL, so it needs no HTTP token. Exit 0 when the quote was loaded or was already there, 1 otherwise,
with a short Spanish message on stderr that never carries the page, a URL or a connection string.
"""

import sys

from sqlalchemy.orm import Session

from backend import database, servicios


def main() -> int:
    try:
        engine = database.create_database_engine()
    except database.DatabaseConfigurationError as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1
    try:
        with Session(engine) as session:
            resultado = servicios.actualizar_dolar_bna(session)
    except servicios.FuenteNoDisponible as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1
    except Exception as error:  # noqa: BLE001 - the message may hold the connection string
        print(f"Error: no se pudo actualizar el dólar ({type(error).__name__}).", file=sys.stderr)
        return 1
    finally:
        engine.dispose()
    fecha = resultado["fecha"].strftime("%d/%m/%Y")
    valor = f"{resultado['ars_por_usd']:.2f}"
    if resultado["estado"] == "creado":
        print(f"Dólar BNA cargado: ${valor} al {fecha}.")
    else:
        print(f"El dólar BNA del {fecha} ya estaba cargado (${valor}).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
