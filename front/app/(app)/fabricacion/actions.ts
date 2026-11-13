"use server";

import { refresh } from "next/cache";
import { redirect } from "next/navigation";
import { error, type FormState, ok } from "@/lib/action-state";
import { apiGet, apiPost } from "@/lib/api";
import { LOT_STATES, lotStateLabel, parseDecimalInput } from "@/lib/format";
import { readItems } from "@/lib/lote-items";
import { type UltimoLote, ultimoLote } from "@/lib/lotes";
import type { HistorialDeTaller, OrdenDetalle } from "@/lib/types";
import {
  denyUnlessVoice,
  denyUnlessWriter,
  fromFailure,
  optional,
  text,
} from "@/lib/write-guard";

const DONDE = ["EXTERNA", "INTERNA"];

export async function createOrden(
  _previous: FormState,
  formData: FormData,
): Promise<FormState> {
  const denied = await denyUnlessWriter();
  if (denied) return denied;

  // The simple form does not send the place: a lot is made at a workshop unless "Más opciones" says otherwise.
  const donde = text(formData, "donde_se_hace") || "EXTERNA";
  if (!DONDE.includes(donde)) return error("Indique dónde se hace el lote.");
  const taller = donde === "EXTERNA" ? optional(formData, "taller") : null;
  if (donde === "EXTERNA" && taller === null) {
    return error("Elija el taller del lote.");
  }
  const items = readItems(formData);
  if (!Array.isArray(items)) return items;

  const result = await apiPost<{ codigo: string }>("/ordenes", {
    donde_se_hace: donde,
    // Only the field that matches the place travels: a workshop for EXTERNA, a person for INTERNA.
    taller,
    persona: donde === "INTERNA" ? optional(formData, "persona") : null,
    fecha_de_envio: optional(formData, "fecha_de_envio"),
    nota: optional(formData, "nota"),
    items,
  });
  if (!result.ok) return fromFailure(result);
  redirect(`/fabricacion/${encodeURIComponent(result.data.codigo)}`);
}

export type UltimoLoteResult =
  | { status: "ok"; ultimo: UltimoLote | null }
  | { status: "hidden" };

/**
 * Last lot of a workshop, for the comparison panel of the new-lot form. The history carries the prices
 * paid and is admin only: for anyone else, or on any failure, the panel is simply hidden.
 */
export async function cargarUltimoLote(
  taller: string,
): Promise<UltimoLoteResult> {
  const denied = await denyUnlessWriter();
  if (denied || !taller) return { status: "hidden" };
  const result = await apiGet<HistorialDeTaller>(
    `/talleres/${encodeURIComponent(taller)}/historial`,
  );
  if (!result.ok) return { status: "hidden" };
  return { status: "ok", ultimo: ultimoLote(result.data) };
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
  const denied = await denyUnlessVoice();
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
    return error("Ingresá el precio pagado (o lo que pidió el taller).");
  }

  const result = await apiPost<OrdenDetalle>(
    `/ordenes/${encodeURIComponent(codigo)}/items/${encodeURIComponent(item)}/precios`,
    body,
  );
  if (!result.ok) return fromFailure(result);
  refresh();
  return ok("Precios del taller guardados.");
}
