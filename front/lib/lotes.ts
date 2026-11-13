// Pure helpers over the workshop history (`GET /talleres/{codigo}/historial`). The amounts come
// calculated by the API; the only arithmetic here is adding the quantities of repeated lines.
import type { HistorialDeTaller, LoteDeTaller } from "./types";

export type ProductoDelUltimoLote = {
  // Sum of the lines of that product in the lot.
  cantidad: string;
  // Paid price per unit of the first line (API order) that has one; null when none was paid yet.
  pagado: string | null;
};

export type UltimoLote = {
  lote: LoteDeTaller;
  productos: Record<string, ProductoDelUltimoLote>;
};

/** Newest first by the date the lot counts on (undated last), then by the highest code. */
export function ordenarLotes(lotes: LoteDeTaller[]): LoteDeTaller[] {
  return [...lotes].sort((a, b) => {
    if (a.fecha !== b.fecha) {
      if (a.fecha === null) return 1;
      if (b.fecha === null) return -1;
      return a.fecha < b.fecha ? 1 : -1;
    }
    if (a.lote === b.lote) return 0;
    return a.lote < b.lote ? 1 : -1;
  });
}

/** Adds two non-negative decimal strings exactly (no floats). */
export function sumarDecimales(a: string, b: string): string {
  const [aInt, aFrac = ""] = a.split(".");
  const [bInt, bFrac = ""] = b.split(".");
  const scale = Math.max(aFrac.length, bFrac.length);
  const scaled = (int: string, frac: string) =>
    BigInt(int + frac.padEnd(scale, "0"));
  const total = (scaled(aInt, aFrac) + scaled(bInt, bFrac))
    .toString()
    .padStart(scale + 1, "0");
  return scale === 0
    ? total
    : `${total.slice(0, total.length - scale)}.${total.slice(total.length - scale)}`;
}

/**
 * The newest lot of the workshop (any state) and, per product, what went in it. SUPUESTO: validar
 * con Robert; "newest" uses the API's lot date (delivery date when it has one, else the send date).
 * `null` when the workshop has no lots yet.
 */
export function ultimoLote(historial: HistorialDeTaller): UltimoLote | null {
  const [lote] = ordenarLotes(historial.lotes);
  if (lote === undefined) return null;
  const productos: Record<string, ProductoDelUltimoLote> = {};
  for (const producto of historial.productos) {
    for (const pago of producto.historial) {
      if (pago.lote !== lote.lote) continue;
      const previo = productos[producto.producto];
      productos[producto.producto] = previo
        ? {
            cantidad: sumarDecimales(previo.cantidad, pago.cantidad),
            pagado: previo.pagado ?? pago.pagado,
          }
        : { cantidad: pago.cantidad, pagado: pago.pagado };
    }
  }
  return { lote, productos };
}
