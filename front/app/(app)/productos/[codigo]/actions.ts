"use server";

import { refresh } from "next/cache";
import { error, type FormState, ok } from "@/lib/action-state";
import { apiPost } from "@/lib/api";
import {
  formatArs,
  formatUsd,
  parseDecimalInput,
  quoteTypeLabel,
} from "@/lib/format";
import type { Cotizacion, Ficha } from "@/lib/types";
import {
  denyUnlessWriter,
  fromFailure,
  optional,
  text,
} from "@/lib/write-guard";

const TIPOS = ["INICIAL", "RECOTIZACION", "FINAL"];

function positive(value: string | null): value is string {
  return value !== null && /[1-9]/.test(value);
}

export async function addExtra(
  codigo: string,
  _previous: FormState,
  formData: FormData,
): Promise<FormState> {
  const denied = await denyUnlessWriter();
  if (denied) return denied;

  const material = text(formData, "material");
  const consumo = parseDecimalInput(text(formData, "consumo"));
  if (!material) return error("Elija el material.");
  if (!positive(consumo)) {
    return error("Ingrese el consumo, mayor que cero (por ejemplo 0,25).");
  }

  const result = await apiPost<Ficha>(
    `/productos/${encodeURIComponent(codigo)}/extras`,
    {
      material,
      color: optional(formData, "color"),
      consumo_neto_por_unidad: consumo,
      nota: optional(formData, "nota"),
    },
  );
  if (!result.ok) return fromFailure(result);
  refresh();
  return ok("Extra agregado a la receta.");
}

export async function addComponente(
  codigo: string,
  _previous: FormState,
  formData: FormData,
): Promise<FormState> {
  const denied = await denyUnlessWriter();
  if (denied) return denied;

  const componente = text(formData, "componente");
  const cantidad = parseDecimalInput(text(formData, "cantidad"));
  if (!componente) return error("Indique el código del producto componente.");
  if (!positive(cantidad)) return error("Ingrese una cantidad mayor que cero.");

  const result = await apiPost<Ficha>(
    `/productos/${encodeURIComponent(codigo)}/componentes`,
    { componente, cantidad },
  );
  if (!result.ok) return fromFailure(result);
  refresh();
  return ok("Componente agregado al kit.");
}

export async function saveCotizacion(
  codigo: string,
  _previous: FormState,
  formData: FormData,
): Promise<FormState> {
  const denied = await denyUnlessWriter();
  if (denied) return denied;

  const tipo = text(formData, "tipo");
  if (!TIPOS.includes(tipo)) return error("Elija el tipo de cotización.");

  const result = await apiPost<Cotizacion>(
    `/productos/${encodeURIComponent(codigo)}/cotizaciones`,
    { tipo, fecha: optional(formData, "fecha") },
  );
  if (!result.ok) {
    if (result.status === 422 && result.avisos.length > 0) {
      return error("Faltan datos para guardar la cotización:", result.avisos);
    }
    return fromFailure(result);
  }
  refresh();
  return ok(
    `Cotización ${quoteTypeLabel(tipo).toLowerCase()} guardada: ${formatArs(
      result.data.total_ars,
    )} (${formatUsd(result.data.total_usd)}).`,
  );
}
