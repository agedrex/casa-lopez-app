"""Import the PRODUCTS of the real Casa López Excel (sheet Marroquineria1, rows 22 to 347) into the DER v3 `producto` table.

Dry-run (default, writes nothing; without DATABASE_URL it only reads the Excel and says what it could not verify):

    uv run --with openpyxl python -I backend/scripts/importar_productos.py "/path/to/COSTOS1 en vigencia al 01-09-2026.xlsx"

Write (staging or production; needs DATABASE_URL and both flags; `--entorno` must equal RAILWAY_ENVIRONMENT_NAME when it exists,
and `--entorno production` is only accepted from inside the production container):

    DATABASE_URL=... uv run --with openpyxl python -I backend/scripts/importar_productos.py "/path/to/COSTOS1 ....xlsx" \
        --entorno staging --confirmar

One product per row with a name (plus rows without one that still carry a model code, which are flagged). Each product is linked to
its seed v3 `modelo` by `modelo.fila_excel_viejo == Excel row`; a row without a model creates nothing and is listed. Everything is
created through `backend.servicios.crear_producto`. Rows with errors, unquotable leather, repeated models, etc. are imported with a
`REVISAR:` text in `nota`; nothing is dropped silently. The `nota` also carries the columns without a header (B, C, D, E) and the
cell comments, as TEXT only (never as current prices). A second run creates nothing: each product carries
`IMPORTADO-EXCEL fila <N>` in its note.

The workbook is untrusted data: openpyxl is not a backend dependency, it is imported lazily and only by `leer_excel`, and the
planning part (`planificar`) is a pure function of the rows already read, so it is tested without a workbook or a database.
Nothing is ever deleted or updated in place here (the project forbids it).
"""

import argparse
import os
import re
import sys
from collections import Counter
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

try:
    from sqlalchemy import select
    from sqlalchemy.orm import Session

    from backend import servicios
    from backend.database import DatabaseConfigurationError, create_database_engine, get_database_url
    from backend.models import Color, Modelo, Producto
    HAY_BACKEND = True
except ModuleNotFoundError:
    # Outside the backend project (e.g. `uv run --with openpyxl` from the repo root) the dry-run still reads the Excel.
    select = Session = servicios = DatabaseConfigurationError = create_database_engine = get_database_url = None
    Color = Modelo = Producto = None
    HAY_BACKEND = False

HOJA = "Marroquineria1"
PRIMERA_FILA, ULTIMA_FILA, ULTIMA_COLUMNA = 22, 347, 35  # rows 22 to 347, columns A to AI
MARCA = "IMPORTADO-EXCEL"
MARCA_FILA = re.compile(rf"{MARCA} fila (\d+)\b")
# Fixed by the user's decisions (S4, S9): the state is the model's default, the rest is not known from the Excel.
ESTADO_DEL_CICLO = "EN_DEFINICION"
QUIEN_LO_CONFECCIONA = None  # closed field (EXTERNA/INTERNA): B and D go to the note instead
FECHA_DE_ALTA = None  # SUPUESTO: validar con Gerardo. Column E looks like a quotation date, not a creation date.
ES_KIT = False
# Column H type -> material code of the seed (the Excel ids overlap between leather and lining; here it is always leather).
CUEROS = {1: "MAT-CU01", 2: "MAT-CU02", 3: "MAT-CU03", 4: "MAT-CU04", 5: "MAT-CU05", 6: "MAT-CU06"}
# SUPUESTO: validar con Gerardo. Same as `cotizable = false` in the seed: crear_producto rejects them, so the product goes without leather.
NO_COTIZABLES = {3: "lagarto", 4: "yacaré"}
# "... - C Arena)": the color is only taken from this clear pattern, anything else leaves it empty.
PATRON_COLOR = re.compile(r"-\s*C\s+([^()]+?)\s*\)\s*$")
PATRON_KIT = re.compile(r"\bkit\b|costo\s*x", re.IGNORECASE)
SIN_CUERO, SIN_COLOR = "(sin cuero)", "(sin color)"
MOTIVO_KIT = "posible kit o costeo por varias unidades"


# --- Plan (pure) ------------------------------------------------------------------------------------------------

@dataclass(frozen=True)
class FilaPlan:
    fila: int
    modelo_excel: str | None
    nombre_propio: str | None
    cuero: str | None  # material code, or None
    color: str | None
    nota: str
    revisar: tuple[tuple[str, str], ...]  # (reason key, full "REVISAR: ..." text)
    cuero_nulo: str | None  # why the leather is empty, or None when it is set


