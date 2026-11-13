"use server";

import { refresh } from "next/cache";
import { redirect } from "next/navigation";
import { error, type FormState, ok } from "@/lib/action-state";
import { apiPost } from "@/lib/api";
import { parseDecimalInput } from "@/lib/format";
import { collapseSpaces } from "@/lib/productos";
import type { Ficha, Formulario, ProductoResumen } from "@/lib/types";
import {
  denyUnlessWriter,
  fromFailure,
  optional,
  text,
} from "@/lib/write-guard";

const QUIEN = ["EXTERNA", "INTERNA"];

export async function createProducto(
  _previous: FormState,
  formData: FormData,
): Promise<FormState> {
  const denied = await denyUnlessWriter();
  if (denied) return denied;

  const esKit = formData.get("es_kit") === "on";
  const modelo = optional(formData, "modelo");
  const quien = text(formData, "quien_lo_confecciona");
  if (!modelo && !esKit) {
    return error("Elija el modelo (solo un kit puede ir sin modelo).");
  }
  if (!text(formData, "cuero") && !esKit) return error("Elija el cuero.");
  if (!QUIEN.includes(quien)) return error("Indique quién lo confecciona.");

  const result = await apiPost<Ficha>("/productos", {
    modelo,
    cuero: optional(formData, "cuero"),
    color: optional(formData, "color"),
    quien_lo_confecciona: quien,
    fecha_de_alta: optional(formData, "fecha_de_alta"),
    nombre_propio: optional(formData, "nombre_propio"),
    es_kit: esKit,
    nota: optional(formData, "nota"),
  });
  if (!result.ok) return fromFailure(result);
  const producto = `/productos/${encodeURIComponent(result.data.codigo)}`;
  if (formData.get("enviar_formulario") !== "on" || esKit) redirect(producto);

  // The product already exists: if the form cannot be created or sent, the person lands on the
  // product and can send it by hand from Formularios (never a second product by retrying).
  const formulario = await apiPost<Formulario>("/formularios", {
    articulo: collapseSpaces(result.data.nombre),
    producto: result.data.codigo,
  });
  if (!formulario.ok) redirect(producto);
  // If sending fails the form stays in BORRADOR and the admin sees it (and the button) on its page.
  await apiPost<Formulario>(
    `/formularios/${encodeURIComponent(formulario.data.codigo)}/enviar`,
    {},
  );
  redirect(`/formularios/${encodeURIComponent(formulario.data.codigo)}`);
}

/** What the products grid sends for a saved row: the margin as typed. */
export type CambioMargenLote = { codigo: string; margen: string };

/** 0 to 99 with at most one decimal, as the API takes it (`30`, `32,5`); `30,50` is written as `30.5`. */
function margenPct(raw: string): string | null {
  const match = /^(\d{1,2})(?:\.(\d)0*)?$/.exec(parseDecimalInput(raw) ?? "");
  return match ? (match[2] ? `${match[1]}.${match[2]}` : match[1]) : null;
}

/**
 * Saves the margins of the products grid in one call (all or nothing). The price is computed by
 * the API from today's cost and saved as a new dated price: nothing is overwritten here.
 */
export async function guardarMargenesLote(
  cambios: CambioMargenLote[],
): Promise<FormState> {
  const denied = await denyUnlessWriter();
  if (denied) return denied;

  if (!Array.isArray(cambios) || cambios.length === 0) {
    return error("No hay cambios para guardar.");
  }
  const items: { codigo: string; margen_pct: string }[] = [];
  for (const cambio of cambios) {
    const codigo =
      typeof cambio?.codigo === "string" ? cambio.codigo.trim() : "";
    if (!codigo) {
      return error("Falta el código de un producto. Recargue la página.");
    }
    const margen = margenPct(String(cambio.margen ?? ""));
    if (margen === null) {
      return error(
        `${codigo}: el margen tiene que ser un porcentaje de 0 a 99,9, con un decimal como máximo. Ejemplo: 30 o 32,5.`,
      );
    }
    items.push({ codigo, margen_pct: margen });
  }

  const result = await apiPost<ProductoResumen[]>("/productos/precios-lote", {
    items,
  });
  if (!result.ok) return fromFailure(result);
  refresh();
  return ok(
    `Listo: ${items.length} ${items.length === 1 ? "precio de venta guardado" : "precios de venta guardados"}.`,
  );
}
