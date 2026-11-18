"use server";

import { refresh } from "next/cache";
import { redirect } from "next/navigation";
import { error, type FormState, ok } from "@/lib/action-state";
import { apiPost } from "@/lib/api";
import { lotStateLabel } from "@/lib/format";
import { siguienteEstadoDelTaller } from "@/lib/lote-estados";
import { canWrite, hasRole } from "@/lib/permissions";
import { getSession } from "@/lib/session";
import type { OrdenDetalle } from "@/lib/types";
import { fromFailure } from "@/lib/write-guard";

/**
 * The taller moves a lot to its next state (one step, dated today by the API, which also records who did it).
 * Admin and taller only: anyone can post to a server action, so the role is checked here and the API checks it again.
 */
export async function avanzarEstado(
  codigo: string,
  _previous: FormState,
  _formData: FormData,
): Promise<FormState> {
  const session = await getSession();
  if (!session) redirect("/login");
  if (!hasRole(session.user.role, "taller") && !canWrite(session.user.role)) {
    return error("No tiene permiso para esta acción.");
  }
  const result = await apiPost<OrdenDetalle>(
    `/ordenes/${encodeURIComponent(codigo)}/avanzar`,
    {},
  );
  if (!result.ok) {
    // The 409 text comes from the API (closed, already ready, leather not cut yet): it says what to do, so it is shown as is.
    return fromFailure(result);
  }
  refresh();
  const nuevo = siguienteEstadoDelTaller(result.data.estado);
  return ok(
    nuevo
      ? `Listo: el lote está «${lotStateLabel(result.data.estado)}».`
      : `Listo: el lote está «${lotStateLabel(result.data.estado)}». Falta que el administrador lo cierre.`,
  );
}
