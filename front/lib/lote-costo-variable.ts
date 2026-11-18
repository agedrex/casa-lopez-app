// How a lot moves the variable cost of its month (S5): its cost and units, and whether it already counts or counts once
// it is finished. Every figure comes calculated by the API (`costo_total`, `unidades`, `cuenta_en_costo_variable`);
// nothing is added here, the values are only formatted.

import {
  formatArs,
  formatPeriod,
  formatQuantity,
  lotStateLabel,
} from "./format";
import type { OrdenDetalle } from "./types";

export type CostoVariableDelLote = {
  /** True when the lot already counts for its month. */
  cuenta: boolean;
  titulo: string;
  texto: string;
};

type Datos = Pick<
  OrdenDetalle,
  | "cuenta_en_costo_variable"
  | "cuenta_desde_estado"
  | "periodo"
  | "unidades"
  | "costo_total"
>;

export function costoVariableDelLote(orden: Datos): CostoVariableDelLote {
  const desde = lotStateLabel(orden.cuenta_desde_estado);
  const unidades = Number(orden.unidades) === 1 ? "unidad" : "unidades";
  const aporte =
    orden.costo_total === null
      ? `${formatQuantity(orden.unidades)} ${unidades} (todavía no se pudo calcular su costo)`
      : `${formatArs(orden.costo_total)} y ${formatQuantity(orden.unidades)} ${unidades}`;
  if (orden.periodo === null) {
    return {
      cuenta: false,
      titulo: "No suma a ningún mes",
      texto: `Este lote no tiene fecha de envío ni de entrega, así que no cuenta en el costo variable de ningún mes. Pasa a contar desde que está en ${desde} y tiene fecha.`,
    };
  }
  const mes = formatPeriod(orden.periodo);
  if (orden.cuenta_en_costo_variable) {
    return {
      cuenta: true,
      titulo: `Ya suma al costo variable de ${mes}`,
      texto: `Está terminado: aporta ${aporte} al costo variable de ${mes}.`,
    };
  }
  return {
    cuenta: false,
    titulo: `Todavía no suma al costo variable de ${mes}`,
    texto: `Va a sumar ${aporte} cuando llegue a ${desde}. Hasta entonces no mueve el costo variable ni las unidades producidas.`,
  };
}
