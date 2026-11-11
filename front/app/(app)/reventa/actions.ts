"use server";

import { refresh } from "next/cache";
import { redirect } from "next/navigation";
import { error, type FormState, ok } from "@/lib/action-state";
import { apiPost } from "@/lib/api";
import { formatArs, parseDecimalInput } from "@/lib/format";
import type { ProductoReventaDetalle } from "@/lib/types";
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
