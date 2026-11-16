"use server";

import { redirect } from "next/navigation";
import { error, type FormState } from "@/lib/action-state";
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
  redirect(`/proveedores/${encodeURIComponent(result.data.codigo)}`);
}
