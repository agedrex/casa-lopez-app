"""Generate backend/migrations/seed_data/seed_v3.json from the plantilla (DER v3).

Not run by migrations: the JSON is committed and migrations never read the xlsx.
Treat the workbook as untrusted data and run it isolated, outside the repository:

    uv run --with openpyxl python -I backend/scripts/generate_seed_v3.py \
        "/path/to/Plantilla Costos Casa Lopez v4.1 (trabajo).xlsx" backend/migrations/seed_data/seed_v3.json

Money and quantities are written as strings and loaded as Decimal. Rows are
located by header name, never by position, and a row is a seed row only when its
name column is filled in (the sheets are pre-formatted with empty coded rows).
"""

import json
import sys
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

import openpyxl

SOURCE_NAME = "Plantilla Costos Casa Lopez v4.1 (trabajo).xlsx"
QUANTUM = {
    "money": Decimal("0.0001"),     # NUMERIC(14,4)
    "quantity": Decimal("0.0001"),  # NUMERIC(10,4)
    "rate": Decimal("0.0001"),      # NUMERIC(12,4)
    "pct": Decimal("0.001"),        # NUMERIC(6,3)
}
# Parameters computed by the sheet; the app recalculates them (Diccionario: "Calculado").
CALCULATED_PARAMETERS = {"DOLAR_VIGENTE", "FECHA_DOLAR_VIGENTE"}

rounded_values: list[str] = []


def clean(value):
    if isinstance(value, str):
        value = value.strip()
        return value or None
    return value


def text(value):
    value = clean(value)
    if value is None:
        return None
    if isinstance(value, float) and value.is_integer():
        value = int(value)
    return str(value)


def boolean(value):
    value = clean(value)
    if value is None:
        return None
    if value not in ("SI", "NO"):
        raise ValueError(f"Expected SI/NO, got {value!r}")
    return value == "SI"


def integer(value):
    value = clean(value)
    return None if value is None else int(value)


def iso_date(value):
    value = clean(value)
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    raise ValueError(f"Expected a date, got {value!r}")


def decimal_of(kind):
    def convert(value):
        value = clean(value)
        if value is None:
            return None
        exact = Decimal(repr(value)) if isinstance(value, float) else Decimal(value)
        quantized = exact.quantize(QUANTUM[kind])
        if quantized != exact:
            rounded_values.append(f"{exact} -> {quantized}")
        return format(quantized.normalize(), "f")
    return convert


def code_before_dot(value):
    """'MAT-FO02 · Tela forrería' -> 'MAT-FO02' (dropdown entries are 'code · name')."""
    value = clean(value)
    return None if value is None else value.split(" · ", 1)[0].strip()


# A column spec: (database column, header in the sheet, converter, type tag, optional (ref table, ref column)).
def col(name, header, convert=text, tag="text", ref=None):
    return {"name": name, "header": header, "convert": convert, "tag": tag, "ref": ref}


def fk(name, header, ref_table, ref_column="codigo", convert=code_before_dot):
    return col(name, header, convert, "fk", (ref_table, ref_column))


