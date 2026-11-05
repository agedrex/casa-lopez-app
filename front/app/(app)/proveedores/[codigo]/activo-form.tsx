"use client";

import { FormFeedback, SecondaryButton } from "@/components/form";
import { useActionForm } from "@/lib/use-action-form";
import { setProveedorActivo } from "../actions";

export function ActivoForm({
  codigo,
  activo,
}: {
  codigo: string;
  activo: boolean;
}) {
  const { state, pending, onSubmit } = useActionForm(
    setProveedorActivo.bind(null, codigo, !activo),
  );
  return (
    <form onSubmit={onSubmit} className="space-y-3">
      <p className="text-sm text-muted">
        {activo
          ? "Desactivar oculta al proveedor de las listas. No se borra nada: sus facturas e imágenes quedan."
          : "Este proveedor está desactivado. Activarlo lo vuelve a mostrar en las listas."}
      </p>
      <FormFeedback state={state} />
      <SecondaryButton pending={pending}>
        {activo ? "Desactivar proveedor" : "Activar proveedor"}
      </SecondaryButton>
    </form>
  );
}
