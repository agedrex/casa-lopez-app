"use server";

import { refresh } from "next/cache";
import { redirect } from "next/navigation";
import { error, type FormState, ok } from "@/lib/action-state";
import { apiPost } from "@/lib/api";
import type { TallerDetalle } from "@/lib/types";
import {
  denyUnlessWriter,
  fromFailure,
  optional,
  text,
} from "@/lib/write-guard";

export async function createTaller(
  _previous: FormState,
  formData: FormData,
): Promise<FormState> {
  const denied = await denyUnlessWriter();
  if (denied) return denied;

  const nombre = text(formData, "nombre");
  if (!nombre) return error("Indique el nombre del taller.");

  const result = await apiPost<TallerDetalle>("/talleres", {
    nombre,
    cuit: optional(formData, "cuit"),
    telefono: optional(formData, "telefono"),
    direccion: optional(formData, "direccion"),
    contacto: optional(formData, "contacto"),
    nota: optional(formData, "nota"),
  });
  if (!result.ok) {
    return fromFailure(result, {
      409: "Ya hay un taller con ese nombre o con ese CUIT.",
    });
  }
  redirect(`/talleres/${encodeURIComponent(result.data.codigo)}`);
}

/** Deactivating hides nothing and deletes nothing: the lots keep pointing at the workshop. */
export async function setActivo(
  codigo: string,
  activo: boolean,
  _previous: FormState,
  _formData: FormData,
): Promise<FormState> {
  const denied = await denyUnlessWriter();
  if (denied) return denied;

  const result = await apiPost<TallerDetalle>(
    `/talleres/${encodeURIComponent(codigo)}/activo`,
    { activo },
  );
  if (!result.ok) return fromFailure(result);
  refresh();
  return ok(activo ? "Taller activado." : "Taller desactivado.");
}
