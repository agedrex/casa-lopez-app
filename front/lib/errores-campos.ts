// Plain-Spanish messages for what FastAPI answers when a request does not validate (422 with a list of
// `{loc, type, msg, ctx}`). The only place that knows how a field is called for a person: the internal name
// (`cuero_m2_por_unidad`) never reaches the screen. Pure functions, no "server-only", so `tsx --test` can run them.

/** Each field of the API bodies as a noun phrase with its article ("el consumo de cuero por unidad"). */
export const FIELD_LABELS: Record<string, string> = {
  activo: "el estado activo",
  alicuota: "la alícuota",
  anulados: "la opción de incluir anulados",
  archivo: "el archivo",
  ars_por_usd: "el valor del dólar",
  articulo: "el artículo",
  cambios: "la lista de cambios",
  canal: "el canal",
  cantidad: "la cantidad",
  cantidad_presentaciones: "la cantidad de presentaciones",
  categoria: "la categoría",
  categorias: "la lista de categorías",
  codigo: "el código",
  color: "el color",
  comentario: "el comentario",
  componente: "el componente",
  con_montos: "la opción de mostrar montos",
  concepto: "el concepto",
  confeccion_estimada_ars: "la confección estimada",
  consumo_neto_por_unidad: "el consumo neto por unidad",
  contacto: "el contacto",
  contenido_por_presentacion: "el contenido por presentación",
  costo: "el costo",
  costo_unitario_ars: "el costo unitario",
  cotizado: "el precio cotizado",
  cuero: "el cuero",
  cuero_m2_por_unidad: "el consumo de cuero por unidad",
  cuit: "el CUIT",
  decision: "la decisión",
  desde: "la fecha desde",
  direccion: "la dirección",
  documento_id: "el documento",
  donde_se_hace: "dónde se confecciona",
  es_kit: "la marca de kit",
  estado: "el estado",
  etapa: "la etapa",
  fabrica_o_tienda: "el ámbito (fábrica o tienda)",
  fecha: "la fecha",
  fecha_de_alta: "la fecha de alta",
  fecha_de_compra: "la fecha de compra",
  fecha_de_entrega: "la fecha de entrega",
  fecha_de_envio: "la fecha de envío",
  fecha_de_recepcion: "la fecha de recepción",
  fecha_documento: "la fecha del documento",
  ficticio: "la marca de dato ficticio",
  filas: "la lista de filas",
  flex_m2_por_unidad: "el consumo de flex por unidad",
  forro: "el forro",
  forro_m2_por_unidad: "el consumo de forro por unidad",
  fuente: "la fuente",
  fuente_estado: "el estado de la fuente",
  goma_eva_m2_por_unidad: "el consumo de goma EVA por unidad",
  hasta: "la fecha hasta",
  herrajes_usd_por_unidad: "el costo de herrajes por unidad (USD)",
  hilo_y_cemento: "el consumo de hilo y cemento",
  horas_de_confeccion: "el tiempo de confección por unidad (horas)",
  id: "el identificador",
  items: "la lista de renglones",
  iva_incluido: "la marca de IVA incluido",
  limit: "el límite de resultados",
  lineas: "la lista de líneas",
  m2: "la superficie en m²",
  m2_iniciales: "la superficie inicial en m²",
  margen: "el margen",
  margen_pct: "el margen",
  material: "el material",
  materiales: "la lista de materiales",
  modelo: "el modelo",
  moneda: "la moneda",
  monto: "el monto",
  monto_ars_del_mes: "el monto del mes",
  nombre: "el nombre",
  nombre_del_modelo: "el nombre del modelo",
  nombre_propio: "el nombre propio",
  nota: "la nota",
  nota_fuente: "la nota de la fuente",
  nuevos: "la lista de filas nuevas",
  numero: "el número",
  orden_item: "el renglón del lote",
  origen: "el origen",
  origen_de_los_consumos: "el origen de los consumos",
  pagado: "el precio pagado",
  pagina: "la página",
  periodo: "el período",
  persona: "la persona",
  pieles: "la lista de pieles",
  precio: "el precio",
  precio_ars: "el precio en pesos",
  precio_pagado_por_m2: "el precio pagado por m²",
  precio_por_m2: "el precio por m²",
  precio_por_presentacion: "el precio por presentación",
  precio_referencial: "el precio de referencia",
  precio_unitario_ars: "el precio unitario",
  precio_venta: "el precio de venta",
  precio_venta_unitario_ars: "el precio de venta unitario",
  presentacion: "la presentación",
  producto: "el producto",
  productos: "la lista de productos",
  proveedor: "el proveedor",
  q: "la búsqueda",
  quien: "quién lo hizo",
  quien_lo_confecciona: "quién lo confecciona",
  registro_id: "el registro",
  remito: "el remito",
  rol: "el rol",
  seccion: "la sección",
  simular: "la opción de simular",
  tamano: "el tamaño",
  tamanos: "la lista de tamaños",
  taller: "el taller",
  taller_precio_cotizado_por_unidad_ars:
    "el precio cotizado por el taller por unidad",
  taller_precio_pagado_por_unidad_ars: "el precio pagado al taller por unidad",
  telefono: "el teléfono",
  texto: "el texto",
  tipo: "el tipo",
  total: "el total",
  unidad: "la unidad",
  unidad_de_consumo: "la unidad de consumo",
  unidad_del_precio: "la unidad del precio",
  unidades: "la cantidad de unidades",
  validado: "la marca de validado",
  valor: "el valor",
  valor_texto: "el valor",
  vigente_desde: "la fecha desde la que rige",
  vinculo: "el vínculo",
};

