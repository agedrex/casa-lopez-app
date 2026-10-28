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
