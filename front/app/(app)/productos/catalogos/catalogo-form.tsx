"use client";

import {
  Field,
  FormFeedback,
  inputClass,
  PrimaryButton,
} from "@/components/form";
import { useActionForm } from "@/lib/use-action-form";
import { createCategoria, createColor } from "./actions";

export function CatalogoForm({
  kind,
  noun,
}: {
  kind: "color" | "categoria";
  noun: string;
}) {
  const { state, pending, formKey, onSubmit } = useActionForm(
    kind === "color" ? createColor : createCategoria,
  );
  return (
    <form key={formKey} onSubmit={onSubmit} className="space-y-4">
      <Field id={`${kind}-nombre`} label={`Nombre de ${noun}`}>
        <input
          id={`${kind}-nombre`}
          name="nombre"
          required
          maxLength={120}
          autoComplete="off"
          className={inputClass}
        />
      </Field>
      <Field id={`${kind}-nota`} label="Nota (opcional)">
        <input
          id={`${kind}-nota`}
          name="nota"
          autoComplete="off"
          className={inputClass}
        />
      </Field>
      <FormFeedback state={state} />
      <PrimaryButton pending={pending}>
        {pending ? "Cargando…" : `Agregar ${noun}`}
      </PrimaryButton>
    </form>
  );
}
