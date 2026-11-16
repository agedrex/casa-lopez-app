"use server";

import { refresh } from "next/cache";
import { redirect } from "next/navigation";
import { error, type FormState, ok } from "@/lib/action-state";
import { apiPostForm } from "@/lib/api";
import { canFillFormularios } from "@/lib/permissions";
import { getSession } from "@/lib/session";
import { fromFailure } from "@/lib/write-guard";
import { fotoHint } from "./foto-limites";

/**
 * Adds a photo to the model (it does not overwrite the old ones: the newest upload is the one shown). Admin and taller: the
 * form is rendered only where the role may use it, the role is checked again here and the backend checks it a third time
 * (a taller only reaches a model whose sheet is ENVIADO or that it created: 403 otherwise).
 */
export async function subirFoto(
  codigo: string,
  _previous: FormState,
  formData: FormData,
): Promise<FormState> {
  const session = await getSession();
  if (!session) redirect("/login");
  if (!canFillFormularios(session.user.role)) {
    return error("No tiene permiso para esta acción.");
  }

  const file = formData.get("archivo");
  if (!(file instanceof File) || file.size === 0) {
    return error("Elija una foto para subir.");
  }
  const hint = fotoHint(file);
  if (hint) return error(`No se puede subir esta foto: ${hint}.`);

  const body = new FormData();
  body.append("archivo", file, file.name);
  const result = await apiPostForm(
    `/modelos/${encodeURIComponent(codigo)}/foto`,
    body,
  );
  if (!result.ok) {
    return fromFailure(result, {
      403: "No tenés permiso para subir la foto de este modelo.",
      413: "La foto supera los 5 MB.",
    });
  }
  refresh();
  return ok("Foto guardada.");
}
