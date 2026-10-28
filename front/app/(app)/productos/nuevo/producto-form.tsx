"use client";

import {
  Field,
  FormFeedback,
  inputClass,
  PrimaryButton,
} from "@/components/form";
import { useActionForm } from "@/lib/use-action-form";
import { createProducto } from "../actions";

export type ModeloOption = { codigo: string; label: string };
export type CueroOption = { codigo: string; label: string };

export function ProductoForm({
  modelos,
  cueros,
  colores,
  today,
}: {
  modelos: ModeloOption[];
  cueros: CueroOption[];
  colores: string[];
  today: string;
}) {
  const { state, pending, onSubmit } = useActionForm(createProducto);
  // No form key: on success the action redirects to the new product's page.
  return (
    <form onSubmit={onSubmit} className="space-y-5">
      <div className="grid gap-5 sm:grid-cols-2">
        <Field
          id="producto-modelo"
          label="Modelo"
          hint="Escriba el código o parte del nombre y elija de la lista."
        >
          <input
            id="producto-modelo"
            name="modelo"
            list="producto-modelos"
            autoComplete="off"
            aria-describedby="producto-modelo-hint"
            className={inputClass}
          />
          <datalist id="producto-modelos">
            {modelos.map((modelo) => (
              <option key={modelo.codigo} value={modelo.codigo}>
                {modelo.label}
              </option>
            ))}
          </datalist>
        </Field>
        <Field
          id="producto-cuero"
          label="Cuero"
          hint="Solo aparecen los cueros que se pueden cotizar."
        >
          <select
            id="producto-cuero"
            name="cuero"
            defaultValue=""
            aria-describedby="producto-cuero-hint"
            className={inputClass}
          >
            <option value="">Elegir…</option>
            {cueros.map((cuero) => (
              <option key={cuero.codigo} value={cuero.codigo}>
                {cuero.label}
              </option>
            ))}
          </select>
        </Field>
        <Field
          id="producto-color"
          label="Color (opcional)"
          hint={
            colores.length === 0
              ? "Todavía no hay colores cargados."
              : undefined
          }
        >
          <select
            id="producto-color"
            name="color"
            defaultValue=""
            disabled={colores.length === 0}
            aria-describedby={
              colores.length === 0 ? "producto-color-hint" : undefined
            }
            className={inputClass}
          >
            <option value="">Sin color</option>
            {colores.map((color) => (
              <option key={color} value={color}>
                {color}
              </option>
            ))}
          </select>
        </Field>
        <Field id="producto-quien" label="Quién lo confecciona">
          <select
            id="producto-quien"
            name="quien_lo_confecciona"
            required
            defaultValue=""
            className={inputClass}
          >
            <option value="">Elegir…</option>
            <option value="EXTERNA">Externa (taller)</option>
            <option value="INTERNA">Interna</option>
          </select>
        </Field>
        <Field id="producto-alta" label="Fecha de alta">
          <input
            id="producto-alta"
            name="fecha_de_alta"
            type="date"
            defaultValue={today}
            className={inputClass}
          />
        </Field>
        <Field
          id="producto-nombre"
          label="Nombre propio (opcional)"
          hint="Si lo deja vacío, el nombre se arma con el modelo, el cuero y el color."
        >
          <input
            id="producto-nombre"
            name="nombre_propio"
            autoComplete="off"
            aria-describedby="producto-nombre-hint"
            className={inputClass}
          />
        </Field>
      </div>
      <Field id="producto-nota" label="Nota (opcional)">
        <input
          id="producto-nota"
          name="nota"
          autoComplete="off"
          className={inputClass}
        />
      </Field>
      <div className="flex items-start gap-3">
        <input
          id="producto-kit"
          name="es_kit"
          type="checkbox"
          className="mt-0.5 size-5 accent-ink"
        />
        <label htmlFor="producto-kit" className="text-sm">
          Es un kit
          <span className="block text-xs text-muted">
            Un kit se arma con otros productos: después de crearlo, agregue sus
            componentes desde la ficha. Un kit puede ir sin modelo ni cuero.
          </span>
        </label>
      </div>
      <FormFeedback state={state} />
      <PrimaryButton pending={pending}>
        {pending ? "Creando…" : "Crear producto"}
      </PrimaryButton>
    </form>
  );
}
