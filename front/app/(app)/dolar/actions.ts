"use server";

import { refresh } from "next/cache";
import { error, type FormState, ok } from "@/lib/action-state";
import { apiPost } from "@/lib/api";
import { parseDecimalInput } from "@/lib/format";
import type { Dolar } from "@/lib/types";
import {
  denyUnlessWriter,
  fromFailure,
  optional,
  text,
} from "@/lib/write-guard";

const TIPOS = ["VENDEDOR", "COMPRADOR"];

export async function createDolar(
  _previous: FormState,
  formData: FormData,
): Promise<FormState> {
  const denied = await denyUnlessWriter();
  if (denied) return denied;

  const fecha = text(formData, "fecha");
  const valor = parseDecimalInput(text(formData, "valor"));
  const tipo = text(formData, "tipo");
  if (!fecha) return error("Indique la fecha del dólar.");
  if (valor === null || !/[1-9]/.test(valor)) {
    return error("Ingrese el valor en pesos, por ejemplo 1545 o 1545,50.");
  }
  if (!TIPOS.includes(tipo)) return error("Elija el tipo de dólar.");

  const result = await apiPost<Dolar>("/dolar", {
    fecha,
    ars_por_usd: valor,
    tipo,
    fuente: "MANUAL",
    nota: optional(formData, "nota"),
  });
  if (!result.ok) {
    return fromFailure(result, {
      409: "Ya hay un dólar cargado para esa fecha y tipo.",
    });
  }
  refresh();
  return ok("Dólar cargado.");
}
