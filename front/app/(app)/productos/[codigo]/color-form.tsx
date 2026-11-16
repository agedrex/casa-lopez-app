"use client";

import { FormFeedback, SecondaryButton } from "@/components/form";
import { useActionForm } from "@/lib/use-action-form";
import { CatalogoSelect } from "../catalogo-select";
import { saveColor } from "./actions";

/** Fills in, changes or clears the color of the product. Rendered for admin only; the action and the API check again. */
export function ColorForm({
  codigo,
  color,
  colores,
}: {
  codigo: string;
  color: string | null;
  colores: string[];
}) {
  const { state, pending, formKey, onSubmit } = useActionForm(
    saveColor.bind(null, codigo),
  );
  // A color that is no longer in the catalog list is still shown so the select never lies.
  const options =
    color && !colores.includes(color) ? [color, ...colores] : colores;
  return (
    <form
      key={formKey}
      onSubmit={onSubmit}
      className="flex flex-wrap items-end gap-4"
    >
      <div className="min-w-64 flex-1">
        <CatalogoSelect
          id="ficha-color"
          name="color"
          label="Color"
          createLabel="+ Crear color nuevo…"
          newNameLabel="Nombre del color nuevo"
          emptyLabel="Sin color"
          options={options}
          defaultValue={color ?? ""}
        />
      </div>
      <SecondaryButton pending={pending}>
        {pending ? "Guardando…" : "Guardar color"}
      </SecondaryButton>
      <div className="basis-full">
        <FormFeedback state={state} />
      </div>
    </form>
  );
}
