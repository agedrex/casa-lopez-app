// Reads the product rows of a lot form. Pure: no session, no API, no arithmetic on the amounts.
import { error, type FormState } from "./action-state";
import { parseDecimalInput } from "./format";

function positive(value: string | null): value is string {
  return value !== null && /[1-9]/.test(value);
}

export type ItemBody = {
  producto: string;
  cantidad: string;
  taller_precio_pagado_por_unidad_ars: string | null;
  taller_precio_cotizado_por_unidad_ars: string | null;
};

/** The rows of the dynamic product list arrive as parallel fields; a row with nothing typed is skipped. */
export function readItems(formData: FormData): ItemBody[] | FormState {
  const productos = formData.getAll("producto");
  const cantidades = formData.getAll("cantidad");
  const pagados = formData.getAll("pagado");
  const cotizados = formData.getAll("cotizado");
  const items: ItemBody[] = [];
  for (let i = 0; i < productos.length; i++) {
    const producto = String(productos[i] ?? "").trim();
    const rawCantidad = String(cantidades[i] ?? "").trim();
    const rawPagado = String(pagados[i] ?? "").trim();
    const rawCotizado = String(cotizados[i] ?? "").trim();
    if (!producto && !rawCantidad && !rawPagado && !rawCotizado) continue;
    const fila = `Producto ${i + 1}`;
    if (!producto) return error(`${fila}: indique el código del producto.`);
    const cantidad = parseDecimalInput(rawCantidad);
    if (!positive(cantidad)) {
      return error(`${fila}: ingrese una cantidad mayor que cero.`);
    }
    const pagado = rawPagado ? parseDecimalInput(rawPagado) : null;
    if (rawPagado && pagado === null) {
      return error(`${fila}: el precio pagado no es un número válido.`);
    }
    const cotizado = rawCotizado ? parseDecimalInput(rawCotizado) : null;
    if (rawCotizado && cotizado === null) {
      return error(`${fila}: el precio cotizado no es un número válido.`);
    }
    items.push({
      producto,
      cantidad,
      taller_precio_pagado_por_unidad_ars: pagado,
      taller_precio_cotizado_por_unidad_ars: cotizado,
    });
  }
  if (items.length === 0) return error("Agregue al menos un producto al lote.");
  return items;
}
