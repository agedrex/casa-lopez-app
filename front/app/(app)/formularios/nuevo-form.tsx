"use client";

import {
  Field,
  FormFeedback,
  inputClass,
  PrimaryButton,
} from "@/components/form";
import { useActionForm } from "@/lib/use-action-form";
import { crearFormulario } from "./actions";

export type TallerOption = { codigo: string; nombre: string };

export function NuevoFormularioForm({
  talleres,
}: {
  talleres: TallerOption[];
}) {
  const { state, pending, onSubmit } = useActionForm(crearFormulario);
  // No form key: on success the action redirects to the new form.
  return (
    <form onSubmit={onSubmit} className="space-y-5">
      <div className="grid gap-5 sm:grid-cols-3">
        <Field id="formulario-nuevo-articulo" label="Artículo">
          <input
            id="formulario-nuevo-articulo"
            name="articulo"
            required
            maxLength={200}
            autoComplete="off"
            placeholder="Nombre o código del artículo"
            className={inputClass}
          />
        </Field>
        <Field id="formulario-nuevo-taller" label="Taller (opcional)">
          <select
            id="formulario-nuevo-taller"
            name="taller"
            defaultValue=""
            className={inputClass}
          >
            <option value="">Sin elegir</option>
            {talleres.map((taller) => (
              <option key={taller.codigo} value={taller.codigo}>
                {taller.nombre} ({taller.codigo})
              </option>
            ))}
          </select>
        </Field>
        <Field
          id="formulario-nuevo-producto"
          label="Producto (opcional)"
          hint="Código del producto, para que su ficha muestre el formulario validado."
        >
          <input
            id="formulario-nuevo-producto"
            name="producto"
            autoComplete="off"
            placeholder="PRD-0001"
            aria-describedby="formulario-nuevo-producto-hint"
            className={inputClass}
          />
        </Field>
      </div>
      <FormFeedback state={state} />
      <PrimaryButton pending={pending}>
        {pending ? "Creando…" : "Crear formulario"}
      </PrimaryButton>
    </form>
  );
}