TABLES = [
    ("etapa", "Etapas", "Código", [
        col("codigo", "Código"), col("orden", "Orden", integer, "int"),
        col("que_es_y_de_donde_viene", "Qué es y de dónde viene"), col("tipo", "Tipo"),
        col("va_siempre", "¿Va siempre?", boolean, "bool"), col("tratamiento", "Tratamiento"),
        col("nota", "Nota"),
    ]),
    ("categoria", "Categorias", "Nombre", [
        col("codigo", "Código"), col("nombre", "Nombre"), col("nota", "Nota"),
    ]),
    # The Colores sheet ships only empty coded rows (the list is for Casa López to fill in): no color is seeded.
    ("color", "Colores", "Nombre", [
        col("codigo", "Código"), col("nombre", "Nombre"), col("nota", "Nota"),
    ]),
    ("persona", "Personas", "Nombre", [
        col("codigo", "Código"), col("nombre", "Nombre"), col("rol", "Rol"), col("vinculo", "Vínculo"),
        col("activo", "Activo", boolean, "bool"), col("nota", "Nota"),
    ]),
    ("taller", "Talleres", "Nombre", [
        col("codigo", "Código"), col("nombre", "Nombre"), col("cuit", "CUIT"), col("telefono", "Teléfono"),
        col("direccion", "Dirección"), col("contacto", "Contacto"), col("activo", "Activo", boolean, "bool"),
        col("nota", "Nota"),
    ]),
    ("impuesto", "Impuestos", "Nombre", [
        col("codigo", "Código"), col("nombre", "Nombre"), col("alicuota", "Alícuota", decimal_of("pct"), "decimal"),
        col("base", "Base"), col("es_costo_del_producto", "¿Es costo del producto?", boolean, "bool"),
        col("nota", "Nota"),
    ]),
    ("material", "Materiales", "Nombre", [
        col("codigo", "Código"), col("nombre", "Nombre"), col("nombre_corto", "Nombre corto"),
        fk("etapa_id", "Etapa", "etapa", convert=text), col("unidad_de_consumo", "Unidad de consumo"),
        col("cotizable", "Cotizable", boolean, "bool"), col("controla_inventario", "Controla inventario", boolean, "bool"),
        col("desperdicio_manual", "Desperdicio manual (opcional)", decimal_of("pct"), "decimal"),
        col("ref_excel_viejo", "Ref. Excel viejo"), col("nota", "Nota"),
    ]),
    ("precio_material", "Precios", "Material", [
        col("codigo", "Código"), fk("material_id", "Material", "material"),
        fk("color_id", "Color (opcional)", "color", "nombre", convert=text),
        col("proveedor", "Proveedor"), col("precio", "Precio", decimal_of("money"), "decimal"),
        col("moneda", "Moneda"), col("unidad_del_precio", "Unidad del precio"),
        col("iva_incluido", "IVA incluido", boolean, "bool"), col("vigente_desde", "Vigente desde", iso_date, "date"),
        col("nota_fuente", "Nota / fuente"),
    ]),
    ("tipo_cambio", "Dolar", "Fecha", [
        col("fecha", "Fecha", iso_date, "date"), col("ars_por_usd", "ARS por USD", decimal_of("rate"), "decimal"),
        col("fuente", "Fuente"), col("tipo", "Tipo"), col("nota", "Nota"),
    ]),
    ("modelo", "Modelos", "Nombre del modelo", [
        col("codigo", "Código"), col("nombre_del_modelo", "Nombre del modelo"),
        fk("categoria_id", "Categoría", "categoria", "nombre", convert=text),
        col("modelo_excel_viejo", "Modelo Excel viejo"), col("fila_excel_viejo", "Fila Excel viejo", integer, "int"),
        col("cuero_m2_por_unidad", "Cuero m² por unidad", decimal_of("quantity"), "decimal"),
        fk("forro_id", "Forro", "material"),
        col("forro_m2_por_unidad", "Forro m² por unidad", decimal_of("quantity"), "decimal"),
        col("flex_m2_por_unidad", "Flex m² por unidad", decimal_of("quantity"), "decimal"),
        col("goma_eva_m2_por_unidad", "Goma EVA m² por unidad", decimal_of("quantity"), "decimal"),
        col("herrajes_usd_por_unidad", "Herrajes USD por unidad", decimal_of("money"), "decimal"),
        col("hilo_y_cemento", "Hilo y cemento (juegos)", decimal_of("quantity"), "decimal"),
        col("confeccion_estimada_ars", "Confección estimada ARS (Mariano)", decimal_of("money"), "decimal"),
        col("horas_de_confeccion", "Horas de confección", decimal_of("quantity"), "decimal"),
        col("origen_de_los_consumos", "Origen de los consumos"), col("validado", "Validado", boolean, "bool"),
        col("nota", "Nota"),
        col("excel_viejo_subtotal_af", "Excel viejo: subtotal AF", decimal_of("money"), "decimal"),
        col("excel_viejo_corte_reb_prep", "Excel viejo: corte + reb + prep", decimal_of("money"), "decimal"),
        col("tamano", "Tamaño (opcional)"),
    ]),
    ("gasto_periodo", "Costos_Fijos", "Concepto", [
        col("codigo", "Código"), col("periodo", "Período"), col("concepto", "Concepto"),
        col("fabrica_o_tienda", "¿Fábrica o tienda?"), col("categoria", "Categoría"),
        fk("persona_id", "Persona", "persona", convert=text),
        col("monto_ars_del_mes", "Monto ARS del mes", decimal_of("money"), "decimal"),
        col("ficticio", "¿Ficticio?", boolean, "bool"), col("nota_fuente", "Nota / fuente"),
    ]),
]


