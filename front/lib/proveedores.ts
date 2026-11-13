import { formatPercent, parseDecimalInput } from "./format";
import type { DocumentoTipo, OcrEstado } from "./types";

// Client-side hint only: the API checks the real size and the file's magic bytes.
export const MAX_FILE_BYTES = 10 * 1024 * 1024;
export const ACCEPTED_MIME = [
  "image/jpeg",
  "image/png",
  "image/webp",
  "application/pdf",
] as const;
export const ACCEPT_ATTRIBUTE = ACCEPTED_MIME.join(",");

export const DOCUMENT_TYPES: { value: DocumentoTipo; label: string }[] = [
  { value: "FACTURA", label: "Factura" },
  { value: "IMAGEN", label: "Imagen" },
  { value: "OTRO", label: "Otro" },
];

export function documentTypeLabel(code: string): string {
  return DOCUMENT_TYPES.find((item) => item.value === code)?.label ?? code;
}

const OCR_LABELS: Record<OcrEstado, string> = {
  PENDIENTE: "Pendiente",
  LISTO: "Listo",
  ERROR: "Error",
  NO_CONFIGURADO: "Sin OCR",
};

export function ocrLabel(state: string): string {
  return OCR_LABELS[state as OcrEstado] ?? state;
}

export function ocrTone(state: string): "neutral" | "warn" | "good" {
  if (state === "LISTO") return "good";
  if (state === "ERROR") return "warn";
  return "neutral";
}

/** The OCR can be asked again only when it failed or was never configured. */
export function canRetryOcr(state: string): boolean {
  return state === "ERROR" || state === "NO_CONFIGURADO";
}

/** Same-origin route that streams the file with the visitor's session. */
export function documentFileUrl(id: number): string {
  return `/proveedores/documentos/${id}/archivo`;
}

export function isImageMime(mime: string): boolean {
  return mime.startsWith("image/");
}

/** `1536` -> `1,5 KB`. Display only. */
export function formatFileSize(bytes: number): string {
  const format = (value: number) =>
    new Intl.NumberFormat("es-AR", { maximumFractionDigits: 1 }).format(value);
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${format(bytes / 1024)} KB`;
  return `${format(bytes / (1024 * 1024))} MB`;
}

/** Why a file is refused before sending it, or null. The API still has the last word. */
export function fileHint(file: { size: number; type: string }): string | null {
  if (file.size === 0) return "el archivo está vacío";
  if (file.size > MAX_FILE_BYTES) return "supera los 10 MB";
  if (file.type && !(ACCEPTED_MIME as readonly string[]).includes(file.type)) {
    return "solo se aceptan fotos (JPG, PNG, WebP) y PDF";
  }
  return null;
}

/** `10.00` -> `+10 %`, `-25.00` -> `-25 %`, none -> `—`. Display only: the API sends the variation already calculated. */
export function variationText(value: string | null | undefined): string {
  const percent = formatPercent(value);
  if (!value || percent === "—") return "—";
  const isZero = /^-?0+(\.0+)?$/.test(value);
  return value.startsWith("-") || isZero ? percent : `+${percent}`;
}

// Products a supplier sells (grid "Productos que vende"). The units mirror the closed list of the backend (`UNITS`).

export const UNIDADES = [
  { value: "m2", label: "m² (metro cuadrado)" },
  { value: "m", label: "m (metro)" },
  { value: "cm", label: "cm (centímetro)" },
  { value: "unidad", label: "Unidad" },
  { value: "juego", label: "Juego" },
  { value: "USD", label: "USD (herrajes migrados)" },
] as const;

export const MONEDAS = ["ARS", "USD"] as const;

/** One row of the grid as the person typed it; amounts stay text until the API parses them. */
export type ProductoDeProveedorFila = Record<string, string>;

export type ProductoDeProveedorBody = {
  nombre: string;
  unidad: string;
  cantidad: string | null;
  precio_referencial: string;
  moneda: string;
  iva_incluido: boolean;
  material: string | null;
  nota: string | null;
};

const POSITIVE = /[1-9]/;

/**
 * Checks one grid row and turns it into the body of `POST /proveedores/{codigo}/productos`
 * (a new product or a new version of one already listed). Text handling only: no amount is
 * converted to a number, and the price per unit is the API's.
 */
export function leerProductoDeProveedor(
  fila: ProductoDeProveedorFila,
  position: number,
):
  | { ok: true; body: ProductoDeProveedorBody }
  | { ok: false; message: string } {
  const cell = (key: string) => String(fila?.[key] ?? "").trim();
  const nombre = cell("nombre");
  const label = nombre ? `${nombre}` : `Producto ${position}`;
  const fail = (message: string) => ({
    ok: false as const,
    message: `${label}: ${message}`,
  });
  if (!nombre) return fail("indique el nombre del producto.");
  const unidad = cell("unidad");
  if (!UNIDADES.some((item) => item.value === unidad)) {
    return fail("elija la unidad de medida.");
  }
  const moneda = cell("moneda");
  if (!(MONEDAS as readonly string[]).includes(moneda)) {
    return fail("elija la moneda (ARS o USD).");
  }
  const precio = parseDecimalInput(cell("precio_referencial"));
  if (precio === null || !POSITIVE.test(precio)) {
    return fail(
      "el precio referencial tiene que ser un número mayor que cero. Ejemplo: 14000 o 5857,14.",
    );
  }
  const rawCantidad = cell("cantidad");
  const cantidad = rawCantidad ? parseDecimalInput(rawCantidad) : null;
  if (rawCantidad && (cantidad === null || !POSITIVE.test(cantidad))) {
    return fail(
      "la cantidad tiene que ser un número mayor que cero, o quedar vacía. Ejemplo: 1,4.",
    );
  }
  return {
    ok: true,
    body: {
      nombre,
      unidad,
      cantidad,
      precio_referencial: precio,
      moneda,
      iva_incluido: cell("iva") === "si",
      material: cell("material") || null,
      nota: cell("nota") || null,
    },
  };
}

/**
 * Rows of a grid save as they go to the API. The grid leaves the name (a `newOnly` column) out of a
 * saved row and does not show the note, so both come back from the saved product: a changed row
 * is a complete new version. New rows already carry their own name.
 */
export function filasParaGuardar(
  save: {
    changes: {
      id: string;
      cells: ProductoDeProveedorFila;
      changed: string[];
    }[];
    added: ProductoDeProveedorFila[];
  },
  productos: { codigo: string; nombre: string; nota: string | null }[],
): ProductoDeProveedorFila[] {
  const changed = save.changes.map((change) => {
    const original = productos.find((p) => p.codigo === change.id);
    return {
      ...change.cells,
      nombre: original?.nombre ?? "",
      nota: original?.nota ?? "",
    };
  });
  return [...changed, ...save.added];
}
