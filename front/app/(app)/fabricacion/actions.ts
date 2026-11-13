"use server";

import { refresh } from "next/cache";
import { redirect } from "next/navigation";
import { error, type FormState, ok } from "@/lib/action-state";
import { apiGet, apiPost } from "@/lib/api";
import { LOT_STATES, lotStateLabel, parseDecimalInput } from "@/lib/format";
import {
  consultaDeBusqueda,
  type ResultadoDeBusqueda,
  resultadosDeBusqueda,
  rutaDeBusqueda,
} from "@/lib/lote-buscador";
import { readItems } from "@/lib/lote-items";
import { type UltimoLote, ultimoLote } from "@/lib/lotes";
import type {
  HistorialDeTaller,
  OrdenDetalle,
  ProductoResumen,
} from "@/lib/types";
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

  // The form sends the place with the "who makes it" choice (INTERNA for the factory); with none, it is a workshop.
  const donde = text(formData, "donde_se_hace") || "EXTERNA";
  if (!DONDE.includes(donde)) return error("Indique dónde se hace el lote.");
  const taller = donde === "EXTERNA" ? optional(formData, "taller") : null;
  if (donde === "EXTERNA" && taller === null) {
    return error("Elija quién hace el lote: la fábrica o un taller.");
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

export type BusquedaDeProductos =
  | { status: "ok"; resultados: ResultadoDeBusqueda[]; hayMas: boolean }
  | { status: "error"; message: string };

/**
 * Finds products in the whole catalog for the new-lot form (`GET /productos?q=`, matched by the API on code,
 * name, model, leather and color). Only the admin builds lots, so anyone else is refused. Nothing is saved
 * and the answer carries no costs or prices.
 */
export async function buscarProductos(
  texto: string,
): Promise<BusquedaDeProductos> {
  const denied = await denyUnlessWriter();
  if (denied)
    return { status: "error", message: "No tiene permiso para esta acción." };
  const consulta = consultaDeBusqueda(texto);
  if (consulta === null) return { status: "ok", resultados: [], hayMas: false };
  const result = await apiGet<ProductoResumen[]>(rutaDeBusqueda(consulta));
  if (!result.ok) return { status: "error", message: result.message };
  return { status: "ok", ...resultadosDeBusqueda(result.data) };
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
