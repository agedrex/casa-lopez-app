import { formatPercent } from "@/lib/format";

/**
 * The API sends the margin as a fraction (`"0.4"` = 40 %). `formatPercent` wants the percentage
 * already expressed (`"40"`), so this only moves the decimal point two places in the text:
 * no number is built and no arithmetic happens.
 */
export function formatMargenPct(fraction: string | null): string {
  const match = fraction ? /^(-?)(\d+)(?:\.(\d+))?$/.exec(fraction) : null;
  if (!match) return formatPercent(null);
  const [, sign, whole, decimals = ""] = match;
  const shifted = decimals.padEnd(2, "0");
  const integer = `${whole}${shifted.slice(0, 2)}`.replace(/^0+(?=\d)/, "");
  const rest = shifted.slice(2);
  return formatPercent(`${sign}${integer}${rest ? `.${rest}` : ""}`);
}
