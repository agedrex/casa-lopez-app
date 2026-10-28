"use server";

import { redirect } from "next/navigation";
import { error, type FormState } from "@/lib/action-state";
import { apiPost } from "@/lib/api";
import type { Ficha } from "@/lib/types";
import {
  denyUnlessWriter,
  fromFailure,
  optional,
  text,
} from "@/lib/write-guard";

const QUIEN = ["EXTERNA", "INTERNA"];

export async function createProducto(
  _previous: FormState,
  formData: FormData,
): Promise<FormState> {
  const denied = await denyUnlessWriter();
  if (denied) return denied;

  const esKit = formData.get("es_kit") === "on";
  const modelo = optional(formData, "modelo");
  const quien = text(formData, "quien_lo_confecciona");
  if (!modelo && !esKit) {
    return error("Elija el modelo (solo un kit puede ir sin modelo).");
  }
  if (!text(formData, "cuero") && !esKit) return error("Elija el cuero.");
  if (!QUIEN.includes(quien)) return error("Indique quién lo confecciona.");

  const result = await apiPost<Ficha>("/productos", {
    modelo,
    cuero: optional(formData, "cuero"),
    color: optional(formData, "color"),
    quien_lo_confecciona: quien,
    fecha_de_alta: optional(formData, "fecha_de_alta"),
    nombre_propio: optional(formData, "nombre_propio"),
    es_kit: esKit,
    nota: optional(formData, "nota"),
  });
  if (!result.ok) return fromFailure(result);
  redirect(`/productos/${encodeURIComponent(result.data.codigo)}`);
}
