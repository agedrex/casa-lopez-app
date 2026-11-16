"use server";

import { revalidatePath } from "next/cache";
import { error, type FormState, ok } from "@/lib/action-state";
import { apiPost } from "@/lib/api";
import { parseDecimalInput } from "@/lib/format";
import { denyUnlessAdmin, fromFailure, text } from "@/lib/write-guard";

/**
 * Saves MARGEN_TRANSFERENCIA_PCT. The person types a percent (20); the parameter stores a fraction
 * (0.2000). It is a rate, not money, so the conversion is safe here. SUPUESTO: validar con Robert.
 */
export async function guardarMargenTransferencia(
  _previous: FormState,
  formData: FormData,
): Promise<FormState> {
  const check = await denyUnlessAdmin();
  if (check.denied) return check.denied;
  const parsed = parseDecimalInput(text(formData, "margen"));
  const pct = parsed === null ? Number.NaN : Number(parsed);
  if (!Number.isFinite(pct) || pct < 0 || pct >= 100) {
    return error(
      "El margen tiene que estar entre 0 y 99,99 %, por ejemplo 20.",
    );
  }
  const result = await apiPost("/parametros/MARGEN_TRANSFERENCIA_PCT", {
    valor: (pct / 100).toFixed(4),
    fuente_estado: formData.get("confirmado") ? "Confirmado" : "Propuesta",
    nota: "Cargado desde la pantalla Negocio",
  });
  if (!result.ok) return fromFailure(result);
  revalidatePath("/admin/negocio");
  return ok("Margen guardado. Los dos escenarios ya lo usan.");
}
