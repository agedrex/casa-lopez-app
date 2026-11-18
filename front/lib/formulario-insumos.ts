import type { InsumoModelo } from "./types";

// The model keeps its herrajes and its hilo y cemento either as a single amount (USD / juegos) or, once a consumption sheet is
// validated, as supplies per unit (`modelo_insumo`), and the supplies replace the amount in the cost. So an empty amount is not
// "missing data" when the model has supplies of that stage.
const ETAPA_DEL_CAMPO: Record<string, string> = {
  herrajes_usd_por_unidad: "HERRAJES",
  hilo_y_cemento: "HILO_CEMENTO",
};

/** Whether the supplies of the model cover the consumption field `campo` (so an empty amount is not "Falta el dato"). */
export function cubiertoPorInsumos(
  campo: string,
  insumos: InsumoModelo[],
): boolean {
  const etapa = ETAPA_DEL_CAMPO[campo];
  return (
    etapa !== undefined && insumos.some((insumo) => insumo.etapa === etapa)
  );
}
