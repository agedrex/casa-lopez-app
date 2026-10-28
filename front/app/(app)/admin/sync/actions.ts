"use server";

import { refresh } from "next/cache";
import { type FormState, ok } from "@/lib/action-state";
import { apiPost } from "@/lib/api";
import type { SyncResultado } from "@/lib/types";
import { denyUnlessAdmin, fromFailure } from "@/lib/write-guard";

// A real push can wait on Google's retries, so it gets more room than a normal API call.
const SYNC_TIMEOUT_MS = 90_000;

const count = new Intl.NumberFormat("es-AR");

async function run(simular: boolean): Promise<FormState> {
  const check = await denyUnlessAdmin();
  if (check.denied) return check.denied;

  const result = await apiPost<SyncResultado>(
    "/sync/sheets",
    { simular },
    SYNC_TIMEOUT_MS,
  );
  if (!result.ok) {
    return fromFailure(result, {
      0: "La API no respondió a tiempo. Puede que la sincronización haya seguido: mire la última ejecución en unos minutos.",
    });
  }
  refresh();
  const { pestanas, total_filas, duracion_ms } = result.data;
  const resumen = `${count.format(pestanas.length)} pestañas y ${count.format(total_filas)} filas`;
  return ok(
    simular
      ? `Simulación lista: ${resumen} preparadas. No se escribió nada en Google.`
      : `Sincronización lista: ${resumen} escritas en el Sheet (${count.format(Math.max(1, Math.round(duracion_ms / 1000)))} s).`,
  );
}

/** Builds every tab and counts the rows, without calling Google. */
export async function simularSync(
  _previous: FormState,
  _formData: FormData,
): Promise<FormState> {
  return run(true);
}

/** Replaces the values of the app's tabs in the Google Sheet. The Sheet is a display copy. */
export async function sincronizarSync(
  _previous: FormState,
  _formData: FormData,
): Promise<FormState> {
  return run(false);
}
