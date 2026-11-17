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
  // Only for a leather line of skins: the colour name the pieces are stored under.
  color?: string;
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

/** Presentation of an old single-size leather line (`PIEL`): the API still stores and lists it, the form no longer sends it. */
export const PRESENTACION_PIEL = "PIEL";

/** Most skins one leather row can have (the API refuses more). */
export const MAX_PIELES = 500;

const SIZE = /^\d+(?:\.\d+)?$/;
const REPEATED_SIZE = /^(\d+)x(\d+(?:\.\d+)?)$/;

type TamanosResult =
  | { ok: true; tamanos: string[] }
  | { ok: false; message: string };

/**
 * Reads the sizes text of a leather row into one m² text per skin. Sizes are separated by commas, spaces
 * or semicolons; `3x2` or `3 x 2` means three skins of 2 m². Decimals use a POINT (`2.5`): a comma is the
 * separator. Text handling only: nothing is converted to a number.
 */
export function leerTamanosDePieles(raw: string): TamanosResult {
  const tokens = raw
    .toLowerCase()
    .replace(/\s*[x×]\s*/g, "x")
    .split(/[\s,;]+/)
    .filter(Boolean);
  if (tokens.length === 0) {
    return {
      ok: false,
      message: "cargá el tamaño de cada piel en m², por ejemplo 1, 2, 2, 5.",
    };
  }
  const tooMany = {
    ok: false as const,
    message: `no puede haber más de ${MAX_PIELES} pieles por pedido.`,
  };
  const tamanos: string[] = [];
  for (const token of tokens) {
    const repeated = REPEATED_SIZE.exec(token);
    const count = repeated ? repeated[1] : "1";
    const size = repeated ? repeated[2] : token;
    if (!SIZE.test(size) || !/^\d+$/.test(count)) {
      return {
        ok: false,
        message: `"${token}" no es un tamaño válido: usá números, con punto para los decimales (2.5).`,
      };
    }
    if (!POSITIVE.test(size)) {
      return {
        ok: false,
        message: `los tamaños deben ser mayores que 0 (revisá "${token}").`,
      };
    }
    if (!POSITIVE.test(count)) {
      return {
        ok: false,
        message: `la cantidad de pieles de "${token}" debe ser 1 o más.`,
      };
    }
    // A count with more than 6 digits is far past the limit: do not expand it.
    if (count.length > 6 || tamanos.length + Number(count) > MAX_PIELES) {
      return tooMany;
    }
    for (let i = 0; i < Number(count); i++) tamanos.push(size);
  }
  return { ok: true, tamanos };
}

/** Sum of m² texts in exact decimal text (BigInt), without trailing zeros: `["2.5", "1.5"]` -> `"4"`. */
function sumarM2(tamanos: string[]): string {
  const parsed = tamanos.map((t) => parseScaled(t));
  const scale = Math.max(...parsed.map((p) => p?.scale ?? 0));
  let total = ZERO;
  for (const p of parsed) {
    if (p) total += p.digits * pow10(scale - p.scale);
  }
  const text = total.toString().padStart(scale + 1, "0");
  const whole = text.slice(0, text.length - scale);
  const fraction = text.slice(text.length - scale).replace(/0+$/, "");
  return fraction ? `${whole}.${fraction}` : whole;
}

/**
 * Live hint under the sizes input: how many skins and how many m² in total, from the text only.
 * Not money: the API stores one piece per skin.
 */
export function resumenDePieles(
  raw: string,
): { ok: true; pieles: number; m2: string } | { ok: false; message: string } {
  const result = leerTamanosDePieles(raw);
  if (!result.ok) return result;
  return {
    ok: true,
    pieles: result.tamanos.length,
    m2: sumarM2(result.tamanos),
  };
}

/** A leather row of the order form, as typed: the sizes text, the price of one m² and the colour. */
export type LineaDePieles = {
  material: string;
  tamanos: string;
  precioPorM2: string;
  color: string;
  moneda: string;
  iva: boolean;
};

/** What the API takes under `pieles`: one m² text per skin and ONE price per m² for all of them. */
export type PielesDePedidoBody = {
  material: string;
  tamanos: string[];
  precio_por_m2: string;
  moneda: string;
  iva_incluido: boolean;
  color?: string;
};

/**
 * Turns a leather row (sizes text, price per m²) into the `pieles` item the API stores. Text handling
 * only: the price is sent as typed and the API prices every skin.
 */
export function leerPielesDePedido(
  linea: LineaDePieles,
  position: number,
): { ok: true; pieles: PielesDePedidoBody } | { ok: false; message: string } {
  const label = `Línea ${position}`;
  const fail = (message: string) => ({
    ok: false as const,
    message: `${label}: ${message}`,
  });
  const material = linea.material.trim();
  if (!material) return fail("elija el material.");
  const sizes = leerTamanosDePieles(linea.tamanos);
  if (!sizes.ok) return fail(sizes.message);
  const precio = parseDecimalInput(linea.precioPorM2);
  if (precio === null) {
    return fail("ingrese el precio por m², por ejemplo 20000 o 18500,50.");
  }
  if (!["ARS", "USD"].includes(linea.moneda)) return fail("elija la moneda.");
  const color = linea.color.trim();
  return {
    ok: true,
    pieles: {
      material,
      tamanos: sizes.tamanos,
      precio_por_m2: precio,
      moneda: linea.moneda,
      iva_incluido: linea.iva,
      ...(color ? { color } : {}),
    },
  };
}

/** What arrived, for the list of received orders: `5,5 m2` for a simple line, `3 × ROLLO` for a real presentation, `3 pieles × 2 m²` for leather skins. */
export function llegoTexto(linea: {
  cantidad_presentaciones: string;
  presentacion: string;
  contenido_por_presentacion: string;
  unidad_de_consumo: string;
}): string {
  const cantidad = formatQuantity(linea.cantidad_presentaciones);
  if (linea.presentacion === PRESENTACION_PIEL) {
    const unit =
      Number(linea.cantidad_presentaciones) === 1 ? "piel" : "pieles";
    return `${cantidad} ${unit} × ${formatQuantity(linea.contenido_por_presentacion)} m²`;
  }
  const isSimple =
    linea.presentacion === PRESENTACION_SIMPLE &&
    Number(linea.contenido_por_presentacion) === 1;
  return isSimple
    ? `${cantidad} ${linea.unidad_de_consumo}`
    : `${cantidad} × ${linea.presentacion}`;
}
