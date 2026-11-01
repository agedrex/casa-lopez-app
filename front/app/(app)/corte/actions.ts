"use server";

import { redirect } from "next/navigation";
import { error, type FormState } from "@/lib/action-state";
import { apiPost } from "@/lib/api";
import { parseDecimalInput, todayIso } from "@/lib/format";
import { getSession } from "@/lib/session";
import type { PiezaCueroDetalle } from "@/lib/types";
import { fromFailure, text } from "@/lib/write-guard";
import { guardarCarga } from "./cargas";

const DECISIONES = ["REUTILIZABLE", "IRRECUPERABLE"];
const MAX_TEXTO = 120;

// Cuts and leftovers are open to admin, cotizador and corte (the backend decides): here only
// a missing session is refused, so the "corte" role is not blocked by denyUnlessWriter.
async function requireLogin(): Promise<void> {
  if (!(await getSession())) redirect("/login");
}

const corteHref = (params: Record<string, string>) =>
  `/corte?${new URLSearchParams(params)}`;

export async function confirmarCorte(
  _previous: FormState,
  formData: FormData,
): Promise<FormState> {
  await requireLogin();

  const pieza = text(formData, "pieza");
  const item = text(formData, "item");
  const lote = text(formData, "lote");
  const producto = text(formData, "producto").slice(0, MAX_TEXTO);
  const m2 = parseDecimalInput(text(formData, "m2"));
  if (!pieza || !item || !lote) {
    return error(
      "Falta elegir el lote, el producto o la piel. Empezá de nuevo.",
    );
  }
  if (m2 === null || !/[1-9]/.test(m2)) {
    return error("Ingresá los m² cortados, por ejemplo 0,25.");
  }

  const result = await apiPost<PiezaCueroDetalle>(
    `/cueros/${encodeURIComponent(pieza)}/cortes`,
    { m2, orden_item: item },
  );
  if (!result.ok) {
    return fromFailure(result, {
      403: "No tenés permiso para registrar cortes.",
    });
  }
  await guardarCarga({ fecha: todayIso(), pieza, m2, producto, lote });
  redirect(corteHref({ lote, item, sobrante: pieza }));
}

export async function decidirSobrante(
  _previous: FormState,
  formData: FormData,
): Promise<FormState> {
  await requireLogin();

  const pieza = text(formData, "pieza");
  const lote = text(formData, "lote");
  const decision = text(formData, "decision");
  if (!pieza) return error("Falta la piel. Empezá de nuevo.");
  if (!DECISIONES.includes(decision)) {
    return error("Elegí qué hacer con lo que sobró.");
  }

  const result = await apiPost<PiezaCueroDetalle>(
    `/cueros/${encodeURIComponent(pieza)}/sobrante`,
    { decision },
  );
  if (!result.ok) {
    return fromFailure(result, {
      403: "No tenés permiso para decidir sobre el sobrante.",
    });
  }
  redirect(corteHref(lote ? { lote, listo: pieza } : { listo: pieza }));
}
