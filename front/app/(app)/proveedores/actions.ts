"use server";

import { refresh } from "next/cache";
import { redirect } from "next/navigation";
import { error, type FormState, ok } from "@/lib/action-state";
import { apiPost } from "@/lib/api";
import type { Proveedor } from "@/lib/types";
import {
  denyUnlessWriter,
  fromFailure,
  optional,
  text,
} from "@/lib/write-guard";

const CONFLICT_PROVEEDOR = "Ya hay un proveedor con ese nombre o con ese CUIT.";

function proveedorBody(formData: FormData) {
  return {
    nombre: text(formData, "nombre"),
    cuit: optional(formData, "cuit"),
    contacto: optional(formData, "contacto"),
    telefono: optional(formData, "telefono"),
    direccion: optional(formData, "direccion"),
    nota: optional(formData, "nota"),
  };
}

export async function createProveedor(
  _previous: FormState,
  formData: FormData,
): Promise<FormState> {
  const denied = await denyUnlessWriter();
  if (denied) return denied;

  const body = proveedorBody(formData);
  if (!body.nombre) return error("Indique el nombre del proveedor.");

  const result = await apiPost<Proveedor>("/proveedores", body);
  if (!result.ok) {
    return fromFailure(result, { 409: CONFLICT_PROVEEDOR });
  }
  // The ticked materials of the grid; if saving them fails the supplier exists already, so say so.
  const materiales = formData.getAll("materiales").map(String);
  if (materiales.length > 0) {
    const provee = await apiPost<string[]>(
      `/proveedores/${encodeURIComponent(result.data.codigo)}/provee`,
      { materiales },
    );
    if (!provee.ok) {
      return error(
        `El proveedor se creó (${result.data.codigo}) pero no se pudo guardar su lista de productos: ${provee.message}`,
      );
    }
  }
  redirect(`/proveedores/${encodeURIComponent(result.data.codigo)}`);
}

/** Sets the whole list of materials this supplier provides (all or nothing). */
export async function setMaterialesQueProvee(
  codigo: string,
  _previous: FormState,
  formData: FormData,
): Promise<FormState> {
  const denied = await denyUnlessWriter();
  if (denied) return denied;

  const materiales = formData.getAll("materiales").map(String);
  const result = await apiPost<string[]>(
    `/proveedores/${encodeURIComponent(codigo)}/provee`,
    { materiales },
  );
  if (!result.ok)
    return fromFailure(result, { 404: "No existe ese proveedor." });
  refresh();
  return ok(
    materiales.length === 0
      ? "Lista guardada: el proveedor no tiene productos."
      : `Lista guardada: ${materiales.length} ${materiales.length === 1 ? "producto" : "productos"}.`,
  );
}
