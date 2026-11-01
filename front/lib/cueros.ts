// Display helpers for the leather screens. Square meters and money are calculated by the API;
// nothing here adds or subtracts them. The only "math" is comparing two decimal strings.

import type { EstadoPiel, MovimientoCuero } from "./types";

const ESTADO_LABELS: Record<EstadoPiel, string> = {
  ENTERA: "Nueva",
  EN_USO: "En uso",
  RETAZO: "Retazo",
  CERRADA: "Cerrada",
};

export function estadoLabel(estado: string): string {
  return ESTADO_LABELS[estado as EstadoPiel] ?? estado;
}

const MOVIMIENTO_LABELS: Record<MovimientoCuero["tipo"], string> = {
  CORTE: "Corte",
  DESPERDICIO: "Desperdicio",
  AJUSTE: "Ajuste",
  ENTRADA: "Entrada",
};

export function movimientoLabel(tipo: string): string {
  return MOVIMIENTO_LABELS[tipo as MovimientoCuero["tipo"]] ?? tipo;
}

/** Badge tone of a skin state: scraps stand out, closed ones are muted. */
export function estadoTone(estado: string): "neutral" | "warn" | "good" {
  if (estado === "RETAZO") return "warn";
  if (estado === "CERRADA") return "neutral";
  return "good";
}

/** Group title: `Estándar · Negro`. A group without color says so. */
export function grupoTitulo(
  materialNombre: string,
  color: string | null,
): string {
  return `${materialNombre} · ${color ?? "Sin color"}`;
}

type Scaled = { int: bigint; scale: number };

// Decimal strings from the API: `12.5`, `0`, or pydantic exponent notation such as `0E-17`.
const DECIMAL = /^(-?)(\d+)(?:\.(\d+))?(?:[eE]([+-]?\d+))?$/;

function scaled(value: string): Scaled | null {
  const match = DECIMAL.exec(value.trim());
  if (!match) return null;
  const [, sign, whole, fraction = "", exponent = "0"] = match;
  const digits = BigInt(`${whole}${fraction}`);
  const int = sign ? -digits : digits;
  const scale = fraction.length - Number(exponent);
  if (scale >= 0) return { int, scale };
  return { int: int * BigInt(`1${"0".repeat(-scale)}`), scale: 0 };
}

/**
 * Compares two decimal strings without floats: -1, 0 or 1; null when either is not a decimal.
 * Comparison only, to decide what to show (nothing is added or subtracted).
 */
export function compareDecimals(
  a: string | null | undefined,
  b: string | null | undefined,
): -1 | 0 | 1 | null {
  if (a == null || b == null) return null;
  const left = scaled(a);
  const right = scaled(b);
  if (!left || !right) return null;
  const scale = Math.max(left.scale, right.scale);
  const lift = (value: Scaled) =>
    value.int * BigInt(`1${"0".repeat(scale - value.scale)}`);
  const x = lift(left);
  const y = lift(right);
  return x === y ? 0 : x > y ? 1 : -1;
}

/** Whether a decimal string is greater than zero. */
export function isPositive(value: string | null | undefined): boolean {
  return compareDecimals(value, "0") === 1;
}
