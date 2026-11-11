"use client";

import { FormFeedback, SecondaryButton } from "@/components/form";
import { useActionForm } from "@/lib/use-action-form";
import { setActivo } from "../actions";

export function ActivoForm({
  codigo,
  activo,
}: {
  codigo: string;
  activo: boolean;
}) {
  const { state, pending, onSubmit } = useActionForm(
    setActivo.bind(null, codigo, !activo),
  );
  return (
    <form onSubmit={onSubmit} className="space-y-3">
      <p className="text-sm text-muted">
        {activo
          ? "Archivar oculta el producto de las listas nuevas. No se borra nada: sus compras quedan en el historial."
          : "Este producto está archivado. Activarlo lo vuelve a mostrar como uno más."}
      </p>
      <FormFeedback state={state} />
      <SecondaryButton pending={pending}>
        {activo ? "Archivar producto" : "Activar producto"}
      </SecondaryButton>
    </form>
  );
}
