"use server";

import { refresh } from "next/cache";
import { error, type FormState, ok } from "@/lib/action-state";
import { apiPost } from "@/lib/api";
import { type LineaDePedidoBody, leerLineaSimpleDePedido } from "@/lib/pedidos";
import type { PedidoProveedor } from "@/lib/types";
import {
  denyUnlessWriter,
  fromFailure,
  optional,
  text,
} from "@/lib/write-guard";

/** Reads `lineas.0.material`, `lineas.1.material`... until one is missing; the first line that is wrong is reported. */
function readLines(formData: FormData): LineaDePedidoBody[] | string {
  const lines: LineaDePedidoBody[] = [];
  for (let i = 0; formData.has(`lineas.${i}.material`); i++) {
    const field = (name: string) => text(formData, `lineas.${i}.${name}`);
    const result = leerLineaSimpleDePedido(
      {
        material: field("material"),
        cantidad: field("cantidad"),
        precio: field("precio"),
        moneda: field("moneda"),
        iva: formData.get(`lineas.${i}.iva`) === "on",
      },
      i + 1,
    );
    if (!result.ok) return result.message;
    lines.push(result.linea);
  }
  return lines;
}

/**
 * Registers an order that arrived from the supplier. The API creates the unit price of each line and
 * saves everything or nothing; a refused line (for example a price already loaded for that date) is
 * named in its message. Orders are only added: there is no edit and no delete.
 */
export async function createPedidoDeProveedor(
  codigo: string,
  _previous: FormState,
  formData: FormData,
): Promise<FormState> {
  const denied = await denyUnlessWriter();
  if (denied) return denied;

  const fecha = text(formData, "fecha_de_recepcion");
  if (!fecha) return error("Indique la fecha de recepción.");
  const lineas = readLines(formData);
  if (typeof lineas === "string") return error(lineas);
  if (lineas.length === 0) return error("Agregue al menos un material.");

  const result = await apiPost<PedidoProveedor>(
    `/proveedores/${encodeURIComponent(codigo)}/pedidos`,
    {
      fecha_de_recepcion: fecha,
      remito: optional(formData, "remito"),
      nota: optional(formData, "nota"),
      lineas,
    },
  );
  if (!result.ok) {
    return fromFailure(result, { 404: "No existe ese proveedor." });
  }
  refresh();
  return ok(`Pedido ${result.data.codigo} registrado.`);
}
