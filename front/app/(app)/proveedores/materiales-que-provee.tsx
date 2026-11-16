"use client";

import { FormFeedback, PrimaryButton } from "@/components/form";
import type { MaterialOption } from "@/lib/proveedores";
import { useActionForm } from "@/lib/use-action-form";
import { setMaterialesQueProvee } from "./actions";

/**
 * The grid of materials a supplier can provide: one checkbox per material of the materials grid, grouped by stage.
 * Only what is ticked is sent (`materiales`); there is no free text, so a supplier never "provides" something the
 * grid does not have.
 */
export function MaterialesGrid({
  materials,
  selected = [],
}: {
  materials: MaterialOption[];
  selected?: string[];
}) {
  const groups = [...new Set(materials.map((m) => m.group))];
  if (materials.length === 0) {
    return <p className="text-sm text-muted">No hay materiales cargados.</p>;
  }
  return (
    <div className="space-y-4">
      {groups.map((group) => (
        <fieldset key={group} className="rounded-card border border-line p-4">
          <legend className="px-1 text-sm font-bold">{group}</legend>
          <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
            {materials
              .filter((m) => m.group === group)
              .map((m) => (
                <label
                  key={m.codigo}
                  className="flex min-h-10 items-center gap-2 text-sm"
                >
                  <input
                    type="checkbox"
                    name="materiales"
                    value={m.codigo}
                    defaultChecked={selected.includes(m.codigo)}
                    className="size-4"
                  />
                  {m.label}
                </label>
              ))}
          </div>
        </fieldset>
      ))}
    </div>
  );
}

/** Saves the whole list of a supplier in one go; the ones left unticked are marked inactive, never deleted. */
export function MaterialesQueProveeForm({
  codigo,
  materials,
  selected,
}: {
  codigo: string;
  materials: MaterialOption[];
  selected: string[];
}) {
  const { state, pending, formKey, onSubmit } = useActionForm(
    setMaterialesQueProvee.bind(null, codigo),
  );
  return (
    <form key={formKey} onSubmit={onSubmit} className="space-y-5">
      <MaterialesGrid materials={materials} selected={selected} />
      <FormFeedback state={state} />
      <PrimaryButton pending={pending}>
        {pending ? "Guardando…" : "Guardar lista"}
      </PrimaryButton>
    </form>
  );
}