@dataclass(frozen=True)
class Plan:
    filas: list[FilaPlan]

    @property
    def con_nombre(self) -> int:
        return sum(1 for f in self.filas if f.nombre_propio is not None)

    @property
    def por_cuero(self) -> Counter:
        return Counter(f.cuero or SIN_CUERO for f in self.filas)

    @property
    def por_color(self) -> Counter:
        return Counter(f.color or SIN_COLOR for f in self.filas)

    @property
    def por_revisar(self) -> Counter:
        return Counter(clave for f in self.filas for clave, _ in f.revisar)

    @property
    def por_cuero_nulo(self) -> Counter:
        return Counter(f.cuero_nulo for f in self.filas if f.cuero_nulo)


def columnas_con_error(celdas) -> list[str]:
    """Letters of the cells (in the order given) whose text starts with `#` (#VALUE!, #REF!...)."""
    return [letra for letra, valor in celdas if isinstance(valor, str) and valor.lstrip().startswith("#")]


def _texto(valor) -> str | None:
    """A cell as text with its spaces normalized; dates as ISO and whole numbers without decimals."""
    if valor is None:
        return None
    if isinstance(valor, datetime):
        return valor.date().isoformat()
    if isinstance(valor, date):
        return valor.isoformat()
    if isinstance(valor, float) and valor.is_integer():
        valor = int(valor)
    return " ".join(str(valor).split()) or None


def _nombre(valor) -> str | None:
    """The name is the original text of column F: only `strip()`, never corrected nor split."""
    if valor is None:
        return None
    return str(valor).strip() or None


def _cuero(tipo) -> tuple[str | None, str | None, tuple[str, str] | None]:
    """(material code, why it is empty, review mark) for the type of column H."""
    if isinstance(tipo, float) and tipo.is_integer():
        tipo = int(tipo)
    if tipo is None or (isinstance(tipo, str) and (not tipo.strip() or tipo.lstrip().startswith("#"))):
        return None, "sin tipo de cuero", ("sin tipo de cuero", "REVISAR: sin tipo de cuero")
    if tipo in NO_COTIZABLES and not isinstance(tipo, bool):
        return None, "cuero no cotizable", (
            "cuero no cotizable", f"REVISAR: cuero {NO_COTIZABLES[tipo]} no cotizable (pendiente Gerardo)")
    if tipo in CUEROS and not isinstance(tipo, bool):
        return CUEROS[tipo], None, None
    return None, "tipo de cuero desconocido", (
        "tipo de cuero desconocido", f"REVISAR: tipo de cuero desconocido ({_texto(tipo)})")


def _color(texto) -> str | None:
    if not isinstance(texto, str):
        return None
    encontrado = PATRON_COLOR.search(texto.strip())
    return " ".join(encontrado.group(1).split()) if encontrado else None


def planificar(filas: list[dict]) -> Plan:
    """What the importer would create for the rows read from the Excel; no clock, no database, no workbook."""
    repetidos = {m for m, n in Counter(_texto(f.get("modelo")) for f in filas).items() if m is not None and n > 1}
    planes = []
    for f in filas:
        nombre = _nombre(f.get("nombre"))
        modelo = _texto(f.get("modelo"))
        cuero, cuero_nulo, marca_cuero = _cuero(f.get("tipo_cuero"))
        revisar = []
        if nombre is None:
            revisar.append(("sin nombre", "REVISAR: sin nombre"))
        if f.get("errores"):
            revisar.append(("error en origen", f"REVISAR: error en origen ({', '.join(f['errores'])})"))
        if marca_cuero:
            revisar.append(marca_cuero)
        if modelo in repetidos:
            revisar.append(("modelo repetido", "REVISAR: modelo repetido"))
        if nombre and PATRON_KIT.search(nombre):
            revisar.append((MOTIVO_KIT, f"REVISAR: {MOTIVO_KIT}"))
        partes = [f"{MARCA} fila {f['fila']}", *(texto for _, texto in revisar)]
        for prefijo, clave in (("B", "b"), ("D", "d"), ("C", "c")):
            valor = _texto(f.get(clave))
            if valor is not None:
                partes.append(f"{prefijo}={valor}")
        fecha = _texto(f.get("e"))
        if fecha is not None:
            partes.append(f"E={fecha}")
        for celda, comentario in f.get("comentarios", []):
            partes.append(f"Comentario {celda}: {_texto(comentario)}")
        planes.append(FilaPlan(f["fila"], modelo, nombre, cuero, _color(f.get("cuero")), " | ".join(partes), tuple(revisar), cuero_nulo))
    return Plan(planes)


def filas_importadas(notas) -> set[int]:
    """Excel rows that already carry the marker in a note; an exact number match ("fila 2" is not "fila 22")."""
    return {int(n) for nota in notas if nota for n in MARCA_FILA.findall(nota)}


