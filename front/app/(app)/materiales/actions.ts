"use server";

import { refresh } from "next/cache";
import { error, type FormState, ok } from "@/lib/action-state";
import { apiGet, apiPost } from "@/lib/api";
import { formatMoney, formatPercent, parseDecimalInput } from "@/lib/format";
import type { Material, Precio, PrecioChequeo } from "@/lib/types";
import {
  denyUnlessWriter,
  fromFailure,
  optional,
  text,
} from "@/lib/write-guard";

const MONEDAS = ["ARS", "USD"];

export async function createPrecio(
  _previous: FormState,
  formData: FormData,
): Promise<FormState> {
  const denied = await denyUnlessWriter();
  if (denied) return denied;

  const material = text(formData, "material");
  const precio = parseDecimalInput(text(formData, "precio"));
  const moneda = text(formData, "moneda");
  const unidad = text(formData, "unidad_del_precio");
  const vigenteDesde = text(formData, "vigente_desde");
  const color = optional(formData, "color");
  if (!material) return error("Elija el material.");
  if (precio === null) {
    return error("Ingrese el precio, por ejemplo 24 o 5857,14.");
  }
  if (!MONEDAS.includes(moneda)) return error("Elija la moneda.");
  if (!vigenteDesde) return error("Indique desde qué fecha rige el precio.");

  // The form never offers a blocked material; refuse it here too (anyone can post to an action).
  const materials = await apiGet<Material[]>("/materiales");
  if (!materials.ok) return fromFailure(materials);
  const chosen = materials.data.find((m) => m.codigo === material);
  if (!chosen) return error("No existe ese material.");
  if (!chosen.cotizable) {
    return error("Bloqueado: falta definir la unidad de este material.");
  }

  // The API does the comparison (the frontend never calculates money). A big jump is a
  // warning, not a block: the person confirms with "Cargar igual".
  if (text(formData, "confirmar") !== "1") {
    const query = new URLSearchParams({
      material,
      precio,
      moneda,
      vigente_desde: vigenteDesde,
    });
    if (color) query.set("color", color);
    const check = await apiGet<PrecioChequeo>(`/precios/chequeo?${query}`);
    if (!check.ok) return fromFailure(check);
    if (check.data.salto_grande) {
      return {
        status: "warning",
        needsConfirm: true,
        message: `El precio nuevo (${formatMoney(precio, moneda)}) varía ${formatPercent(
          check.data.variacion_pct,
        )} respecto del anterior (${formatMoney(check.data.anterior, moneda)}). ¿Es correcto?`,
        avisos: [
          "Si es un error de tipeo, corríjalo antes de cargar: los precios no se editan ni se borran.",
        ],
      };
    }
  }

  const result = await apiPost<Precio>("/precios", {
    material,
    color,
    precio,
    moneda,
    unidad_del_precio: unidad,
    vigente_desde: vigenteDesde,
    proveedor: optional(formData, "proveedor"),
    nota_fuente: optional(formData, "nota_fuente"),
  });
  if (!result.ok) {
    return fromFailure(result, {
      409: "Ya hay un precio de ese material y color para esa fecha. Cargue uno con otra fecha.",
    });
  }
  refresh();
  return ok("Precio cargado.");
}
