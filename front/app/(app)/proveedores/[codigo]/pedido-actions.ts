"use server";

import { refresh } from "next/cache";
import { error, type FormState, ok } from "@/lib/action-state";
import { apiPost } from "@/lib/api";
import {
  type LineaDePedidoBody,
  leerLineaSimpleDePedido,
  leerPielesDePedido,
  type PielesDePedidoBody,
} from "@/lib/pedidos";
import type { PedidoProveedor } from "@/lib/types";
import {
  denyUnlessWriter,
  fromFailure,
  optional,
  text,
} from "@/lib/write-guard";

/**
 * Reads `lineas.0.material`, `lineas.1.material`... until one is missing; the first row that is wrong is
 * reported. Leather rows (the ones with a sizes field) go under `pieles`, the rest under `lineas`.
 */
function readLines(
  formData: FormData,
): { lineas: LineaDePedidoBody[]; pieles: PielesDePedidoBody[] } | string {
  const lineas: LineaDePedidoBody[] = [];
  const pieles: PielesDePedidoBody[] = [];
  for (let i = 0; formData.has(`lineas.${i}.material`); i++) {
    const field = (name: string) => text(formData, `lineas.${i}.${name}`);
    const iva = formData.get(`lineas.${i}.iva`) === "on";
    // Only a leather row renders the `tamanos` field.
    if (formData.has(`lineas.${i}.tamanos`)) {
      const result = leerPielesDePedido(
        {
          material: field("material"),
          tamanos: field("tamanos"),
          precioPorM2: field("precio_por_m2"),
          color: field("color"),
          moneda: field("moneda"),
          iva,
        },
        i + 1,
      );
      if (!result.ok) return result.message;
      pieles.push(result.pieles);
    } else {
      const result = leerLineaSimpleDePedido(
        {
          material: field("material"),
          cantidad: field("cantidad"),
          precio: field("precio"),
          moneda: field("moneda"),
          iva,
        },
        i + 1,
      );
      if (!result.ok) return result.message;
      lineas.push(result.linea);
    }
  }
  return { lineas, pieles };
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
  const read = readLines(formData);
  if (typeof read === "string") return error(read);
  const { lineas, pieles } = read;
  if (lineas.length === 0 && pieles.length === 0) {
    return error("Agregue al menos un material.");
  }

  const result = await apiPost<PedidoProveedor>(
    `/proveedores/${encodeURIComponent(codigo)}/pedidos`,
    {
      fecha_de_recepcion: fecha,
      remito: optional(formData, "remito"),
      nota: optional(formData, "nota"),
      lineas,
      pieles,
    },
  );
  if (!result.ok) {
    return fromFailure(result, { 404: "No existe ese proveedor." });
  }
  refresh();
  return ok(`Pedido ${result.data.codigo} registrado.`);
}