# --- Reading the workbook (the only place that imports openpyxl) ------------------------------------------------

def leer_excel(ruta) -> list[dict]:
    """The rows 22 to 347 of Marroquineria1 as dicts of raw values (`data_only=True`: values, not formulas)."""
    if not Path(ruta).is_file():
        raise FileNotFoundError(ruta)
    import openpyxl
    from openpyxl.utils import get_column_letter

    libro = openpyxl.load_workbook(ruta, data_only=True)
    try:
        hoja = libro[HOJA]
        filas = []
        for n in range(PRIMERA_FILA, ULTIMA_FILA + 1):
            celdas = [(get_column_letter(c), hoja.cell(n, c)) for c in range(1, ULTIMA_COLUMNA + 1)]
            valores = {letra: celda.value for letra, celda in celdas}
            if _nombre(valores["F"]) is None and _texto(valores["G"]) is None:
                continue  # an empty row (a row without a name but with a model code is kept and flagged)
            comentarios = [(celda.coordinate, celda.comment.text) for _, celda in celdas if getattr(celda, "comment", None)]
            filas.append({
                "fila": n, "nombre": valores["F"], "modelo": valores["G"], "tipo_cuero": valores["H"], "cuero": valores["I"],
                "b": valores["B"], "c": valores["C"], "d": valores["D"], "e": valores["E"],
                "errores": columnas_con_error(valores.items()), "comentarios": comentarios,
            })
        return filas
    finally:
        libro.close()


# --- Loading ----------------------------------------------------------------------------------------------------

@dataclass
class Resumen:
    plan: Plan
    verificado: bool  # False: nothing was compared with the database
    escribio: bool
    a_crear: list[FilaPlan]
    existentes: list[FilaPlan]
    sin_modelo: list[FilaPlan]
    colores_nuevos: list[str]
    avisos: list[str]


def resumen_sin_base(plan: Plan) -> Resumen:
    return Resumen(plan, False, False, [], [], [], [], [])


def importar(session: Session, plan: Plan, escribir: bool) -> Resumen:
    """Create the products the plan lists and the database does not have yet; with `escribir=False` only count them."""
    por_fila: dict[int, list[str]] = {}
    for fila, codigo in session.execute(select(Modelo.fila_excel_viejo, Modelo.codigo).where(Modelo.fila_excel_viejo.is_not(None))):
        por_fila.setdefault(fila, []).append(codigo)
    ya = filas_importadas(session.scalars(select(Producto.nota).where(Producto.nota.like(f"%{MARCA} fila %"))))
    resumen = Resumen(plan, True, escribir, [], [], [], [], [])
    modelo_de = {}
    for f in plan.filas:
        codigos = por_fila.get(f.fila, [])
        if f.fila in ya:
            resumen.existentes.append(f)
        elif len(codigos) != 1:
            resumen.sin_modelo.append(f)
            if len(codigos) > 1:
                resumen.avisos.append(f"La fila {f.fila} tiene más de un modelo en la base: no se crea el producto.")
        else:
            resumen.a_crear.append(f)
            modelo_de[f.fila] = codigos[0]
    conocidos = set(session.scalars(select(Color.nombre)))
    resumen.colores_nuevos = sorted({f.color for f in resumen.a_crear if f.color and f.color not in conocidos})
    if escribir:
        for nombre in resumen.colores_nuevos:
            servicios.crear_color(session, nombre=nombre, nota=f"{MARCA} color")
        for f in resumen.a_crear:
            servicios.crear_producto(
                session, modelo=modelo_de[f.fila], cuero=f.cuero, color=f.color, quien_lo_confecciona=QUIEN_LO_CONFECCIONA,
                fecha_de_alta=FECHA_DE_ALTA, nombre_propio=f.nombre_propio, es_kit=ES_KIT, nota=f.nota)
    return resumen


# --- Command line -----------------------------------------------------------------------------------------------

def rechazar(mensaje: str) -> int:
    print(mensaje, file=sys.stderr)
    return 2


