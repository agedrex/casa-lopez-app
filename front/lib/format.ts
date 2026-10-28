// Display-only formatting of decimal strings coming from the API.
// No arithmetic happens here: Intl formats the exact decimal string.

const NONE = "—";

const ars = new Intl.NumberFormat("es-AR", {
  style: "currency",
  currency: "ARS",
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
});

const usd = new Intl.NumberFormat("es-AR", {
  style: "currency",
  currency: "USD",
  currencyDisplay: "code",
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
});

const quantity = new Intl.NumberFormat("es-AR", {
  minimumFractionDigits: 0,
  maximumFractionDigits: 4,
});

const rate = new Intl.NumberFormat("es-AR", {
  minimumFractionDigits: 2,
  maximumFractionDigits: 4,
});

// pydantic serializes Decimal with str(), so exponent notation such as "0E-17" can appear.
const DECIMAL = /^-?\d+(\.\d+)?([eE][+-]?\d+)?$/;

function asDecimal(
  value: string | null | undefined,
): Intl.StringNumericLiteral | null {
  if (value === null || value === undefined) return null;
  return DECIMAL.test(value) ? (value as Intl.StringNumericLiteral) : null;
}

export function formatArs(value: string | null | undefined): string {
  const decimal = asDecimal(value);
  return decimal === null ? NONE : ars.format(decimal);
}

export function formatUsd(value: string | null | undefined): string {
  const decimal = asDecimal(value);
  return decimal === null ? NONE : usd.format(decimal);
}

export function formatQuantity(value: string | null | undefined): string {
  const decimal = asDecimal(value);
  return decimal === null ? NONE : quantity.format(decimal);
}

export function formatRate(value: string | null | undefined): string {
  const decimal = asDecimal(value);
  return decimal === null ? NONE : rate.format(decimal);
}

/** `2026-09-01` -> `01/09/2026`, without going through Date (no timezone shifts). */
export function formatDate(value: string | null | undefined): string {
  if (!value) return NONE;
  const match = /^(\d{4})-(\d{2})-(\d{2})/.exec(value);
  return match ? `${match[3]}/${match[2]}/${match[1]}` : value;
}

const percent = new Intl.NumberFormat("es-AR", {
  minimumFractionDigits: 0,
  maximumFractionDigits: 2,
});

/** The API sends the percentage already calculated (`"53.33"`); this only formats it. */
export function formatPercent(value: string | null | undefined): string {
  const decimal = asDecimal(value);
  return decimal === null ? NONE : `${percent.format(decimal)} %`;
}

/** Money in its own currency, as the API stores it. */
export function formatMoney(
  value: string | null | undefined,
  currency: string,
): string {
  return currency === "USD" ? formatUsd(value) : formatArs(value);
}

/**
 * Turns what a person types in an amount field into a plain decimal string for the API,
 * or null. `1545,5` and `1545.5` are accepted; thousands separators (`1.545,50`) are not.
 * Pure text handling: the amount is never converted to a number.
 */
export function parseDecimalInput(raw: string): string | null {
  const text = raw.trim().replace(",", ".");
  return /^\d+(\.\d+)?$/.test(text) ? text : null;
}

/** Today in Buenos Aires as `YYYY-MM-DD` (the server runs in UTC). */
export function todayIso(): string {
  return new Intl.DateTimeFormat("en-CA", {
    timeZone: "America/Argentina/Buenos_Aires",
  }).format(new Date());
}

/** Stage order of the quote, shared by the pages. */
export const STAGE_ORDER = [
  "CUERO",
  "FORRO",
  "FLEX",
  "GOMA_EVA",
  "HERRAJES",
  "HILO_CEMENTO",
  "CORTE",
  "CONFECCION",
];

const STAGE_LABELS: Record<string, string> = {
  CUERO: "Cuero",
  FORRO: "Forro",
  FLEX: "Flex",
  GOMA_EVA: "Goma EVA",
  HERRAJES: "Herrajes",
  HILO_CEMENTO: "Hilo y cemento",
  CORTE: "Corte",
  CONFECCION: "Confección",
};

// Stage codes are kept as the sheet names them; unknown ones are shown as-is.
export function stageLabel(code: string): string {
  return STAGE_LABELS[code] ?? code;
}

const LIFECYCLE_LABELS: Record<string, string> = {
  EN_DEFINICION: "En definición",
  COTIZADO: "Cotizado",
  EN_PRODUCCION: "En producción",
  PRODUCIDO: "Producido",
};

export function lifecycleLabel(code: string): string {
  return LIFECYCLE_LABELS[code] ?? code;
}

const QUOTE_TYPE_LABELS: Record<string, string> = {
  INICIAL: "Inicial",
  RECOTIZACION: "Recotización",
  FINAL: "Final",
};

export function quoteTypeLabel(code: string): string {
  return QUOTE_TYPE_LABELS[code] ?? code;
}

const LOT_STATE_LABELS: Record<string, string> = {
  PLANIFICADA: "Planificada",
  EN_CORTE: "En corte",
  CORTADA: "Cortada",
  EN_CONFECCION: "En confección",
  LISTA: "Lista",
  CERRADA: "Cerrada",
};

/** Lot states in the order of the cycle (the API accepts any of them except after CERRADA). */
export const LOT_STATES = Object.keys(LOT_STATE_LABELS);

export function lotStateLabel(code: string): string {
  return LOT_STATE_LABELS[code] ?? code;
}

export function whereLabel(code: string): string {
  return code === "EXTERNA"
    ? "En taller"
    : code === "INTERNA"
      ? "En casa"
      : code;
}

const EXPENSE_CATEGORY_LABELS: Record<string, string> = {
  SUELDOS: "Sueldos",
  CARGAS_SOCIALES: "Cargas sociales",
  ALQUILER: "Alquiler",
  SERVICIOS: "Servicios",
  IMPUESTOS_FIJOS: "Impuestos fijos",
  OTROS: "Otros",
};

export const EXPENSE_CATEGORIES = Object.keys(EXPENSE_CATEGORY_LABELS);

export function expenseCategoryLabel(code: string): string {
  return EXPENSE_CATEGORY_LABELS[code] ?? code;
}

/** `2026-10` -> `10/2026`. */
export function formatPeriod(value: string | null | undefined): string {
  const match = /^(\d{4})-(\d{2})$/.exec(value ?? "");
  return match ? `${match[2]}/${match[1]}` : (value ?? NONE);
}

/**
 * Whether two decimal strings written by people or by the API are the same number, compared as text
 * (`0.250000` = `0,25`; empty = empty). No arithmetic: only separators and trailing zeros are dropped.
 */
export function sameDecimalText(
  a: string | null | undefined,
  b: string | null | undefined,
): boolean {
  const normalize = (value: string | null | undefined) => {
    const text = (value ?? "").trim().replace(",", ".");
    return text.includes(".") ? text.replace(/\.?0+$/, "") : text;
  };
  return normalize(a) === normalize(b);
}
