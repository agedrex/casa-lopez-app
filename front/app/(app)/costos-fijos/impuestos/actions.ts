"use server";

import { refresh } from "next/cache";
import { percentToFraction } from "@/app/(app)/admin/impuestos/percent";
import { error, type FormState, IDLE, ok } from "@/lib/action-state";
import { apiPost } from "@/lib/api";
import type { Impuesto } from "@/lib/types";
import { denyUnlessAdmin, fromFailure, text } from "@/lib/write-guard";

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

/** What the grid sends for a saved row: the new percentage, as typed. */
export type CambioImpuestoLote = { codigo: string; porcentaje: string };

function formWith(values: Record<string, string>): FormData {
  const formData = new FormData();
  for (const [key, value] of Object.entries(values)) formData.set(key, value);
  return formData;
}

/**
 * Saves the taxes grid in one go: new percentages for saved taxes and new taxes. Everything is
 * checked first, so a typo saves nothing; then each row goes through the single-row actions.
 * The API has no batch endpoint, so a failure in the middle leaves the rows before it saved.
 */
export async function guardarImpuestosLote(
  cambios: CambioImpuestoLote[],
  nuevos: Record<string, string>[],
): Promise<FormState> {
  const check = await denyUnlessAdmin();
  if (check.denied) return check.denied;

  if (!Array.isArray(cambios) || !Array.isArray(nuevos)) {
    return error("No se pudieron leer los cambios. Recargue la página.");
  }
  if (cambios.length + nuevos.length === 0) {
    return error("No hay cambios para guardar.");
  }

  for (const cambio of cambios) {
    const codigo =
      typeof cambio?.codigo === "string" ? cambio.codigo.trim() : "";
    if (!codigo) {
      return error("Falta el código de un impuesto. Recargue la página.");
    }
    if (percentToFraction(String(cambio.porcentaje ?? "")) === null) {
      return error(`${codigo}: ${PERCENT_HELP}`);
    }
  }
  for (const [index, fila] of nuevos.entries()) {
    const name = `Impuesto nuevo ${index + 1}`;
    if (!String(fila?.nombre ?? "").trim()) {
      return error(`${name}: indique el nombre del impuesto.`);
    }
    if (percentToFraction(String(fila?.porcentaje ?? "")) === null) {
      return error(`${name}: ${PERCENT_HELP}`);
    }
  }

  for (const cambio of cambios) {
    const result = await setImpuestoAlicuota(
      cambio.codigo.trim(),
      IDLE,
      formWith({ porcentaje: cambio.porcentaje }),
    );
    if (result.status === "error") {
      return error(`${cambio.codigo}: ${result.message}`, result.avisos);
    }
  }
  for (const [index, fila] of nuevos.entries()) {
    const result = await createImpuesto(
      IDLE,
      formWith({ nombre: fila.nombre, porcentaje: fila.porcentaje }),
    );
    if (result.status === "error") {
      return error(
        `Impuesto nuevo ${index + 1}: ${result.message}`,
        result.avisos,
      );
    }
  }

  const partes = [
    cambios.length > 0
      ? `${cambios.length} ${cambios.length === 1 ? "impuesto cambiado" : "impuestos cambiados"}`
      : null,
    nuevos.length > 0
      ? `${nuevos.length} ${nuevos.length === 1 ? "impuesto nuevo" : "impuestos nuevos"}`
      : null,
  ].filter(Boolean);
  return ok(`Listo: ${partes.join(", ")}.`);
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
