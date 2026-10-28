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
          ? "Desactivar oculta al taller de los lotes nuevos. No se borra nada: sus lotes y precios quedan."
          : "Este taller está desactivado. Activarlo lo vuelve a ofrecer en los lotes nuevos."}
      </p>
      <FormFeedback state={state} />
      <SecondaryButton pending={pending}>
        {activo ? "Desactivar taller" : "Activar taller"}
      </SecondaryButton>
    </form>
  );
}
