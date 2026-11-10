// Display helpers of the product screens. Pure text: no money is calculated here.

/** Shown when a product has no cost and the API sent no warning to explain it. */
export const COSTO_SIN_CAUSA = "No se pudo calcular el costo de hoy.";

/**
 * Names typed in the Excel carry runs of spaces (and tabs or line breaks). Only the display
 * collapses them: the stored name is never modified.
 */
export function collapseSpaces(text: string): string {
  return text.replace(/\s+/g, " ").trim();
}

/** Why a product has no cost: the first real warning of the API, else a neutral text. */
export function costoFaltante(avisos: readonly string[]): string {
  const first = avisos.map(collapseSpaces).find((aviso) => aviso !== "");
  return first ?? COSTO_SIN_CAUSA;
}
