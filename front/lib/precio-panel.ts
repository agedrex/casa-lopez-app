import { parseDecimalInput } from "@/lib/format";

export const PRECIO_COOKIE = "panel_precio";
// The API accepts up to 14 digits with 4 decimals and a price above zero.
const PRECIO_VALIDO = /^\d{1,10}(\.\d{1,4})?$/;
const SOLO_CEROS = /^0+(\.0+)?$/;

/** Returns the price as the API expects it, or null when the text is not a usable price. */
export function precioValido(raw: string): string | null {
  const parsed = parseDecimalInput(raw);
  if (
    parsed === null ||
    !PRECIO_VALIDO.test(parsed) ||
    SOLO_CEROS.test(parsed)
  ) {
    return null;
  }
  return parsed;
}