/** What each list of rows is called, to say which row failed ("Línea 2: ..."). */
const ROW_LABELS: Record<string, string> = {
  cambios: "Cambio",
  filas: "Fila",
  items: "Renglón",
  lineas: "Línea",
  materiales: "Material",
  nuevos: "Fila nueva",
  pieles: "Piel",
  productos: "Producto",
};

const MAX_MESSAGES = 4;

type Issue = {
  loc?: unknown;
  type?: unknown;
  msg?: unknown;
  ctx?: unknown;
};

function capitalize(text: string): string {
  return text.charAt(0).toUpperCase() + text.slice(1);
}

/** The person's name for a field. An unknown one is shown without underscores, never as `snake_case`. */
export function fieldLabel(name: string): string {
  return FIELD_LABELS[name] ?? `el dato «${name.replaceAll("_", " ")}»`;
}

function limit(ctx: unknown, key: string): string | null {
  const value = (ctx as Record<string, unknown> | null | undefined)?.[key];
  return typeof value === "string" || typeof value === "number"
    ? String(value)
        .replace(/(\.\d*?)0+$/, "$1")
        .replace(/\.$/, "")
    : null;
}

function plural(count: string, one: string, many: string): string {
  return `${count} ${count === "1" ? one : many}`;
}

function sentence(issue: Issue, label: string): string {
  const ctx = issue.ctx;
  const type = typeof issue.type === "string" ? issue.type : "";
  const ge = limit(ctx, "ge");
  const gt = limit(ctx, "gt");
  const le = limit(ctx, "le");
  const lt = limit(ctx, "lt");
  const min = limit(ctx, "min_length");
  const max = limit(ctx, "max_length");
  const places = limit(ctx, "decimal_places");
  const digits = limit(ctx, "max_digits");
  switch (type) {
    case "missing":
      return `Falta completar ${label}.`;
    case "greater_than_equal":
      return `${capitalize(label)} debe ser mayor o igual a ${ge ?? "0"}.`;
    case "greater_than":
      return `${capitalize(label)} debe ser mayor que ${gt ?? "0"}.`;
    case "less_than_equal":
      return `${capitalize(label)} debe ser menor o igual a ${le ?? "el máximo permitido"}.`;
    case "less_than":
      return `${capitalize(label)} debe ser menor que ${lt ?? "el máximo permitido"}.`;
    case "string_too_short":
      return min === "1"
        ? `Falta completar ${label}.`
        : `${capitalize(label)} necesita al menos ${plural(min ?? "1", "carácter", "caracteres")}.`;
    case "string_too_long":
      return `${capitalize(label)} admite como máximo ${plural(max ?? "0", "carácter", "caracteres")}.`;
    case "too_short":
      return `Cargue al menos ${plural(min ?? "1", "elemento", "elementos")} en ${label}.`;
    case "too_long":
      return `${capitalize(label)} admite como máximo ${plural(max ?? "0", "elemento", "elementos")}.`;
    case "decimal_max_places":
      return `${capitalize(label)} admite como máximo ${plural(places ?? "0", "decimal", "decimales")}.`;
    case "decimal_max_digits":
    case "decimal_whole_digits":
      return `${capitalize(label)} tiene demasiados dígitos${digits ? ` (máximo ${digits})` : ""}.`;
    case "decimal_parsing":
    case "decimal_type":
    case "int_parsing":
    case "int_type":
    case "int_from_float":
    case "float_parsing":
    case "float_type":
    case "finite_number":
      return `${capitalize(label)} tiene que ser un número.`;
    case "date_parsing":
    case "date_type":
    case "date_from_datetime_parsing":
    case "date_from_datetime_inexact":
      return `${capitalize(label)} tiene que ser una fecha válida (día, mes y año).`;
    case "bool_parsing":
    case "bool_type":
      return `${capitalize(label)} tiene que ser sí o no.`;
    case "string_type":
      return `${capitalize(label)} tiene que ser texto.`;
    case "literal_error":
    case "enum":
      return `${capitalize(label)} no es una de las opciones permitidas.`;
    case "string_pattern_mismatch":
      return `${capitalize(label)} no tiene el formato esperado.`;
    case "extra_forbidden":
      return `Se envió un dato que no corresponde (${label}).`;
    case "value_error": {
      // Our own validators already write the message in Spanish: "Value error, Indicá el precio..."
      const own = typeof issue.msg === "string" ? issue.msg : "";
      return (
        own.replace(/^Value error,\s*/i, "") ||
        `${capitalize(label)} no es válido.`
      );
    }
    default:
      return `${capitalize(label)} no es válido.`;
  }
}

