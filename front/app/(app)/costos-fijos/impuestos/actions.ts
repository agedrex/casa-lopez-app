"use server";

import { refresh } from "next/cache";
import { error, type FormState, ok } from "@/lib/action-state";
import { apiPost } from "@/lib/api";
import type { Impuesto } from "@/lib/types";
import { denyUnlessAdmin, fromFailure, text } from "@/lib/write-guard";
import { percentToFraction } from "./percent";

const PERCENT_HELP =
  "Escriba el porcentaje entre 0 y 100, con hasta un decimal: por ejemplo 21 o 3,5.";

export async function createImpuesto(
  _previous: FormState,
  formData: FormData,
): Promise<FormState> {
  const check = await denyUnlessAdmin();
  if (check.denied) return check.denied;

  const nombre = text(formData, "nombre");
  const alicuota = percentToFraction(text(formData, "porcentaje"));
  if (!nombre) return error("Indique el nombre del impuesto.");
  if (alicuota === null) return error(PERCENT_HELP);

  const result = await apiPost<Impuesto>("/impuestos", { nombre, alicuota });
  if (!result.ok) {
    return fromFailure(result, { 409: "Ya hay un impuesto con ese nombre." });
  }
  refresh();
  return ok(`Impuesto cargado con el código ${result.data.codigo}.`);
}

/** The percentage is edited in place; prices are never stored with taxes, so the next read uses it. */
export async function setImpuestoAlicuota(
  codigo: string,
  _previous: FormState,
  formData: FormData,
): Promise<FormState> {
  const check = await denyUnlessAdmin();
  if (check.denied) return check.denied;

  const alicuota = percentToFraction(text(formData, "porcentaje"));
  if (alicuota === null) return error(PERCENT_HELP);

  const result = await apiPost<Impuesto>(
    `/impuestos/${encodeURIComponent(codigo)}/alicuota`,
    { alicuota },
  );
  if (!result.ok) return fromFailure(result);
  refresh();
  return ok("Porcentaje guardado.");
}

/** Deactivating deletes nothing: the tax only stops showing in the price breakdown. */
export async function setImpuestoActivo(
  codigo: string,
  activo: boolean,
  _previous: FormState,
  _formData: FormData,
): Promise<FormState> {
  const check = await denyUnlessAdmin();
  if (check.denied) return check.denied;

  const result = await apiPost<Impuesto>(
    `/impuestos/${encodeURIComponent(codigo)}/activo`,
    { activo },
  );
  if (!result.ok) return fromFailure(result);
  refresh();
  return ok(activo ? "Impuesto activado." : "Impuesto desactivado.");
}
