"use server";

import { refresh } from "next/cache";
import { error, type FormState, ok } from "@/lib/action-state";
import { apiPost } from "@/lib/api";
import { EXPENSE_CATEGORIES, parseDecimalInput } from "@/lib/format";
import type { CostosFijos } from "@/lib/types";
import {
  denyUnlessWriter,
  fromFailure,
  optional,
  text,
} from "@/lib/write-guard";

const PERIODO = /^\d{4}-(0[1-9]|1[0-2])$/;

export async function createGasto(
  _previous: FormState,
  formData: FormData,
): Promise<FormState> {
  const denied = await denyUnlessWriter();
  if (denied) return denied;

  const periodo = text(formData, "periodo");
  const concepto = text(formData, "concepto");
  const lado = text(formData, "fabrica_o_tienda");
  const categoria = text(formData, "categoria");
  const rawMonto = text(formData, "monto");
  const monto = rawMonto ? parseDecimalInput(rawMonto) : null;
  if (!PERIODO.test(periodo)) return error("Indique el período como AAAA-MM.");
  if (!concepto) return error("Indique el concepto del gasto.");
  if (!["FABRICA", "TIENDA"].includes(lado)) {
    return error("Indique si es de la fábrica o de la tienda.");
  }
  if (!EXPENSE_CATEGORIES.includes(categoria)) {
    return error("Elija la categoría del gasto.");
  }
  if (rawMonto && monto === null) {
    return error(
      "El monto no es un número válido. Ejemplo: 250000 o 250000,50.",
    );
  }

  const result = await apiPost<CostosFijos>("/costos-fijos", {
    periodo,
    concepto,
    fabrica_o_tienda: lado,
    categoria,
    persona: optional(formData, "persona"),
    monto_ars_del_mes: monto,
    ficticio: formData.get("ficticio") === "on",
    nota_fuente: optional(formData, "nota_fuente"),
  });
  if (!result.ok) return fromFailure(result);
  refresh();
  return ok(
    monto === null
      ? "Gasto cargado sin monto: queda pendiente."
      : "Gasto cargado.",
  );
}

/** Fills the amount of a pending row. A row that already has one is corrected with a new row, never updated. */
export async function setMonto(
  codigo: string,
  _previous: FormState,
  formData: FormData,
): Promise<FormState> {
  const denied = await denyUnlessWriter();
  if (denied) return denied;

  const monto = parseDecimalInput(text(formData, "monto"));
  if (monto === null) {
    return error("Ingrese el monto en pesos, por ejemplo 250000 o 250000,50.");
  }
  const result = await apiPost<CostosFijos>(
    `/costos-fijos/${encodeURIComponent(codigo)}/monto`,
    { monto_ars_del_mes: monto },
  );
  if (!result.ok) {
    return fromFailure(result, {
      409: "Ese gasto ya tiene monto. Para corregirlo, cargue un gasto nuevo.",
    });
  }
  refresh();
  return ok("Monto cargado.");
}
