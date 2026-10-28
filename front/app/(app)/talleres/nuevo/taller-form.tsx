"use client";

import {
  Field,
  FormFeedback,
  inputClass,
  PrimaryButton,
} from "@/components/form";
import { useActionForm } from "@/lib/use-action-form";
import { createTaller } from "../actions";

export function TallerForm() {
  const { state, pending, onSubmit } = useActionForm(createTaller);
  // No form key: on success the action redirects to the new workshop.
  return (
    <form onSubmit={onSubmit} className="space-y-5">
      <div className="grid gap-5 sm:grid-cols-2">
        <Field id="taller-nombre" label="Nombre">
          <input
            id="taller-nombre"
            name="nombre"
            required
            autoComplete="off"
            className={inputClass}
          />
        </Field>
        <Field
          id="taller-cuit"
          label="CUIT (opcional)"
          hint="No puede repetirse entre talleres."
        >
          <input
            id="taller-cuit"
            name="cuit"
            autoComplete="off"
            inputMode="numeric"
            aria-describedby="taller-cuit-hint"
            className={inputClass}
          />
        </Field>
        <Field id="taller-telefono" label="Teléfono (opcional)">
          <input
            id="taller-telefono"
            name="telefono"
            type="tel"
            autoComplete="off"
            className={inputClass}
          />
        </Field>
        <Field id="taller-contacto" label="Contacto (opcional)">
          <input
            id="taller-contacto"
            name="contacto"
            autoComplete="off"
            className={inputClass}
          />
        </Field>
      </div>
      <Field id="taller-direccion" label="Dirección (opcional)">
        <input
          id="taller-direccion"
          name="direccion"
          autoComplete="off"
          className={inputClass}
        />
      </Field>
      <Field id="taller-nota" label="Nota (opcional)">
        <input
          id="taller-nota"
          name="nota"
          autoComplete="off"
          className={inputClass}
        />
      </Field>
      <FormFeedback state={state} />
      <PrimaryButton pending={pending}>
        {pending ? "Creando…" : "Crear taller"}
      </PrimaryButton>
    </form>
  );
}