/** Where the issue is: the field, and the row of its list when there is one ("Línea 2: "). */
function whereIs(loc: unknown): { field: string | null; row: string } {
  if (!Array.isArray(loc)) return { field: null, row: "" };
  const path = loc.filter(
    (part, index) => !(index === 0 && /^(body|query|path)$/.test(String(part))),
  );
  const field = [...path].reverse().find((part) => typeof part === "string");
  const rowAt = path.findIndex((part) => typeof part === "number");
  let row = "";
  if (rowAt > 0 && typeof path[rowAt] === "number") {
    const list = String(path[rowAt - 1]);
    row = `${ROW_LABELS[list] ?? "Fila"} ${Number(path[rowAt]) + 1}: `;
  }
  return { field: typeof field === "string" ? field : null, row };
}

/** One readable text for the whole `detail` list of a 422; the same issue is said once. */
export function describeValidationErrors(detail: unknown[]): string {
  const messages: string[] = [];
  for (const item of detail) {
    if (!item || typeof item !== "object") continue;
    const issue = item as Issue;
    const { field, row } = whereIs(issue.loc);
    const text =
      field === null ? "" : `${row}${sentence(issue, fieldLabel(field))}`;
    if (text && !messages.includes(text)) messages.push(text);
  }
  if (messages.length === 0) return "Revise los datos ingresados.";
  const shown = messages.slice(0, MAX_MESSAGES).join(" ");
  const rest = messages.length - MAX_MESSAGES;
  return rest > 0
    ? `${shown} (y ${plural(String(rest), "error más", "errores más")}).`
    : shown;
}

/** What an error body of the API says: its `detail` as one text (a 422 list becomes plain Spanish) and its `avisos`. */
export function readErrorBody(body: unknown): {
  detail: string;
  avisos: string[];
} {
  if (!body || typeof body !== "object") return { detail: "", avisos: [] };
  const record = body as { detail?: unknown; avisos?: unknown };
  const detail =
    typeof record.detail === "string"
      ? record.detail
      : Array.isArray(record.detail)
        ? describeValidationErrors(record.detail)
        : "";
  const avisos = Array.isArray(record.avisos)
    ? record.avisos.filter((item): item is string => typeof item === "string")
    : [];
  return { detail, avisos };
}
