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

/** What the grid sends for a saved row: only the cells that changed, as typed. */
export type CambioGastoLote = {
  codigo: string;
  valores: Record<string, string>;
};

const LADOS = ["FABRICA", "TIENDA"];

/**
 * Saves the month's grid in one call (all or nothing): changes to saved rows and new rows. A
 * changed amount is a correction on the API side (a new row that replaces the old one, which
 * stays in the history); nothing is overwritten. Totals come back from the API, never from here.
 */
export async function guardarGastosLote(
  periodo: string,
  cambios: CambioGastoLote[],
  nuevos: Record<string, string>[],
  anulados: string[] = [],
): Promise<FormState> {
  const denied = await denyUnlessWriter();
  if (denied) return denied;

  if (!PERIODO.test(periodo))
    return error("No se pudo leer el mes. Recargue la página.");
  if (!Array.isArray(cambios) || !Array.isArray(nuevos)) {
    return error("No se pudieron leer los cambios. Recargue la página.");
  }
  if (
    !Array.isArray(anulados) ||
    anulados.some((codigo) => typeof codigo !== "string" || !codigo.trim())
  ) {
    return error("No se pudieron leer los cambios. Recargue la página.");
  }
  if (cambios.length + nuevos.length + anulados.length === 0) {
    return error("No hay cambios para guardar.");
  }

  const montoError =
    "el monto no es un número válido. Ejemplo: 250000 o 250000,50.";
  const cambiosBody: Record<string, string>[] = [];
  for (const cambio of cambios) {
    const codigo =
      typeof cambio?.codigo === "string" ? cambio.codigo.trim() : "";
    if (!codigo)
      return error("Falta el código de un gasto. Recargue la página.");
    const valores = cambio.valores ?? {};
    const body: Record<string, string> = { codigo };
    if ("concepto" in valores) {
      const concepto = String(valores.concepto ?? "").trim();
      if (!concepto)
        return error(`${codigo}: el concepto no puede quedar vacío.`);
      body.concepto = concepto;
    }
    if ("fabrica_o_tienda" in valores) {
      const lado = String(valores.fabrica_o_tienda ?? "").trim();
      if (!LADOS.includes(lado)) {
        return error(`${codigo}: indique si es de la fábrica o de la tienda.`);
      }
      body.fabrica_o_tienda = lado;
    }
    if ("categoria" in valores) {
      const categoria = String(valores.categoria ?? "").trim();
      if (!EXPENSE_CATEGORIES.includes(categoria)) {
        return error(`${codigo}: elija la categoría del gasto.`);
      }
      body.categoria = categoria;
    }
    if ("monto" in valores) {
      const monto = parseDecimalInput(String(valores.monto ?? ""));
      if (monto === null) return error(`${codigo}: ${montoError}`);
      body.monto = monto;
    }
    // An empty person or note clears it; the API treats "" as "no value".
    if ("persona" in valores)
      body.persona = String(valores.persona ?? "").trim();
    if ("nota_fuente" in valores) {
      body.nota_fuente = String(valores.nota_fuente ?? "").trim();
    }
    cambiosBody.push(body);
  }

  const nuevosBody: Record<string, string | null>[] = [];
  for (const [index, fila] of nuevos.entries()) {
    const name = `Fila nueva ${index + 1}`;
    const concepto = String(fila?.concepto ?? "").trim();
    const lado = String(fila?.fabrica_o_tienda ?? "").trim();
    const categoria = String(fila?.categoria ?? "").trim();
    const rawMonto = String(fila?.monto ?? "").trim();
    const monto = rawMonto ? parseDecimalInput(rawMonto) : null;
    if (!concepto) return error(`${name}: indique el concepto del gasto.`);
    if (!LADOS.includes(lado)) {
      return error(`${name}: indique si es de la fábrica o de la tienda.`);
    }
    if (!EXPENSE_CATEGORIES.includes(categoria)) {
      return error(`${name}: elija la categoría del gasto.`);
    }
    if (rawMonto && monto === null) return error(`${name}: ${montoError}`);
    nuevosBody.push({
      concepto,
      fabrica_o_tienda: lado,
      categoria,
      persona: String(fila?.persona ?? "").trim() || null,
      monto_ars_del_mes: monto,
      nota_fuente: String(fila?.nota_fuente ?? "").trim() || null,
    });
  }

  const result = await apiPost<CostosFijos>("/costos-fijos/lote", {
    periodo,
    cambios: cambiosBody,
    nuevos: nuevosBody,
    anulados,
  });
  if (!result.ok) {
    return fromFailure(result, {
      404: "No encontramos alguno de los gastos. Recargue la página e intente de nuevo.",
      409: "Alguno de los gastos ya fue corregido o borrado. Recargue la página para ver lo vigente.",
    });
  }
  refresh();
  const partes = [
    cambiosBody.length > 0
      ? `${cambiosBody.length} ${cambiosBody.length === 1 ? "gasto cambiado" : "gastos cambiados"}`
      : null,
    nuevosBody.length > 0
      ? `${nuevosBody.length} ${nuevosBody.length === 1 ? "gasto nuevo" : "gastos nuevos"}`
      : null,
    anulados.length > 0
      ? `${anulados.length} ${anulados.length === 1 ? "gasto borrado" : "gastos borrados"}`
      : null,
  ].filter(Boolean);
  return ok(`Listo: ${partes.join(", ")}.`);
}