ENTORNOS = ("staging", "production")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Importa los productos del Excel de costos (por defecto, solo muestra qué haría).")
    parser.add_argument("excel", help="Ruta del Excel (solo lectura).")
    parser.add_argument("--entorno", help="Para escribir tiene que ser exactamente 'staging' o 'production'.")
    parser.add_argument("--confirmar", action="store_true", help="Confirma que querés escribir productos.")
    opciones = parser.parse_args(argv)
    escribir = opciones.entorno is not None or opciones.confirmar
    if escribir:
        if opciones.entorno not in ENTORNOS or not opciones.confirmar:
            return rechazar("No se importó nada: para escribir hacen falta los dos avisos juntos, --entorno (staging o production) y --confirmar. "
                            "Sin ellos el script solo muestra qué haría.")
        railway = os.environ.get("RAILWAY_ENVIRONMENT_NAME")
        if railway is None:
            # SUPUESTO: production solo se escribe desde dentro de su contenedor; una corrida local solo puede apuntar a staging
            if opciones.entorno == "production":
                return rechazar("No se importó nada: production solo se escribe desde dentro del contenedor de production (no hay entorno de Railway).")
        elif railway != opciones.entorno:
            return rechazar(f"No se importó nada: el entorno de Railway no coincide con --entorno {opciones.entorno}.")  # the Railway value is never echoed
    hay_base = bool(os.environ.get("DATABASE_URL"))
    if (escribir or hay_base) and not HAY_BACKEND:
        return rechazar("Para hablar con la base corré el script desde backend/: "
                        "cd backend && uv run --with openpyxl python -I scripts/importar_productos.py ...")
    if escribir or hay_base:
        try:
            get_database_url()
        except DatabaseConfigurationError:
            print("No se pudo leer DATABASE_URL: hace falta una URL de PostgreSQL válida.", file=sys.stderr)
            return 1
    try:
        plan = planificar(leer_excel(opciones.excel))
    except FileNotFoundError:
        return rechazar(f"No se encontró el Excel: {opciones.excel}")
    except ModuleNotFoundError:
        return rechazar("Falta openpyxl: correlo con 'uv run --with openpyxl python -I backend/scripts/importar_productos.py ...'.")
    except Exception as error:  # a broken or hostile workbook: only the class is shown
        return rechazar(f"No se pudo leer el Excel ({type(error).__name__}).")
    if not (escribir or hay_base):
        resumen = resumen_sin_base(plan)
    else:
        engine = create_database_engine()
        try:
            with Session(engine) as session:
                resumen = importar(session, plan, escribir)
                session.rollback()  # a dry-run never leaves a transaction open
        except (servicios.DatosInvalidos, servicios.Conflicto, servicios.NoEncontrado) as error:
            print(f"Se frenó la importación: {error}", file=sys.stderr)
            return 1
        except Exception as error:  # driver errors can carry connection details: only the class is shown
            print(f"Se frenó la importación por un error inesperado ({type(error).__name__}).", file=sys.stderr)
            return 1
        finally:
            engine.dispose()
    imprimir(resumen, opciones.entorno if escribir else None)
    return 0


def _contar(titulo: str, conteo: Counter) -> None:
    print(f"{titulo}:")
    for clave, cantidad in sorted(conteo.items(), key=lambda par: (-par[1], par[0])):
        print(f"  {clave}: {cantidad}")
    if not conteo:
        print("  ninguno")


def imprimir(resumen: Resumen, entorno: str | None = None) -> None:
    plan = resumen.plan
    print(f"Filas leídas del bloque central: {len(plan.filas)}")
    print(f"Filas con nombre: {plan.con_nombre}")
    _contar("Productos por cuero", plan.por_cuero)
    _contar("Productos por color", plan.por_color)
    _contar("Filas REVISAR por motivo (una fila puede tener varios)", plan.por_revisar)
    _contar("Cuero NULL por motivo", plan.por_cuero_nulo)
    repetidos = sorted({f.modelo_excel for f in plan.filas if any(c == "modelo repetido" for c, _ in f.revisar)}, key=lambda m: (len(m), m))
    print(f"Modelos repetidos ({len(repetidos)}): {', '.join(repetidos) if repetidos else 'ninguno'}")
    if not resumen.verificado:
        print("A crear / ya existentes / sin modelo: sin verificar contra la base (no hay DATABASE_URL).")
    else:
        print(f"{'Creados' if resumen.escribio else 'A crear'}: {len(resumen.a_crear)}")
        print(f"Ya existentes (se saltean): {len(resumen.existentes)}")
        print(f"Sin modelo en la base (no se crea el producto): {len(resumen.sin_modelo)}")
        for f in resumen.sin_modelo[:20]:
            print(f"  fila {f.fila}: {f.nombre_propio or '(sin nombre)'} (modelo del Excel {f.modelo_excel or '-'})")
        if resumen.colores_nuevos:
            print(f"Colores {'creados' if resumen.escribio else 'a crear'}: {', '.join(resumen.colores_nuevos)}")
        for aviso in resumen.avisos:
            print(f"Aviso: {aviso}")
    # the environment named here is the one the user passed with --entorno, never the Railway variable
    print(f"Modo escritura{f' en {entorno}' if entorno else ''}: terminó." if resumen.escribio else "No se escribió nada (dry-run).")


if __name__ == "__main__":
    raise SystemExit(main())
