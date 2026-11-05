"use client";

import { updateProveedor } from "../actions";
import { ProveedorForm, type ProveedorValues } from "../proveedor-form";

export function EditarForm({
  codigo,
  initial,
}: {
  codigo: string;
  initial: ProveedorValues;
}) {
  return (
    <ProveedorForm
      action={updateProveedor.bind(null, codigo)}
      initial={initial}
      submitLabel="Guardar datos"
      pendingLabel="Guardando…"
    />
  );
}
