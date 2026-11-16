// Supplier orders: suggestions for the free-text presentation, the unit price preview and the simple line.
import { formatQuantity, parseDecimalInput } from "./format";

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

const POSITIVE = /[1-9]/;

/** A line of the simple order form, as typed: what arrived, in the unit of the material, and the price of one unit. */
export type LineaSimple = {
  material: string;
  cantidad: string;
  precio: string;
  moneda: string;
  iva: boolean;
};

export type LineaDePedidoBody = {
  material: string;
  cantidad_presentaciones: string;
  presentacion: string;
  contenido_por_presentacion: string;
  precio_por_presentacion: string;
  moneda: string;
  iva_incluido: boolean;
};

/** Presentation used by the simple form: the quantity is already in the unit of the material, so each "package" is one unit. */
export const PRESENTACION_SIMPLE = "UNIDAD";

/**
 * Turns a simple line (material, quantity, price per unit) into the line the API stores: `cantidad`
 * presentations of 1 unit each, priced per unit. Text handling only: nothing is calculated here.
 */
export function leerLineaSimpleDePedido(
  linea: LineaSimple,
  position: number,
): { ok: true; linea: LineaDePedidoBody } | { ok: false; message: string } {
  const label = `Línea ${position}`;
  const fail = (message: string) => ({
    ok: false as const,
    message: `${label}: ${message}`,
  });
  const material = linea.material.trim();
  if (!material) return fail("elija el material.");
  const cantidad = parseDecimalInput(linea.cantidad);
  if (cantidad === null || !POSITIVE.test(cantidad)) {
    return fail("la cantidad debe ser un número mayor que 0.");
  }
  const precio = parseDecimalInput(linea.precio);
  if (precio === null) {
    return fail("ingrese el precio por unidad, por ejemplo 14000 o 5857,14.");
  }
  if (!["ARS", "USD"].includes(linea.moneda)) return fail("elija la moneda.");
  return {
    ok: true,
    linea: {
      material,
      cantidad_presentaciones: cantidad,
      presentacion: PRESENTACION_SIMPLE,
      contenido_por_presentacion: "1",
      precio_por_presentacion: precio,
      moneda: linea.moneda,
      iva_incluido: linea.iva,
    },
  };
}

/** What arrived, for the list of received orders: `5,5 m2` for a simple line, `3 × ROLLO` for a real presentation. */
export function llegoTexto(linea: {
  cantidad_presentaciones: string;
  presentacion: string;
  contenido_por_presentacion: string;
  unidad_de_consumo: string;
}): string {
  const cantidad = formatQuantity(linea.cantidad_presentaciones);
  const isSimple =
    linea.presentacion === PRESENTACION_SIMPLE &&
    Number(linea.contenido_por_presentacion) === 1;
  return isSimple
    ? `${cantidad} ${linea.unidad_de_consumo}`
    : `${cantidad} × ${linea.presentacion}`;
}
