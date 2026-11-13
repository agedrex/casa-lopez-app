// Supplier orders: suggestions for the free-text presentation and the unit price preview.

/** Suggested presentations. The field is free text: the API accepts any non-empty value. */
export const PRESENTACIONES = [
  "CARRETE",
  "CAJA",
  "ROLLO",
  "BOLSA",
  "UNIDAD",
  "PLANCHA",
] as const;

/** Decimal places of a stored unit price (`money()` in the backend: NUMERIC(14,4)). */
const PRICE_SCALE = 4;

// BigInt literals (0n) need a newer compile target than this project uses.
const ZERO = BigInt(0);
const TWO = BigInt(2);
const pow10 = (exponent: number) => BigInt(`1${"0".repeat(exponent)}`);

const POSITIVE_DECIMAL = /^(\d+)(?:\.(\d+))?$/;

/** `"12.50"` -> digits and scale as BigInt, or null when it is not a plain non-negative decimal. */
function parseScaled(raw: string): { digits: bigint; scale: number } | null {
  const match = POSITIVE_DECIMAL.exec(raw.trim().replace(",", "."));
  if (!match) return null;
  const fraction = match[2] ?? "";
  return { digits: BigInt(match[1] + fraction), scale: fraction.length };
}

/**
 * Preview of the unit price of an order line: price per presentation / content per presentation,
 * in exact decimal text (BigInt, no floating point), rounded half up to 4 decimals. Accepts a comma
 * or a point as decimal separator. Null while either value is missing, not a number, or the content is 0.
 * Only a hint for the person: the API calculates and stores the real price.
 */
export function unitPricePreview(
  priceText: string,
  contentText: string,
): string | null {
  const price = parseScaled(priceText);
  const content = parseScaled(contentText);
  if (!price || !content || content.digits === ZERO) return null;

  // price.digits / 10^ps  /  (content.digits / 10^cs), scaled by 10^PRICE_SCALE.
  const numerator = price.digits * pow10(content.scale + PRICE_SCALE);
  const denominator = content.digits * pow10(price.scale);
  const rounded = (numerator * TWO + denominator) / (denominator * TWO);

  const text = rounded.toString().padStart(PRICE_SCALE + 1, "0");
  const whole = text.slice(0, -PRICE_SCALE);
  return `${whole}.${text.slice(-PRICE_SCALE)}`;
}
