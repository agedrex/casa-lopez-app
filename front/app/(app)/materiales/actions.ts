"use server";

import { refresh } from "next/cache";
import { error, type FormState, ok } from "@/lib/action-state";
import { apiGet, apiPost } from "@/lib/api";
import { formatMoney, formatPercent, parseDecimalInput } from "@/lib/format";
import type {
  Material,
  MaterialesLote,
  Precio,
  PrecioChequeo,
} from "@/lib/types";
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

/** What the grid sends for a saved row: only the cells that changed, as typed. */
export type CambioMaterialLote = {
  codigo: string;
  valores: Record<string, string>;
};

const UNIDADES = ["m2", "cm", "juego", "unidad", "USD", "m"];

function positive(value: string | null): value is string {
  return value !== null && /[1-9]/.test(value);
}

/**
 * Saves the materials grid in one call (all or nothing): a changed price, currency or supplier
 * becomes a NEW dated price on the API side (nothing is overwritten) and a new row becomes a new
 * material, with its first price when it has one. The unit of the price is the consumption unit of
 * the material, so it is never sent. Prices and variations come back from the API.
 */
export async function guardarMaterialesLote(
  cambios: CambioMaterialLote[],
  nuevos: Record<string, string>[],
): Promise<FormState> {
  const denied = await denyUnlessWriter();
  if (denied) return denied;

  if (!Array.isArray(cambios) || !Array.isArray(nuevos)) {
    return error("No se pudieron leer los cambios. Recargue la página.");
  }
  if (cambios.length + nuevos.length === 0) {
    return error("No hay cambios para guardar.");
  }

  const cambiosBody: Record<string, string>[] = [];
  for (const cambio of cambios) {
    const codigo =
      typeof cambio?.codigo === "string" ? cambio.codigo.trim() : "";
    if (!codigo) {
      return error("Falta el código de un material. Recargue la página.");
    }
    const valores = cambio.valores ?? {};
    const body: Record<string, string> = { codigo };
    if ("precio" in valores) {
      const precio = parseDecimalInput(String(valores.precio ?? ""));
      if (!positive(precio)) {
        return error(
          `${codigo}: el precio no es un número válido, mayor que cero. Ejemplo: 24 o 5857,14.`,
        );
      }
      body.precio = precio;
    }
    if ("moneda" in valores) {
      const moneda = String(valores.moneda ?? "").trim();
      if (!MONEDAS.includes(moneda)) {
        return error(`${codigo}: elija la moneda del precio.`);
      }
      body.moneda = moneda;
    }
    // An empty supplier clears it; the API treats "" as "no value".
    if ("proveedor" in valores) {
      body.proveedor = String(valores.proveedor ?? "").trim();
    }
    cambiosBody.push(body);
  }

  const nuevosBody: Record<string, string | null>[] = [];
  for (const [index, fila] of nuevos.entries()) {
    const name = `Material nuevo ${index + 1}`;
    const nombre = String(fila?.nombre ?? "").trim();
    if (!nombre) return error(`${name}: indique el nombre del material.`);
    const etapa = String(fila?.etapa ?? "").trim();
    if (!etapa) return error(`${name}: elija la etapa.`);
    const unidad = String(fila?.unidad_de_consumo ?? "").trim();
    if (!UNIDADES.includes(unidad)) {
      return error(`${name}: elija la unidad de consumo.`);
    }
    const rawPrecio = String(fila?.precio ?? "").trim();
    const precio = rawPrecio ? parseDecimalInput(rawPrecio) : null;
    if (rawPrecio && !positive(precio)) {
      return error(
        `${name}: el precio no es un número válido, mayor que cero. Ejemplo: 24 o 5857,14.`,
      );
    }
    const moneda = String(fila?.moneda ?? "").trim();
    if (precio && !MONEDAS.includes(moneda)) {
      return error(`${name}: elija la moneda del precio.`);
    }
    nuevosBody.push({
      nombre,
      etapa,
      unidad_de_consumo: unidad,
      precio,
      moneda: precio ? moneda : null,
      proveedor: String(fila?.proveedor ?? "").trim() || null,
    });
  }

  const result = await apiPost<MaterialesLote>("/materiales/lote", {
    cambios: cambiosBody,
    nuevos: nuevosBody,
  });
  if (!result.ok) {
    return fromFailure(result, {
      409: "Ya hay un material con ese nombre, o un precio de hoy para ese material.",
    });
  }
  refresh();
  const partes = [
    result.data.precios.length > 0
      ? `${result.data.precios.length} ${result.data.precios.length === 1 ? "precio nuevo" : "precios nuevos"}`
      : null,
    nuevosBody.length > 0
      ? `${nuevosBody.length} ${nuevosBody.length === 1 ? "material nuevo" : "materiales nuevos"}`
      : null,
  ].filter(Boolean);
  const saltos = result.data.precios
    .filter((precio) => precio.salto_grande)
    .map(
      (precio) =>
        `${precio.material}: el precio nuevo varía ${formatPercent(precio.variacion_pct)} respecto del anterior. Si es un error de tipeo, un precio no se edita: cárguelo de nuevo con otra fecha.`,
    );
  return {
    ...ok(
      partes.length > 0
        ? `Listo: ${partes.join(", ")}.`
        : "Listo: no había nada distinto que guardar.",
    ),
    avisos: saltos,
  };
}
