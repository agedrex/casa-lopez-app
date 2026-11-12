import { formatPercent } from "./format";
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
