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

/** Lifecycle states the product list can be filtered by, in the order of the cycle (the API accepts only these). */
export const LIFECYCLE_STATES = [
  "EN_DEFINICION",
  "COTIZADO",
  "EN_PRODUCCION",
  "PRODUCIDO",
] as const;

export type LifecycleState = (typeof LIFECYCLE_STATES)[number];

/** A state read from the URL: anything that is not one of the four is dropped instead of sent (the API would answer 422). */
export function parseLifecycleState(value: string): LifecycleState | "" {
  return LIFECYCLE_STATES.find((state) => state === value) ?? "";
}
