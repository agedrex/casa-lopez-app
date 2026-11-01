"use server";

import { refresh } from "next/cache";
import { error, type FormState, ok } from "@/lib/action-state";
import { apiPost } from "@/lib/api";
import { parseDecimalInput } from "@/lib/format";
import type { PiezaCueroDetalle } from "@/lib/types";
import {
  denyUnlessWriter,
  fromFailure,
  optional,
  text,
} from "@/lib/write-guard";

const ORIGENES = ["COMPRA", "SOBRANTE_EXISTENTE"];
const MONEDAS = ["ARS", "USD"];

export async function createCuero(
  _previous: FormState,
  formData: FormData,
): Promise<FormState> {
  const denied = await denyUnlessWriter();
  if (denied) return denied;

  const origen = text(formData, "origen");
  const material = text(formData, "material");
  const m2 = parseDecimalInput(text(formData, "m2"));
  if (!ORIGENES.includes(origen)) {
    return error("Elegí si es cuero comprado o un sobrante que ya tenían.");
  }
  if (!material) return error("Elegí el cuero.");
  if (m2 === null || !/[1-9]/.test(m2)) {
    return error("Ingresá los m², por ejemplo 12 o 12,5.");
  }

  const comprado = origen === "COMPRA";
  const fecha = text(formData, "fecha");
  if (comprado && !fecha) return error("Indicá la fecha de compra.");

  // Price and currency travel together or not at all (the API refuses one without the other).
  const precioTexto = comprado ? text(formData, "precio") : "";
  const moneda = comprado ? text(formData, "moneda") : "";
  let precio: string | null = null;
  if (precioTexto || moneda) {
    precio = parseDecimalInput(precioTexto);
    if (precio === null)
      return error("Ingresá el precio por m², por ejemplo 24.");
    if (!MONEDAS.includes(moneda)) return error("Elegí la moneda del precio.");
  }

  const result = await apiPost<PiezaCueroDetalle>("/cueros", {
    origen,
    material,
    color: optional(formData, "color"),
    m2_iniciales: m2,
    fecha_de_compra: comprado ? fecha : null,
    precio_pagado_por_m2: precio,
    moneda: precio === null ? null : moneda,
    proveedor: comprado ? optional(formData, "proveedor") : null,
  });
  if (!result.ok) {
    return fromFailure(result, {
      403: "No tenés permiso para cargar cueros.",
    });
  }
  refresh();
  return ok(`Cuero cargado: ${result.data.codigo}.`);
}
