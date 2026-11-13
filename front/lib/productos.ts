// Display helpers of the product screens. Pure text: no money is calculated here.
import { formatDate, formatRate } from "./format";
import type { ProductoResumen } from "./types";

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

/** Shown in the quoted-cost column of a product with no saved quote. */
export const SIN_COTIZACION = "Sin cotización";

/** Whether the API sent a saved quote for the product (older APIs do not send the fields at all). */
export function tieneCotizacion(
  producto: Pick<ProductoResumen, "costo_cotizado_ars" | "cotizacion_fecha">,
): boolean {
  return Boolean(producto.costo_cotizado_ars && producto.cotizacion_fecha);
}

/** "USD 1.545 · 12/10/2026": the dollar of the quote and its date. Text only; a whole dollar drops the ",00". */
export function cotizacionCaption(
  dolar: string | null | undefined,
  fecha: string | null | undefined,
): string {
  const rate = formatRate(dolar).replace(/,00$/, "");
  return `USD ${rate} · ${formatDate(fecha)}`;
}

/** The model of a product: its unique code (`MOD-nnnn`) and name when the API sends them, else the Excel's model code. */
export function modeloDe(
  producto: Pick<ProductoResumen, "modelo" | "modelo_codigo" | "modelo_nombre">,
): { codigo: string | null; nombre: string | null; busqueda: string | null } {
  const codigo = producto.modelo_codigo ?? null;
  const nombre = producto.modelo_nombre ?? producto.modelo ?? null;
  return { codigo, nombre, busqueda: codigo ?? producto.modelo ?? null };
}
