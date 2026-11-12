"use server";

import { refresh } from "next/cache";
import { error, type FormState, ok } from "@/lib/action-state";
import { apiPost } from "@/lib/api";
import { PERSON_LINKS, PERSON_ROLES } from "@/lib/people";
import type { Persona } from "@/lib/types";
import {
  denyUnlessAdmin,
  fromFailure,
  optional,
  text,
} from "@/lib/write-guard";

export async function createPersona(
  _previous: FormState,
  formData: FormData,
): Promise<FormState> {
  const check = await denyUnlessAdmin();
  if (check.denied) return check.denied;

  const nombre = text(formData, "nombre");
  const rol = text(formData, "rol");
  const vinculo = text(formData, "vinculo");
  if (!nombre) return error("Indique el nombre de la persona.");
  if (!PERSON_ROLES.some((item) => item.value === rol))
    return error("Elija el rol.");
  if (!PERSON_LINKS.some((item) => item.value === vinculo))
    return error("Elija el vínculo.");

  const result = await apiPost<Persona>("/personas", {
    nombre,
    rol,
    vinculo,
    nota: optional(formData, "nota"),
  });
  if (!result.ok) {
    return fromFailure(result, { 409: "Ya hay una persona con ese nombre." });
  }
  refresh();
  return ok(`Persona cargada con el código ${result.data.codigo}.`);
}

/** Deactivating deletes nothing: expenses and lots keep pointing at the person. */
export async function setPersonaActiva(
  codigo: string,
  activo: boolean,
  _previous: FormState,
  _formData: FormData,
): Promise<FormState> {
  const check = await denyUnlessAdmin();
  if (check.denied) return check.denied;

  const result = await apiPost<Persona>(
    `/personas/${encodeURIComponent(codigo)}/activo`,
    { activo },
  );
  if (!result.ok) return fromFailure(result);
  refresh();
  return ok(activo ? "Persona activada." : "Persona desactivada.");
}
