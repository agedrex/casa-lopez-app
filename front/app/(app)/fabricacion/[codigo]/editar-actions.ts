"use server";

import { refresh } from "next/cache";
import { type FormState, ok } from "@/lib/action-state";
import { apiDelete, apiPut } from "@/lib/api";
import { readCantidad } from "@/lib/lote-editar";
import type { OrdenDetalle } from "@/lib/types";
import { denyUnlessWriter, fromFailure } from "@/lib/write-guard";

const rutaDelRenglon = (codigo: string, item: string) =>
  `/ordenes/${encodeURIComponent(codigo)}/items/${encodeURIComponent(item)}`;

/** Admin only (the API refuses everyone else too): sets the units of one line of an open lot. */
export async function changeCantidad(
  codigo: string,
  item: string,
  _previous: FormState,
  formData: FormData,
): Promise<FormState> {
  const denied = await denyUnlessWriter();
  if (denied) return denied;

  const cantidad = readCantidad(formData);
  if (typeof cantidad !== "string") return cantidad;

  const result = await apiPut<OrdenDetalle>(rutaDelRenglon(codigo, item), {
    cantidad,
  });
  if (!result.ok) return fromFailure(result);
  refresh();
  return ok("Cantidad actualizada.");
}

/** Admin only: takes a line out of an open lot. The row is kept by the API with its log; nothing is deleted. */
export async function removeItem(
  codigo: string,
  item: string,
  _previous: FormState,
  _formData: FormData,
): Promise<FormState> {
  const denied = await denyUnlessWriter();
  if (denied) return denied;

  const result = await apiDelete<OrdenDetalle>(rutaDelRenglon(codigo, item));
  if (!result.ok) return fromFailure(result);
  refresh();
  return ok("Producto quitado del lote.");
}