def read_rows(workbook, sheet, key_header):
    rows = workbook[sheet].iter_rows(values_only=True)
    headers = [clean(cell) for cell in next(rows)]
    position = {header: index for index, header in enumerate(headers) if header is not None}
    for values in rows:
        if clean(values[position[key_header]]) is not None:
            yield lambda header, values=values: values[position[header]]


def parameter_table(workbook):
    columns = [
        {"name": "codigo", "tag": "text"}, {"name": "constante", "tag": "text"},
        {"name": "valor", "tag": "decimal"}, {"name": "valor_texto", "tag": "text"},
        {"name": "unidad", "tag": "text"}, {"name": "que_es", "tag": "text"},
        {"name": "fuente_estado", "tag": "text"},
    ]
    rows = []
    for get in read_rows(workbook, "Parametros", "Constante"):
        code = text(get("Código en la base"))
        if code in CALCULATED_PARAMETERS:
            continue
        value = clean(get("Valor"))
        number = decimal_of("money")(value) if isinstance(value, (int, float)) else None
        rows.append([code, text(get("Constante")), number, text(value) if number is None else None,
                     text(get("Unidad")), text(get("Qué es")), text(get("Fuente / estado"))])
    return {"name": "parametro", "columns": columns, "rows": rows}


def table_payload(workbook, name, sheet, key_header, columns):
    rows = [[spec["convert"](get(spec["header"])) for spec in columns]
            for get in read_rows(workbook, sheet, key_header)]
    described = []
    for spec in columns:
        entry = {"name": spec["name"], "tag": spec["tag"]}
        if spec["ref"]:
            entry["ref"] = list(spec["ref"])
        described.append(entry)
    return {"name": name, "columns": described, "rows": rows}


def build(workbook_path):
    workbook = openpyxl.load_workbook(workbook_path, data_only=True)
    tables = []
    for name, sheet, key_header, columns in TABLES:
        payload = table_payload(workbook, name, sheet, key_header, columns)
        if payload["rows"]:
            tables.append(payload)
        if name == "impuesto":
            tables.append(parameter_table(workbook))
    return {"source": SOURCE_NAME, "tables": tables}


def dump(seed):
    lines = ['{', f' "source": {json.dumps(seed["source"], ensure_ascii=False)},', ' "tables": [']
    for index, table in enumerate(seed["tables"]):
        lines.append('  {')
        lines.append(f'   "name": {json.dumps(table["name"])},')
        lines.append(f'   "columns": {json.dumps(table["columns"], ensure_ascii=False)},')
        lines.append('   "rows": [')
        lines.append(",\n".join("    " + json.dumps(row, ensure_ascii=False) for row in table["rows"]))
        lines.append('   ]')
        lines.append('  }' + ("," if index < len(seed["tables"]) - 1 else ""))
    lines += [' ]', '}', '']
    return "\n".join(lines)


def main(argv):
    if len(argv) != 3:
        raise SystemExit(__doc__)
    seed = build(argv[1])
    Path(argv[2]).write_text(dump(seed), encoding="utf-8")
    for table in seed["tables"]:
        print(f'{table["name"]}: {len(table["rows"])} rows')
    print(f"values rounded to the column scale: {len(rounded_values)}", *rounded_values[:10], sep="\n  ")


if __name__ == "__main__":
    main(sys.argv)
