"use client";

import {
  Field,
  FormFeedback,
  inputClass,
  PrimaryButton,
} from "@/components/form";
import type { FormState } from "@/lib/action-state";
import { useActionForm } from "@/lib/use-action-form";

type Action = (previous: FormState, formData: FormData) => Promise<FormState>;

/** New supplier: its data only (what it offers is listed on its page). The code is assigned by the backend, never typed. */
export function ProveedorForm({
  action,
  submitLabel,
  pendingLabel,
}: {
  action: Action;
  submitLabel: string;
  pendingLabel: string;
}) {
  // The action redirects to the new supplier.
  const { state, pending, formKey, onSubmit } = useActionForm(action);
  return (
    <form key={formKey} onSubmit={onSubmit} className="space-y-5">
      <div className="grid gap-5 sm:grid-cols-2">
        <Field id="proveedor-nombre" label="Nombre">
          <input
            id="proveedor-nombre"
            name="nombre"
            required
            autoComplete="off"
            className={inputClass}
          />
        </Field>
        <Field
          id="proveedor-cuit"
          label="CUIT (opcional)"
          hint="No puede repetirse entre proveedores."
        >
          <input
            id="proveedor-cuit"
            name="cuit"
            autoComplete="off"
            inputMode="numeric"
            aria-describedby="proveedor-cuit-hint"
            className={inputClass}
          />
        </Field>
        <Field id="proveedor-contacto" label="Contacto (opcional)">
          <input
            id="proveedor-contacto"
            name="contacto"
            autoComplete="off"
            className={inputClass}
          />
        </Field>
        <Field id="proveedor-telefono" label="Teléfono (opcional)">
          <input
            id="proveedor-telefono"
            name="telefono"
            type="tel"
            autoComplete="off"
            className={inputClass}
          />
        </Field>
      </div>
      <Field id="proveedor-direccion" label="Dirección (opcional)">
        <input
          id="proveedor-direccion"
          name="direccion"
          autoComplete="off"
          className={inputClass}
        />
      </Field>
      <Field id="proveedor-nota" label="Descripción (opcional)">
        <input
          id="proveedor-nota"
          name="nota"
          autoComplete="off"
          className={inputClass}
        />
      </Field>
      <FormFeedback state={state} />
      <PrimaryButton pending={pending}>
        {pending ? pendingLabel : submitLabel}
      </PrimaryButton>
    </form>
  );
}
