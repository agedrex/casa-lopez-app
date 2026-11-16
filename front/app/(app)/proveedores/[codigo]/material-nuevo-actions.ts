"use server";

import { refresh } from "next/cache";
import { error, type FormState, ok } from "@/lib/action-state";
import { apiPost } from "@/lib/api";
import type { MaterialesLote } from "@/lib/types";
import { denyUnlessWriter, fromFailure, text } from "@/lib/write-guard";

const UNIDADES = ["m2", "cm", "juego", "unidad", "USD", "m"];

/** Adds a material without a price: its prices only arrive with the supplier orders. */
export async function crearMaterialRapido(
  _previous: FormState,
  formData: FormData,
): Promise<FormState> {
  const denied = await denyUnlessWriter();
  if (denied) return denied;

  const nombre = text(formData, "nombre");
  const etapa = text(formData, "etapa");
  const unidad = text(formData, "unidad_de_consumo");
  if (!nombre) return error("Escriba el nombre del material.");
  if (!etapa) return error("Elija para qué parte del producto es.");
  if (!UNIDADES.includes(unidad)) return error("Elija cómo se mide.");

  const result = await apiPost<MaterialesLote>("/materiales/lote", {
    cambios: [],
    nuevos: [
      {
        nombre,
        etapa,
        unidad_de_consumo: unidad,
        precio: null,
        moneda: null,
        proveedor: null,
      },
    ],
  });
  if (!result.ok) {
    return fromFailure(result, { 409: "Ya hay un material con ese nombre." });
  }
  refresh();
  return ok(`Material "${nombre}" agregado. Ya está en la lista de arriba.`);
}
