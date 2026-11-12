/**
 * The grid shows and takes percentages (21 %), the API stores fractions (0.21). Text in, text out: no float
 * touches the value. NUMERIC(6,3) holds tenths of a percent, so `3,5` is valid and `3,55` is not.
 */

/** `21` -> `0.210`, `3,5` -> `0.035`, `100` -> `1.000`; null when it is not a percentage between 0 and 100. */
export function percentToFraction(raw: string): string | null {
  const match = /^(\d{1,3})(?:[.,](\d))?$/.exec(raw.trim());
  if (!match) return null;
  const thousandths = Number(match[1] + (match[2] ?? "0"));
  if (thousandths > 1000) return null;
  const padded = String(thousandths).padStart(4, "0");
  return `${padded.slice(0, -3)}.${padded.slice(-3)}`;
}

/** `0.210` -> `21`, `0.035` -> `3,5`: how a person types it. Empty when the tax has no percentage yet. */
export function fractionToPercentInput(fraction: string | null): string {
  const match = fraction
    ? /^(\d+)(?:\.(\d{1,3}))?0*$/.exec(fraction.trim())
    : null;
  if (!match) return "";
  const thousandths = Number(match[1] + (match[2] ?? "").padEnd(3, "0"));
  const tenths = thousandths % 10;
  return `${Math.floor(thousandths / 10)}${tenths ? `,${tenths}` : ""}`;
}
