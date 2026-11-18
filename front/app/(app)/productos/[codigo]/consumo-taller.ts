// The "Consumo" rows the taller sees on a product sheet: quantities only. The taller never gets money, so the
// amounts in USD of the herrajes are left out, and hilo y cemento is a quantity in juegos (two decimals at most),
// not the price of the dollar. Display only: nothing is calculated here.
import { type ConsumoRow, consumoRows } from "@/lib/ficha-consumo";
import type { Ficha, ModeloDetalle } from "@/lib/types";

const NO_AMOUNT = "—";
const MISSING = "Falta el dato";

const twoDecimals = new Intl.NumberFormat("es-AR", {
  minimumFractionDigits: 0,
  maximumFractionDigits: 2,
});

function juegos(value: string | null | undefined): string {
  if (value === null || value === undefined) return MISSING;
  // Same plural rule as the lot consumption: exactly 1 is singular.
  return `${twoDecimals.format(Number(value))} ${Number(value) === 1 ? "juego" : "juegos"}`;
}

export function consumoRowsDelTaller(
  ficha: Ficha,
  modelo: ModeloDetalle | null,
): ConsumoRow[] {
  const rows = consumoRows(ficha, modelo);
  // Without the model only the recipe lines are listed, and those are quantities already.
  if (modelo === null) return rows;
  return rows.map((row) => {
    if (row.insumo === "Hilo y cemento") {
      return { ...row, porUnidad: juegos(modelo.hilo_y_cemento) };
    }
    if (row.insumo === "Herrajes") return { ...row, porUnidad: NO_AMOUNT };
    return row;
  });
}
