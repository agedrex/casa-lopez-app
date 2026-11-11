"use client";

import {
  Field,
  FormFeedback,
  inputClass,
  PrimaryButton,
} from "@/components/form";
import { useActionForm } from "@/lib/use-action-form";
import { createReventa } from "../actions";

export function ReventaForm({ categorias }: { categorias: string[] }) {
  const { state, pending, onSubmit } = useActionForm(createReventa);
  // No form key: on success the action redirects to the new product.
  return (
    <form onSubmit={onSubmit} className="space-y-5">
      <div className="grid gap-5 sm:grid-cols-2">
        <Field id="reventa-nombre" label="Nombre">
          <input
            id="reventa-nombre"
            name="nombre"
            required
            maxLength={200}
            autoComplete="off"
            className={inputClass}
          />
        </Field>
        <Field id="reventa-categoria" label="Categoría (opcional)">
          <select
            id="reventa-categoria"
            name="categoria"
            defaultValue=""
            className={inputClass}
          >
            <option value="">Sin categoría</option>
            {categorias.map((categoria) => (
              <option key={categoria} value={categoria}>
                {categoria}
              </option>
            ))}
          </select>
        </Field>
        <Field id="reventa-proveedor" label="Proveedor (opcional)">
          <input
            id="reventa-proveedor"
            name="proveedor"
            autoComplete="off"
            className={inputClass}
          />
        </Field>
        <Field id="reventa-nota" label="Nota (opcional)">
          <input
            id="reventa-nota"
            name="nota"
            autoComplete="off"
            className={inputClass}
          />
        </Field>
      </div>
      <FormFeedback state={state} />
      <PrimaryButton pending={pending}>
        {pending ? "Creando…" : "Crear producto"}
      </PrimaryButton>
    </form>
  );
}
