"use client";

import {
  Field,
  FormFeedback,
  inputClass,
  PrimaryButton,
} from "@/components/form";
import { useActionForm } from "@/lib/use-action-form";
import { createProducto } from "../actions";
import { CatalogoSelect } from "../catalogo-select";

export type ModeloOption = { codigo: string; label: string };
export type CueroOption = { codigo: string; label: string };

export function ProductoForm({
  modelos,
  cueros,
  colores,
  modeloInicial,
}: {
  modelos: ModeloOption[];
  cueros: CueroOption[];
  colores: string[];
  modeloInicial?: string;
}) {
  const { state, pending, onSubmit } = useActionForm(createProducto);
  // No form key: on success the action redirects to the new product's page.
  // The sheet date is not a field: the action fills it in with today's date.
  return (
    <form onSubmit={onSubmit} className="space-y-5">
      <div className="grid gap-5 sm:grid-cols-2">
        <Field id="producto-modelo" label="Modelo">
          <input
            id="producto-modelo"
            name="modelo"
            defaultValue={modeloInicial}
            list="producto-modelos"
            autoComplete="off"
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
        <Field id="producto-nombre" label="Nombre (opcional)">
          <input
            id="producto-nombre"
            name="nombre_propio"
            autoComplete="off"
            className={inputClass}
          />
        </Field>
        <Field id="producto-cuero" label="Cuero">
          <select
            id="producto-cuero"
            name="cuero"
            defaultValue=""
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
        <CatalogoSelect
          id="producto-color"
          name="color"
          label="Color (opcional)"
          createLabel="+ Crear color nuevo…"
          newNameLabel="Nombre del color nuevo"
          emptyLabel="Sin color"
          options={colores}
        />
        <Field id="producto-quien" label="Confeccionamiento">
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
        <Field id="producto-nota" label="Nota (opcional)">
          <input
            id="producto-nota"
            name="nota"
            autoComplete="off"
            className={inputClass}
          />
        </Field>
      </div>
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
