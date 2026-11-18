// View model of the single supplies table of a lot: the total per supply (GET /ordenes/{codigo}/consumo), the
// leather stock next to each leather (GET /ordenes/{codigo}/cuero) and the per-product detail. Every quantity is
// calculated by the API; nothing here adds or multiplies. Quantities only, never money: the taller reads it.
import { formatQuantity } from "@/lib/format";
import { insumoTexto, unidadTexto } from "@/lib/lote-consumo";
import { resumenDeCuero } from "@/lib/lote-cuero";
import type { ConsumoLote, LoteCuero } from "@/lib/types";

const juegos = new Intl.NumberFormat("es-AR", {
  minimumFractionDigits: 0,
  maximumFractionDigits: 2,
});

/** A quantity with its unit. Juegos (hilo y cemento) show two decimals at most: `0,2662` is `0,27 juegos`. */
export function cantidadDeInsumo(cantidad: string, unidad: string): string {
  if (unidad === "juego") {
    const redondeada = Math.round(Number(cantidad) * 100) / 100;
    return `${juegos.format(redondeada)} ${unidadTexto(unidad, String(redondeada))}`;
  }
  return `${formatQuantity(cantidad)} ${unidadTexto(unidad, cantidad)}`;
}

export type FilaDeInsumo = {
  key: string;
  nombre: string;
  /** Total for the whole lot, with its unit. */
  total: string;
  /** Leather stock message (`Alcanza · sobran 2 m²`, `Falta 0,5 m²`); null when the supply is not a leather in the stock check. */
  cuero: string | null;
  falta: boolean;
};

export type ProductoDeInsumos = {
  key: string;
  producto: string;
  titulo: string;
  cantidad: string;
  insumos: { key: string; nombre: string; porUnidad: string; total: string }[];
  sinConsumo: boolean;
};

export type TablaDeInsumos = {
  filas: FilaDeInsumo[];
  productos: ProductoDeInsumos[];
  /** True when the leather answer came with leathers: the table then has a stock column. */
  hayCuero: boolean;
  /** How many leathers are short. */
  faltan: number;
  /** One line about the leather (`Hay cuero para todo el lote.`); null without the leather answer. */
  titularCuero: string | null;
  /** Products with no supply loaded, as `Nombre (código)`. */
  sinConsumo: string[];
  /** Products without a leather consumption, as `Nombre (código)`. */
  sinConsumoDeCuero: string[];
};

export function tablaDeInsumos(
  consumo: ConsumoLote,
  cuero: LoteCuero | null,
): TablaDeInsumos {
  const resumen = cuero ? resumenDeCuero(cuero) : null;
  const stock = new Map(
    (resumen?.tarjetas ?? []).map((t) => [t.key, t] as const),
  );
  return {
    filas: consumo.totales.map((t) => {
      const tarjeta = stock.get(`${t.material}|${t.color ?? ""}`);
      return {
        key: `${t.material}-${t.color ?? ""}`,
        nombre: insumoTexto(t),
        total: cantidadDeInsumo(t.total, t.unidad),
        cuero: tarjeta?.mensaje ?? null,
        falta: tarjeta?.estado === "FALTA",
      };
    }),
    productos: consumo.productos.map((p) => ({
      key: p.item,
      producto: p.producto,
      titulo: p.producto_nombre,
      cantidad: formatQuantity(p.cantidad),
      insumos: p.insumos.map((i) => ({
        key: `${i.material}-${i.color ?? ""}`,
        nombre: insumoTexto(i),
        porUnidad: cantidadDeInsumo(i.por_unidad, i.unidad),
        total: cantidadDeInsumo(i.total, i.unidad),
      })),
      sinConsumo: p.insumos.length === 0,
    })),
    hayCuero: (resumen?.tarjetas.length ?? 0) > 0,
    faltan: resumen?.faltan ?? 0,
    titularCuero: resumen?.titular ?? null,
    sinConsumo: consumo.sin_consumo.map(
      (p) => `${p.producto_nombre} (${p.producto})`,
    ),
    sinConsumoDeCuero: (resumen?.sinConsumo ?? []).map(
      (p) => `${p.producto_nombre} (${p.producto})`,
    ),
  };
}
