"use server";

import { refresh } from "next/cache";
import { redirect } from "next/navigation";
import { error, type FormState, ok } from "@/lib/action-state";
import { apiPost } from "@/lib/api";
import { LOT_STATES, lotStateLabel, parseDecimalInput } from "@/lib/format";
import type { OrdenDetalle } from "@/lib/types";
import {
  denyUnlessWriter,
  fromFailure,
  optional,
  text,
} from "@/lib/write-guard";

const DONDE = ["EXTERNA", "INTERNA"];

function positive(value: string | null): value is string {
  return value !== null && /[1-9]/.test(value);
}

type ItemBody = {
  producto: string;
  cantidad: string;
  taller_precio_cotizado_por_unidad_ars: string | null;
};

/** The rows of the dynamic product list arrive as parallel fields; a row with nothing typed is skipped. */
function readItems(formData: FormData): ItemBody[] | FormState {
  const productos = formData.getAll("producto");
  const cantidades = formData.getAll("cantidad");
  const cotizados = formData.getAll("cotizado");
  const items: ItemBody[] = [];
  for (let i = 0; i < productos.length; i++) {
    const producto = String(productos[i] ?? "").trim();
    const rawCantidad = String(cantidades[i] ?? "").trim();
    const rawCotizado = String(cotizados[i] ?? "").trim();
    if (!producto && !rawCantidad && !rawCotizado) continue;
    const fila = `Producto ${i + 1}`;
    if (!producto) return error(`${fila}: indique el código del producto.`);
    const cantidad = parseDecimalInput(rawCantidad);
    if (!positive(cantidad)) {
      return error(`${fila}: ingrese una cantidad mayor que cero.`);
    }
    const cotizado = rawCotizado ? parseDecimalInput(rawCotizado) : null;
    if (rawCotizado && cotizado === null) {
      return error(`${fila}: el precio cotizado no es un número válido.`);
    }
    items.push({
      producto,
      cantidad,
      taller_precio_cotizado_por_unidad_ars: cotizado,
    });
  }
  if (items.length === 0) return error("Agregue al menos un producto al lote.");
  return items;
}

export async function createOrden(
  _previous: FormState,
  formData: FormData,
): Promise<FormState> {
  const denied = await denyUnlessWriter();
  if (denied) return denied;

  const donde = text(formData, "donde_se_hace");
  if (!DONDE.includes(donde)) return error("Indique dónde se hace el lote.");
  const items = readItems(formData);
  if (!Array.isArray(items)) return items;

  const result = await apiPost<{ codigo: string }>("/ordenes", {
    donde_se_hace: donde,
    // Only the field that matches the place travels: a workshop for EXTERNA, a person for INTERNA.
    taller: donde === "EXTERNA" ? optional(formData, "taller") : null,
    persona: donde === "INTERNA" ? optional(formData, "persona") : null,
    fecha_de_envio: optional(formData, "fecha_de_envio"),
    nota: optional(formData, "nota"),
    items,
  });
  if (!result.ok) return fromFailure(result);
  redirect(`/fabricacion/${encodeURIComponent(result.data.codigo)}`);
}

export async function changeEstado(
  codigo: string,
  _previous: FormState,
  formData: FormData,
): Promise<FormState> {
  const denied = await denyUnlessWriter();
  if (denied) return denied;

  const estado = text(formData, "estado");
  const fecha = text(formData, "fecha");
  const entrega = optional(formData, "fecha_de_entrega");
  if (!LOT_STATES.includes(estado)) return error("Elija el nuevo estado.");
  if (!fecha) return error("Indique la fecha del cambio de estado.");
  if (estado === "CERRADA" && !entrega) {
    return error(
      "Para cerrar el lote indique la fecha de entrega: es la que cierra la cotización final.",
    );
  }

  const result = await apiPost<OrdenDetalle>(
    `/ordenes/${encodeURIComponent(codigo)}/estado`,
    {
      estado,
      fecha,
      quien: optional(formData, "quien"),
      fecha_de_entrega: entrega,
    },
  );
  if (!result.ok) {
    return fromFailure(result, {
      409: "El lote ya está cerrado o ya está en ese estado: no se puede cambiar.",
    });
  }
  refresh();
  return ok(`Estado cambiado a «${lotStateLabel(estado)}».`);
}

export async function addItem(
  codigo: string,
  _previous: FormState,
  formData: FormData,
): Promise<FormState> {
  const denied = await denyUnlessWriter();
  if (denied) return denied;

  const items = readItems(formData);
  if (!Array.isArray(items)) return items;
  // One product per submission here (the form has one row), so a single call is enough.
  const [item] = items;
  const result = await apiPost<OrdenDetalle>(
    `/ordenes/${encodeURIComponent(codigo)}/items`,
    item,
  );
  if (!result.ok) return fromFailure(result);
  refresh();
  return ok("Producto agregado al lote.");
}

export async function savePrecios(
  codigo: string,
  item: string,
  _previous: FormState,
  formData: FormData,
): Promise<FormState> {
  const denied = await denyUnlessWriter();
  if (denied) return denied;

  const body: { cotizado?: string; pagado?: string } = {};
  for (const [field, label] of [
    ["cotizado", "cotizado"],
    ["pagado", "pagado"],
  ] as const) {
    const raw = text(formData, field);
    if (!raw) continue;
    const value = parseDecimalInput(raw);
    if (value === null)
      return error(`El precio ${label} no es un número válido.`);
    body[field] = value;
  }
  if (!body.cotizado && !body.pagado) {
    return error("Ingrese el precio cotizado, el pagado o los dos.");
  }

  const result = await apiPost<OrdenDetalle>(
    `/ordenes/${encodeURIComponent(codigo)}/items/${encodeURIComponent(item)}/precios`,
    body,
  );
  if (!result.ok) return fromFailure(result);
  refresh();
  return ok("Precios del taller guardados.");
}
