"use server";

import { refresh } from "next/cache";
import { error, type FormState, ok } from "@/lib/action-state";
import { apiPostForm } from "@/lib/api";
import { denyUnlessWriter, fromFailure } from "@/lib/write-guard";
import { fotoHint } from "./foto-limites";

/**
 * Adds a photo to the model (it does not overwrite the old ones: the newest upload is the one shown). Admin only here: the
 * form is rendered only for admin, the role is checked again and the backend checks it a third time.
 */
export async function subirFoto(
  codigo: string,
  _previous: FormState,
  formData: FormData,
): Promise<FormState> {
  const denied = await denyUnlessWriter();
  if (denied) return denied;

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
    return fromFailure(result, { 413: "La foto supera los 5 MB." });
  }
  refresh();
  return ok("Foto guardada.");
}
