"use client";

import {
  Field,
  FormFeedback,
  inputClass,
  PrimaryButton,
} from "@/components/form";
import { SIZES } from "@/lib/modelos";
import { useActionForm } from "@/lib/use-action-form";
import { CatalogoSelect } from "../catalogo-select";
import { FOTO_ACCEPT } from "./[codigo]/foto-limites";
import { createModelo } from "./actions";

/** The only "Nuevo modelo" form (also shown in /productos/nuevo): no consumptions, they are loaded from the model page. */
export function ModeloNuevoForm({ categorias }: { categorias: string[] }) {
  const { state, pending, onSubmit } = useActionForm(createModelo);
  // No form key: on success the action redirects to the new model.
  return (
    <form onSubmit={onSubmit} className="space-y-5">
      <div className="grid gap-5 sm:grid-cols-3">
        <Field
          id="modelo-nombre"
          label="Nombre del modelo"
          hint="Se guarda en MAYÚSCULAS y no puede repetirse: agregue algo que lo distinga."
        >
          <input
            id="modelo-nombre"
            name="nombre_del_modelo"
            required
            maxLength={200}
            autoComplete="off"
            aria-describedby="modelo-nombre-hint"
            className={`${inputClass} uppercase`}
          />
        </Field>
        <CatalogoSelect
          id="modelo-categoria"
          name="categoria"
          label="Categoría"
          createLabel="+ Crear categoría nueva…"
          newNameLabel="Nombre de la categoría nueva"
          emptyLabel="Elegir…"
          options={categorias}
          required
        />
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
      <Field
        id="modelo-foto"
        label="Foto del modelo"
        hint="Es la guía que se usa para armar el modelo. JPG, PNG o WebP, de hasta 5 MB. También se puede subir después, desde la ficha."
      >
        <input
          id="modelo-foto"
          name="foto"
          type="file"
          accept={FOTO_ACCEPT}
          aria-describedby="modelo-foto-hint"
          className={inputClass}
        />
      </Field>
      <Field
        id="modelo-nota"
        label="Notas (opcional)"
        hint="Medidas, materiales, detalles."
      >
        <textarea
          id="modelo-nota"
          name="nota"
          rows={2}
          maxLength={2000}
          aria-describedby="modelo-nota-hint"
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
