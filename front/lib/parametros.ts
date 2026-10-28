// Display rules for the parameters screen. The ranges themselves are enforced by the API
// (servicios.validar_valor_de_parametro); this only decides what the form offers.
import { formatQuantity, formatRate } from "./format";
import type { Parametro } from "./types";

export const PARAMETER_STATES = [
  "Pendiente",
  "Propuesta",
  "Confirmado",
] as const;

const NUMERIC_UNITS = ["%", "ARS/USD", "m2"];
const TEXT_UNIT = "AAAA-MM";

export function isTextParameter(parametro: Parametro): boolean {
  return parametro.unidad === TEXT_UNIT;
}

/** Calculated parameters (and units without a validation rule) are shown but not edited. */
export function isEditable(parametro: Parametro): boolean {
  if ((parametro.fuente_estado ?? "").toLowerCase().startsWith("calculado")) {
    return false;
  }
  return (
    isTextParameter(parametro) || NUMERIC_UNITS.includes(parametro.unidad ?? "")
  );
}

export function unitLabel(unit: string | null): string {
  if (unit === "%") return "fracción: 0,05 es 5 %";
  if (unit === "AAAA-MM") return "mes, AAAA-MM";
  if (unit === "m2") return "m²";
  return unit ?? "";
}

export function displayValue(parametro: Parametro): string {
  if (parametro.valor_texto !== null) return parametro.valor_texto;
  if (parametro.valor === null) return "Sin cargar";
  return parametro.unidad === "ARS/USD"
    ? formatRate(parametro.valor)
    : formatQuantity(parametro.valor);
}

/** `Confirmado: Robert 27/10` -> state `Confirmado` and note `Robert 27/10`. */
export function splitStatus(fuenteEstado: string | null): {
  state: (typeof PARAMETER_STATES)[number] | "";
  note: string;
} {
  const text = (fuenteEstado ?? "").trim();
  const state = PARAMETER_STATES.find(
    (candidate) => text === candidate || text.startsWith(`${candidate}:`),
  );
  if (!state) return { state: "", note: text };
  return { state, note: text.slice(state.length).replace(/^:\s*/, "") };
}
