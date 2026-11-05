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
      409: "Ese gasto ya tiene monto. Para cambiarlo, use «Corregir monto» en su fila.",
    });
  }
  refresh();
  return ok("Monto cargado.");
}

/** Corrects the amount of a row: the API adds a new row that replaces it, the old one stays in the history. */
export async function corregirGasto(
  codigo: string,
  _previous: FormState,
  formData: FormData,
): Promise<FormState> {
  const denied = await denyUnlessWriter();
  if (denied) return denied;

  const monto = parseDecimalInput(text(formData, "monto"));
  if (monto === null) {
    return error(
      "Ingrese el monto nuevo en pesos, por ejemplo 250000 o 250000,50.",
    );
  }
  const result = await apiPost<CostosFijos>(
    `/costos-fijos/${encodeURIComponent(codigo)}/corregir`,
    {
      monto_ars_del_mes: monto,
      nota: optional(formData, "nota"),
      ficticio: formData.get("ficticio") === "on",
    },
  );
  if (!result.ok) {
    if (result.status === 409) {
      return error(
        "Ese gasto ya fue corregido. Recargue la página para ver el monto vigente.",
        [result.message],
      );
    }
    return fromFailure(result, {
      404: "No encontramos ese gasto. Recargue la página e intente de nuevo.",
      422: "Revise el monto: tiene que ser un número de cero o más.",
    });
  }
  refresh();
  return ok("Monto corregido. El anterior quedó en el historial.");
}

/** Creates the month's rows from the previous month's current rows (with their amounts or pending). */
export async function copiarMes(
  _previous: FormState,
  formData: FormData,
): Promise<FormState> {
  const denied = await denyUnlessWriter();
  if (denied) return denied;

  const desde = text(formData, "desde");
  const hasta = text(formData, "hasta");
  const modo = text(formData, "modo");
  if (!PERIODO.test(desde) || !PERIODO.test(hasta)) {
    return error("No se pudo leer el mes. Recargue la página.");
  }
  if (modo !== "con_montos" && modo !== "pendientes") {
    return error("Elija si quiere copiar los montos o dejarlos pendientes.");
  }
  const result = await apiPost<CostosFijos>("/costos-fijos/copiar", {
    desde,
    hasta,
    con_montos: modo === "con_montos",
  });
  if (!result.ok) {
    if (result.status === 422) {
      return error("El mes anterior no tiene gastos para copiar.", [
        result.message,
      ]);
    }
    return fromFailure(result, {
      409: "Este mes ya tiene gastos cargados. No se copia encima de lo que hay.",
    });
  }
  refresh();
  return ok("Listo: se copiaron los gastos del mes anterior.");
}
