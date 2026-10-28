"use client";

import {
  Field,
  FormFeedback,
  inputClass,
  PrimaryButton,
} from "@/components/form";
import { SIZES } from "@/lib/modelos";
import { useActionForm } from "@/lib/use-action-form";
import { createModelo } from "./actions";
import { ConsumptionFields, type ForroOption } from "./consumption-fields";

export function ModeloNuevoForm({
  categorias,
  forros,
}: {
  categorias: string[];
  forros: ForroOption[];
}) {
  const { state, pending, onSubmit } = useActionForm(createModelo);
  // No form key: on success the action redirects to the new model.
  return (
    <form onSubmit={onSubmit} className="space-y-6">
      <div className="grid gap-5 sm:grid-cols-3">
        <Field
          id="modelo-nombre"
          label="Nombre del modelo"
          hint="No puede repetirse: agregue algo que lo distinga."
        >
          <input
            id="modelo-nombre"
            name="nombre_del_modelo"
            required
            maxLength={200}
            autoComplete="off"
            aria-describedby="modelo-nombre-hint"
            className={inputClass}
          />
        </Field>
        <Field id="modelo-categoria" label="Categoría">
          <select
            id="modelo-categoria"
            name="categoria"
            required
            defaultValue=""
            className={inputClass}
          >
            <option value="" disabled>
              Elegir…
            </option>
            {categorias.map((categoria) => (
              <option key={categoria} value={categoria}>
                {categoria}
              </option>
            ))}
          </select>
        </Field>
        <Field id="modelo-tamano" label="Tamaño (opcional)">
          <select
            id="modelo-tamano"
            name="tamano"
            defaultValue=""
            className={inputClass}
          >
            <option value="">Sin tamaño</option>
            {SIZES.map((size) => (
              <option key={size.value} value={size.value}>
                {size.label}
              </option>
            ))}
          </select>
        </Field>
      </div>
      <ConsumptionFields prefix="nuevo" forros={forros} />
      <Field id="modelo-nota" label="Nota (opcional)">
        <input
          id="modelo-nota"
          name="nota"
          autoComplete="off"
          className={inputClass}
        />
      </Field>
      <FormFeedback state={state} />
      <PrimaryButton pending={pending}>
        {pending ? "Creando…" : "Crear modelo"}
      </PrimaryButton>
    </form>
  );
}
