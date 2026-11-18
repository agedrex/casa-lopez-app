// View model of the consumption of a lot. Every quantity is calculated by the API
// (GET /ordenes/{codigo}/consumo); nothing here multiplies or adds. Quantities only, never money:
// the taller role reads this.

import { formatQuantity } from "./format";
import type { ConsumoLote } from "./types";

const SINGULAR: Record<string, string> = {
  m2: "m²",
  cm: "cm",
  m: "m",
  juego: "juego",
  unidad: "unidad",
};
const PLURAL: Record<string, string> = { juego: "juegos", unidad: "unidades" };

/** Unit as shown next to a quantity: `m2` → `m²`; countable units go plural unless the quantity is exactly 1. */
export function unidadTexto(unidad: string, cantidad?: string): string {
  const plural = PLURAL[unidad];
  if (plural && cantidad !== undefined && Number(cantidad) !== 1) return plural;
  return SINGULAR[unidad] ?? unidad;
}

function conUnidad(cantidad: string, unidad: string): string {
  return `${formatQuantity(cantidad)} ${unidadTexto(unidad, cantidad)}`;
}

/** `Estándar · Negro`, or just the name when the supply has no color. */
export function insumoTexto(insumo: {
  material_nombre: string;
  color: string | null;
}): string {
  return insumo.color
    ? `${insumo.material_nombre} · ${insumo.color}`
    : insumo.material_nombre;
}

export type FilaDeInsumo = {
  key: string;
  nombre: string;
  /** Quantity for one unit of the product, with its unit. */
  porUnidad: string;
  /** Quantity for the whole lot quantity of the product, with its unit. */
  total: string;
};

export type ConsumoDeProducto = {
  key: string;
  producto: string;
  titulo: string;
  cantidad: string;
  insumos: FilaDeInsumo[];
  /** True when the product has no supply loaded (nothing to count). */
  sinConsumo: boolean;
};

export type TotalDeInsumo = {
  key: string;
  nombre: string;
  total: string;
  /** How many products of the lot use this supply. */
  productos: number;
};

export type ResumenDeConsumo = {
  productos: ConsumoDeProducto[];
  totales: TotalDeInsumo[];
  /** One line for the top of the section. */
  titular: string;
  /** Products that cannot be counted, as `Nombre (código)`. */
  sinConsumo: string[];
};

function plural(n: number, uno: string, varios: string): string {
  return `${n} ${n === 1 ? uno : varios}`;
}

export function resumenDeConsumo(consumo: ConsumoLote): ResumenDeConsumo {
  const productos = consumo.productos.map((p) => ({
    key: p.item,
    producto: p.producto,
    titulo: p.producto_nombre,
    cantidad: formatQuantity(p.cantidad),
    insumos: p.insumos.map((i) => ({
      key: `${i.material}-${i.color ?? ""}`,
      nombre: insumoTexto(i),
      porUnidad: conUnidad(i.por_unidad, i.unidad),
      total: conUnidad(i.total, i.unidad),
    })),
    sinConsumo: p.insumos.length === 0,
  }));
  const totales = consumo.totales.map((t) => ({
    key: `${t.material}-${t.color ?? ""}`,
    nombre: insumoTexto(t),
    total: conUnidad(t.total, t.unidad),
    productos: t.productos.length,
  }));
  const unidades = consumo.productos.reduce(
    (a, p) => a + Number(p.cantidad),
    0,
  );
  const titular =
    totales.length === 0
      ? "Todavía no hay consumo para este lote."
      : `${plural(productos.length, "producto", "productos")} · ${plural(
          unidades,
          "unidad",
          "unidades",
        )} · ${plural(totales.length, "insumo", "insumos")} en total`;
  return {
    productos,
    totales,
    titular,
    sinConsumo: consumo.sin_consumo.map(
      (p) => `${p.producto_nombre} (${p.producto})`,
    ),
  };
}
