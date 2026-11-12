"use server";

import { refresh } from "next/cache";
import { redirect } from "next/navigation";
import { error, type FormState, ok } from "@/lib/action-state";
import { apiPost } from "@/lib/api";
import { formatArs, parseDecimalInput } from "@/lib/format";
import type { ProductoReventa, ProductoReventaDetalle } from "@/lib/types";
import {
  denyUnlessWriter,
  fromFailure,
  optional,
  text,
} from "@/lib/write-guard";

function positive(value: string | null): value is string {
  return value !== null && /[1-9]/.test(value);
}

export async function createReventa(
  _previous: FormState,
  formData: FormData,
): Promise<FormState> {
  const denied = await denyUnlessWriter();
  if (denied) return denied;

  const nombre = text(formData, "nombre");
  if (!nombre) return error("Indique el nombre del producto.");

  const result = await apiPost<ProductoReventaDetalle>("/reventa", {
    nombre,
    categoria: optional(formData, "categoria"),
    proveedor: optional(formData, "proveedor"),
    nota: optional(formData, "nota"),
  });
  if (!result.ok) {
    return fromFailure(result, {
      409: "Ya hay un producto de mercadería con ese nombre.",
    });
  }
  redirect(`/reventa/${encodeURIComponent(result.data.codigo)}`);
}

/** What the grid sends for a saved row: only the cells that changed, as typed. */
export type CambioReventaLote = {
  codigo: string;
  valores: Record<string, string>;
};

function invalidAmount(name: string, what: string): FormState {
  return error(
    `${name}: ${what} no es un número válido, mayor que cero. Ejemplo: 12500 o 12500,50.`,
  );
}

/**
 * Saves the merchandise grid in one call (all or nothing): edits to saved rows and new products.
 * A changed cost or sale price is a price update on the API side (a new history row without
 * units); nothing is overwritten. Margins come back from the API, never from here.
 */
export async function guardarReventaLote(
  cambios: CambioReventaLote[],
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
      return error("Falta el código de un producto. Recargue la página.");
    }
    const valores = cambio.valores ?? {};
    const body: Record<string, string> = { codigo };
    if ("nombre" in valores) {
      const nombre = String(valores.nombre ?? "").trim();
      if (!nombre) return error(`${codigo}: el nombre no puede quedar vacío.`);
      body.nombre = nombre;
    }
    // An empty category, supplier or note clears it; the API treats "" as "no value".
    if ("categoria" in valores) {
      body.categoria = String(valores.categoria ?? "").trim();
    }
    if ("proveedor" in valores) {
      body.proveedor = String(valores.proveedor ?? "").trim();
    }
    if ("nota" in valores) body.nota = String(valores.nota ?? "").trim();
    if ("costo" in valores) {
      const costo = parseDecimalInput(String(valores.costo ?? ""));
      if (!positive(costo)) return invalidAmount(codigo, "el costo");
      body.costo = costo;
    }
    if ("precio_venta" in valores) {
      const precio = parseDecimalInput(String(valores.precio_venta ?? ""));
      if (!positive(precio)) {
        return invalidAmount(codigo, "el precio de venta");
      }
      body.precio_venta = precio;
    }
    cambiosBody.push(body);
  }

  const nuevosBody: Record<string, string | null>[] = [];
  for (const [index, fila] of nuevos.entries()) {
    const name = `Producto nuevo ${index + 1}`;
    const nombre = String(fila?.nombre ?? "").trim();
    if (!nombre) return error(`${name}: indique el nombre del producto.`);
    const rawCosto = String(fila?.costo ?? "").trim();
    const rawPrecio = String(fila?.precio_venta ?? "").trim();
    const rawUnidades = String(fila?.unidades ?? "").trim();
    const costo = rawCosto ? parseDecimalInput(rawCosto) : null;
    const precio = rawPrecio ? parseDecimalInput(rawPrecio) : null;
    const unidades = rawUnidades ? parseDecimalInput(rawUnidades) : null;
    if (rawCosto && !positive(costo)) return invalidAmount(name, "el costo");
    if (rawPrecio && !positive(precio)) {
      return invalidAmount(name, "el precio de venta");
    }
    if (rawUnidades && !positive(unidades)) {
      return invalidAmount(name, "las unidades");
    }
    if (!rawCosto && (rawPrecio || rawUnidades)) {
      return error(
        `${name}: cargue el costo de compra para poder guardar el precio de venta o las unidades.`,
      );
    }
    nuevosBody.push({
      nombre,
      categoria: String(fila?.categoria ?? "").trim() || null,
      proveedor: String(fila?.proveedor ?? "").trim() || null,
      nota: String(fila?.nota ?? "").trim() || null,
      costo,
      precio_venta: precio,
      unidades,
    });
  }

  const result = await apiPost<ProductoReventa[]>("/reventa/lote", {
    cambios: cambiosBody,
    nuevos: nuevosBody,
  });
  if (!result.ok) {
    return fromFailure(result, {
      409: "Ya hay un producto de mercadería con ese nombre.",
    });
  }
  refresh();
  const partes = [
    cambiosBody.length > 0
      ? `${cambiosBody.length} ${cambiosBody.length === 1 ? "producto cambiado" : "productos cambiados"}`
      : null,
    nuevosBody.length > 0
      ? `${nuevosBody.length} ${nuevosBody.length === 1 ? "producto nuevo" : "productos nuevos"}`
      : null,
  ].filter(Boolean);
  return ok(`Listo: ${partes.join(", ")}.`);
}

/** A purchase is never edited: a new price is a new purchase in the history. */
export async function registrarCompra(
  codigo: string,
  _previous: FormState,
  formData: FormData,
): Promise<FormState> {
  const denied = await denyUnlessWriter();
  if (denied) return denied;

  const unidades = parseDecimalInput(text(formData, "unidades"));
  if (!positive(unidades)) {
    return error("Ingrese las unidades compradas, mayores que cero.");
  }
  const costo = parseDecimalInput(text(formData, "costo"));
  if (!positive(costo)) {
    return error(
      "Ingrese el costo por unidad mayor que cero, por ejemplo 12500.",
    );
  }
  const precioTexto = text(formData, "precio_venta");
  const precio = precioTexto ? parseDecimalInput(precioTexto) : null;
  if (precioTexto && !positive(precio)) {
    return error(
      "El precio de venta por unidad tiene que ser mayor que cero. Si no lo sabe todavía, déjelo vacío.",
    );
  }

  const result = await apiPost<ProductoReventaDetalle>(
    `/reventa/${encodeURIComponent(codigo)}/compras`,
    {
      unidades,
      costo_unitario_ars: costo,
      precio_venta_unitario_ars: precio,
      fecha: optional(formData, "fecha"),
      proveedor: optional(formData, "proveedor"),
      nota: optional(formData, "nota"),
    },
  );
  if (!result.ok) return fromFailure(result);
  refresh();
  return ok(
    `Compra registrada. Costo por unidad: ${formatArs(result.data.costo_unitario_ars)}.`,
  );
}

/** Archiving hides nothing and deletes nothing: the purchase history stays. */
export async function setActivo(
  codigo: string,
  activo: boolean,
  _previous: FormState,
  _formData: FormData,
): Promise<FormState> {
  const denied = await denyUnlessWriter();
  if (denied) return denied;

  const result = await apiPost<ProductoReventaDetalle>(
    `/reventa/${encodeURIComponent(codigo)}/activo`,
    { activo },
  );
  if (!result.ok) return fromFailure(result);
  refresh();
  return ok(activo ? "Producto activado." : "Producto archivado.");
}
