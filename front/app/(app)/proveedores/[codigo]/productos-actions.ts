"use server";

import { refresh } from "next/cache";
import { error, type FormState, ok } from "@/lib/action-state";
import { apiPost } from "@/lib/api";
import {
  leerProductoDeProveedor,
  type ProductoDeProveedorBody,
  type ProductoDeProveedorFila,
} from "@/lib/proveedores";
import type { ProveedorProducto } from "@/lib/types";
import { denyUnlessWriter, fromFailure } from "@/lib/write-guard";

const MAX_ROWS = 200;

/**
 * Saves the "Productos que vende" grid in one call (all or nothing). Every row is a full product:
 * a saved row that changed arrives complete and the API stores it as a new dated row of the same
 * product (nothing is overwritten); a new row is a new product. The price per unit comes back
 * from the API, never from here.
 */
export async function guardarProductosDeProveedor(
  codigo: string,
  filas: ProductoDeProveedorFila[],
): Promise<FormState> {
  const denied = await denyUnlessWriter();
  if (denied) return denied;

  if (!Array.isArray(filas) || filas.length === 0) {
    return error("No hay cambios para guardar.");
  }
  if (filas.length > MAX_ROWS) {
    return error(`Se pueden guardar hasta ${MAX_ROWS} productos por vez.`);
  }
  const productos: ProductoDeProveedorBody[] = [];
  for (const [index, fila] of filas.entries()) {
    const result = leerProductoDeProveedor(fila, index + 1);
    if (!result.ok) return error(result.message);
    productos.push(result.body);
  }

  const result = await apiPost<ProveedorProducto[]>(
    `/proveedores/${encodeURIComponent(codigo)}/productos`,
    { productos },
  );
  if (!result.ok) return fromFailure(result);
  refresh();
  return ok(
    `Listo: ${productos.length} ${productos.length === 1 ? "producto guardado" : "productos guardados"}.`,
  );
}
