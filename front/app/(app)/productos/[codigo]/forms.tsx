"use client";

import {
  Field,
  FormFeedback,
  inputClass,
  PrimaryButton,
} from "@/components/form";
import { useActionForm } from "@/lib/use-action-form";
import { addComponente, addExtra, saveCotizacion } from "./actions";

export type ExtraOption = { codigo: string; label: string; group: string };

export function ExtraForm({
  codigo,
  materials,
  colores,
}: {
  codigo: string;
  materials: ExtraOption[];
  colores: string[];
}) {
  const { state, pending, formKey, onSubmit } = useActionForm(
    addExtra.bind(null, codigo),
  );
  const groups = [...new Set(materials.map((m) => m.group))];
  return (
    <form key={formKey} onSubmit={onSubmit} className="space-y-4">
      <Field id="extra-material" label="Material">
        <select
          id="extra-material"
          name="material"
          required
          defaultValue=""
          className={inputClass}
        >
          <option value="">Elegir…</option>
          {groups.map((group) => (
            <optgroup key={group} label={group}>
              {materials
                .filter((m) => m.group === group)
                .map((m) => (
                  <option key={m.codigo} value={m.codigo}>
                    {m.label}
                  </option>
                ))}
            </optgroup>
          ))}
        </select>
      </Field>
      <div className="grid gap-4 sm:grid-cols-2">
        <Field
          id="extra-color"
          label="Color (opcional)"
          hint={
            colores.length === 0
              ? "Todavía no hay colores cargados."
              : undefined
          }
        >
          <select
            id="extra-color"
            name="color"
            defaultValue=""
            disabled={colores.length === 0}
            aria-describedby={
              colores.length === 0 ? "extra-color-hint" : undefined
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
        <Field id="extra-consumo" label="Consumo por unidad">
          <input
            id="extra-consumo"
            name="consumo"
            inputMode="decimal"
            autoComplete="off"
            required
            placeholder="0,25"
            className={inputClass}
          />
        </Field>
      </div>
      <Field id="extra-nota" label="Nota (opcional)">
        <input
          id="extra-nota"
          name="nota"
          autoComplete="off"
          className={inputClass}
        />
      </Field>
      <FormFeedback state={state} />
      <PrimaryButton pending={pending}>
        {pending ? "Agregando…" : "Agregar extra"}
      </PrimaryButton>
    </form>
  );
}

export function CotizacionForm({ codigo }: { codigo: string }) {
  const { state, pending, formKey, onSubmit } = useActionForm(
    saveCotizacion.bind(null, codigo),
  );
  return (
    <form key={formKey} onSubmit={onSubmit} className="space-y-4">
      <div className="grid gap-4 sm:grid-cols-2">
        <Field id="cotizacion-tipo" label="Tipo">
          <select
            id="cotizacion-tipo"
            name="tipo"
            required
            defaultValue="INICIAL"
            className={inputClass}
          >
            <option value="INICIAL">Inicial</option>
            <option value="RECOTIZACION">Recotización</option>
            <option value="FINAL">Final</option>
          </select>
        </Field>
        <Field
          id="cotizacion-fecha"
          label="Fecha (opcional)"
          hint="Si la deja vacía se usa la fecha del producto para ese tipo."
        >
          <input
            id="cotizacion-fecha"
            name="fecha"
            type="date"
            aria-describedby="cotizacion-fecha-hint"
            className={inputClass}
          />
        </Field>
      </div>
      <p className="text-xs text-muted">
        Se guarda una foto del costo a esa fecha. No se edita: si algo cambia,
        se guarda otra.
      </p>
      <FormFeedback state={state} />
      <PrimaryButton pending={pending}>
        {pending ? "Guardando…" : "Guardar cotización"}
      </PrimaryButton>
    </form>
  );
}

export function ComponenteForm({ codigo }: { codigo: string }) {
  const { state, pending, formKey, onSubmit } = useActionForm(
    addComponente.bind(null, codigo),
  );
  return (
    <form key={formKey} onSubmit={onSubmit} className="space-y-4">
      <div className="grid gap-4 sm:grid-cols-2">
        <Field id="componente-producto" label="Producto componente">
          <input
            id="componente-producto"
            name="componente"
            autoComplete="off"
            required
            placeholder="PRD-0001"
            className={inputClass}
          />
        </Field>
        <Field id="componente-cantidad" label="Cantidad">
          <input
            id="componente-cantidad"
            name="cantidad"
            inputMode="decimal"
            autoComplete="off"
            required
            defaultValue="1"
            className={inputClass}
          />
        </Field>
      </div>
      <FormFeedback state={state} />
      <PrimaryButton pending={pending}>
        {pending ? "Agregando…" : "Agregar componente"}
      </PrimaryButton>
    </form>
  );
}
