"use client";

import {
  Field,
  FormFeedback,
  inputClass,
  PrimaryButton,
} from "@/components/form";
import { useActionForm } from "@/lib/use-action-form";
import { createProductoRapido } from "../actions";

export function AltaRapidaForm() {
  const { state, pending, onSubmit } = useActionForm(createProductoRapido);
  // On success the action redirects to the form the taller will fill.
  return (
    <form onSubmit={onSubmit} className="space-y-5">
      <Field
        id="alta-nombre"
        label="Nombre del modelo"
        hint="Se guarda en MAYÚSCULAS. El código y la hoja de consumos para el taller se crean solos."
      >
        <input
          id="alta-nombre"
          name="nombre"
          required
          autoComplete="off"
          aria-describedby="alta-nombre-hint"
          className={`${inputClass} uppercase`}
        />
      </Field>
      <FormFeedback state={state} />
      <PrimaryButton pending={pending}>
        {pending ? "Creando…" : "Crear modelo y enviar al taller"}
      </PrimaryButton>
    </form>
  );
}
