"use server";

import { refresh } from "next/cache";
import { error, type FormState, ok } from "@/lib/action-state";
import { apiPost } from "@/lib/api";
import type { ItemCatalogo } from "@/lib/types";
import {
  denyUnlessAdmin,
  fromFailure,
  optional,
  text,
} from "@/lib/write-guard";

async function createItem(
  path: "/colores" | "/categorias",
  noun: string,
  formData: FormData,
): Promise<FormState> {
  const check = await denyUnlessAdmin();
  if (check.denied) return check.denied;

  const nombre = text(formData, "nombre");
  if (!nombre) return error(`Indique el nombre de ${noun}.`);
  const result = await apiPost<ItemCatalogo>(path, {
    nombre,
    nota: optional(formData, "nota"),
  });
  if (!result.ok) return fromFailure(result);
  refresh();
  return ok(`Cargado con el código ${result.data.codigo}.`);
}

export async function createColor(
  _previous: FormState,
  formData: FormData,
): Promise<FormState> {
  return createItem("/colores", "el color", formData);
}

export async function createCategoria(
  _previous: FormState,
  formData: FormData,
): Promise<FormState> {
  return createItem("/categorias", "la categoría", formData);
}
