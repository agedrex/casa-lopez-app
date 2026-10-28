"use server";

import { refresh } from "next/cache";
import { redirect } from "next/navigation";
import { error, type FormState, ok } from "@/lib/action-state";
import { apiPost } from "@/lib/api";
import { parseDecimalInput } from "@/lib/format";
import { CONSUMPTION_FIELDS, ORIGINS, SIZES } from "@/lib/modelos";
import type { ModeloDetalle } from "@/lib/types";
import {
  denyUnlessAdmin,
  fromFailure,
  optional,
  text,
} from "@/lib/write-guard";

type Consumptions = Record<string, string | null>;

/**
 * Reads the consumption fields of the form. An empty field is "missing data" (null), a 0 is
 * "no lleva". Amounts stay text: the API checks sign and precision.
 */
function readConsumptions(formData: FormData): Consumptions | FormState {
  const body: Consumptions = {};
  for (const field of CONSUMPTION_FIELDS) {
    const raw = text(formData, field.name);
    if (!raw) {
      if (field.required)
        return error(
          `Indique el consumo de ${field.label.toLowerCase()} (0 si no lleva).`,
        );
      body[field.name] = null;
      continue;
    }
    const value = parseDecimalInput(raw);
    if (value === null) {
      return error(`${field.label}: no es un número válido. Ejemplo: 0,25.`);
    }
    body[field.name] = value;
  }
  const origen = text(formData, "origen_de_los_consumos");
  if (!ORIGINS.some((item) => item.value === origen)) {
    return error("Elija el origen de los consumos.");
  }
  body.origen_de_los_consumos = origen;
  body.forro = optional(formData, "forro");
  return body;
}

function isFailure(value: Consumptions | FormState): value is FormState {
  return "status" in value;
}

export async function createModelo(
  _previous: FormState,
  formData: FormData,
): Promise<FormState> {
  const check = await denyUnlessAdmin();
  if (check.denied) return check.denied;

  const nombre = text(formData, "nombre_del_modelo");
  const categoria = text(formData, "categoria");
  const tamano = text(formData, "tamano");
  if (!nombre) return error("Indique el nombre del modelo.");
  if (!categoria) return error("Elija la categoría.");
  if (tamano && !SIZES.some((item) => item.value === tamano)) {
    return error("El tamaño no es válido.");
  }
  const consumptions = readConsumptions(formData);
  if (isFailure(consumptions)) return consumptions;

  const result = await apiPost<ModeloDetalle>("/modelos", {
    nombre_del_modelo: nombre,
    categoria,
    tamano: tamano || null,
    nota: optional(formData, "nota"),
    ...consumptions,
  });
  if (!result.ok) {
    return fromFailure(result, {
      409: "Ya hay un modelo con ese nombre: agregue algo que lo distinga.",
    });
  }
  redirect(`/admin/modelos/${encodeURIComponent(result.data.codigo)}`);
}

export async function setValidado(
  codigo: string,
  validado: boolean,
  _previous: FormState,
  _formData: FormData,
): Promise<FormState> {
  const check = await denyUnlessAdmin();
  if (check.denied) return check.denied;

  const result = await apiPost<ModeloDetalle>(
    `/modelos/${encodeURIComponent(codigo)}/validado`,
    { validado },
  );
  if (!result.ok) return fromFailure(result);
  refresh();
  return ok(
    validado
      ? "Modelo marcado como validado."
      : "Se quitó la validación del modelo.",
  );
}

/** The only way to change the consumptions of an existing model: admin only, and it resets `validado`. */
export async function updateConsumos(
  codigo: string,
  _previous: FormState,
  formData: FormData,
): Promise<FormState> {
  const check = await denyUnlessAdmin();
  if (check.denied) return check.denied;

  const consumptions = readConsumptions(formData);
  if (isFailure(consumptions)) return consumptions;
  const result = await apiPost<ModeloDetalle>(
    `/modelos/${encodeURIComponent(codigo)}/consumos`,
    consumptions,
  );
  if (!result.ok) return fromFailure(result);
  refresh();
  return ok("Consumos guardados. El modelo quedó sin validar.");
}
