"use server";

import { refresh } from "next/cache";
import { error, type FormState, ok } from "@/lib/action-state";
import { apiPost } from "@/lib/api";
import { parseDecimalInput } from "@/lib/format";
import { PARAMETER_STATES } from "@/lib/parametros";
import type { Parametro } from "@/lib/types";
import {
  denyUnlessAdmin,
  fromFailure,
  optional,
  text,
} from "@/lib/write-guard";

/**
 * Text parameters (the current period) arrive as `valor_texto`, numeric ones as `valor`.
 * The API checks the range for the parameter's unit; the screen only normalizes the text.
 */
export async function updateParametro(
  codigo: string,
  _previous: FormState,
  formData: FormData,
): Promise<FormState> {
  const check = await denyUnlessAdmin();
  if (check.denied) return check.denied;

  const estado = text(formData, "fuente_estado");
  if (!(PARAMETER_STATES as readonly string[]).includes(estado)) {
    return error("Elija el estado del parámetro.");
  }
  const body: Record<string, unknown> = {
    fuente_estado: estado,
    nota: optional(formData, "nota"),
  };
  if (formData.has("valor_texto")) {
    body.valor_texto = text(formData, "valor_texto");
  } else {
    const valor = parseDecimalInput(text(formData, "valor"));
    if (valor === null) {
      return error("El valor no es un número válido. Ejemplo: 0,05 o 1700.");
    }
    body.valor = valor;
  }

  const result = await apiPost<Parametro>(
    `/parametros/${encodeURIComponent(codigo)}`,
    body,
  );
  if (!result.ok) return fromFailure(result);
  refresh();
  return ok(
    "Parámetro actualizado. La próxima cotización ya usa el valor nuevo.",
  );
}
