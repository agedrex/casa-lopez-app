"use server";

import { refresh } from "next/cache";
import { error, type FormState, ok } from "@/lib/action-state";
import { apiPost } from "@/lib/api";
import { parseDecimalInput } from "@/lib/format";
import type { PedidoProveedor } from "@/lib/types";
import {
  denyUnlessWriter,
  fromFailure,
  optional,
  text,
} from "@/lib/write-guard";

const MONEDAS = ["ARS", "USD"];
const POSITIVE = /[1-9]/;

type Line = {
  material: string;
  cantidad_presentaciones: string;
  presentacion: string;
  contenido_por_presentacion: string;
  precio_por_presentacion: string;
  moneda: string;
  iva_incluido: boolean;
};

/** Reads `lineas.0.material`, `lineas.1.material`... until one is missing; the first line that is wrong is reported. */
function readLines(formData: FormData): Line[] | string {
  const lines: Line[] = [];
  for (let i = 0; formData.has(`lineas.${i}.material`); i++) {
    const field = (name: string) => text(formData, `lineas.${i}.${name}`);
    const label = `Línea ${i + 1}`;
    const material = field("material");
    const cantidad = parseDecimalInput(field("cantidad_presentaciones"));
    const presentacion = field("presentacion");
    const contenido = parseDecimalInput(field("contenido_por_presentacion"));
    const precio = parseDecimalInput(field("precio_por_presentacion"));
    const moneda = field("moneda");
    if (!material) return `${label}: elija el material.`;
    if (cantidad === null || !POSITIVE.test(cantidad)) {
      return `${label}: la cantidad de presentaciones debe ser un número mayor que 0.`;
    }
    if (!presentacion) return `${label}: indique la presentación.`;
    if (contenido === null || !POSITIVE.test(contenido)) {
      return `${label}: el contenido por presentación debe ser un número mayor que 0.`;
    }
    if (precio === null) {
      return `${label}: ingrese el precio por presentación, por ejemplo 14000 o 5857,14.`;
    }
    if (!MONEDAS.includes(moneda)) return `${label}: elija la moneda.`;
    lines.push({
      material,
      cantidad_presentaciones: cantidad,
      presentacion,
      contenido_por_presentacion: contenido,
      precio_por_presentacion: precio,
      moneda,
      iva_incluido: formData.get(`lineas.${i}.iva_incluido`) === "on",
    });
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
