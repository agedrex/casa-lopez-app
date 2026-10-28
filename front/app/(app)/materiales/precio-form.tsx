"use client";

import { useState } from "react";
import {
  Field,
  FormFeedback,
  inputClass,
  PrimaryButton,
  SecondaryButton,
} from "@/components/form";
import { useActionForm } from "@/lib/use-action-form";
import { createPrecio } from "./actions";

export type MaterialOption = {
  codigo: string;
  label: string;
  unidad: string;
  group: string;
};

export function PrecioForm({
  materials,
  colores,
  today,
  defaultMaterial,
}: {
  materials: MaterialOption[];
  colores: string[];
  today: string;
  defaultMaterial: string;
}) {
  const { state, pending, formKey, onSubmit } = useActionForm(createPrecio);
  return (
    <form key={formKey} onSubmit={onSubmit} className="space-y-5" id="cargar">
      <Fields
        materials={materials}
        colores={colores}
        today={today}
        defaultMaterial={defaultMaterial}
      />
      <FormFeedback state={state} />
      <div className="flex flex-wrap gap-3">
        {state.needsConfirm ? (
          <>
            <PrimaryButton pending={pending} name="confirmar" value="1">
              Cargar igual
            </PrimaryButton>
            <SecondaryButton pending={pending}>
              Corregir y volver a comprobar
            </SecondaryButton>
          </>
        ) : (
          <PrimaryButton pending={pending}>
            {pending ? "Cargando…" : "Cargar precio nuevo"}
          </PrimaryButton>
        )}
      </div>
    </form>
  );
}

// Lives below the form key so the selected material resets with the form.
function Fields({
  materials,
  colores,
  today,
  defaultMaterial,
}: {
  materials: MaterialOption[];
  colores: string[];
  today: string;
  defaultMaterial: string;
}) {
  const [material, setMaterial] = useState(defaultMaterial);
  const unidad = materials.find((m) => m.codigo === material)?.unidad ?? "";
  const groups = [...new Set(materials.map((m) => m.group))];

  return (
    <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-4">
      <Field id="precio-material" label="Material">
        <select
          id="precio-material"
          name="material"
          required
          value={material}
          onChange={(event) => setMaterial(event.target.value)}
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
      <Field
        id="precio-color"
        label="Color (opcional)"
        hint={
          colores.length === 0 ? "Todavía no hay colores cargados." : undefined
        }
      >
        <select
          id="precio-color"
          name="color"
          defaultValue=""
          disabled={colores.length === 0}
          aria-describedby={
            colores.length === 0 ? "precio-color-hint" : undefined
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
      <Field id="precio-precio" label="Precio">
        <input
          id="precio-precio"
          name="precio"
          inputMode="decimal"
          autoComplete="off"
          required
          className={inputClass}
        />
      </Field>
      <Field id="precio-moneda" label="Moneda">
        <select
          id="precio-moneda"
          name="moneda"
          required
          defaultValue="USD"
          className={inputClass}
        >
          <option value="USD">USD</option>
          <option value="ARS">ARS</option>
        </select>
      </Field>
      <Field
        id="precio-unidad"
        label="Unidad del precio"
        hint="Siempre es la unidad de consumo del material."
      >
        <input
          id="precio-unidad"
          value={unidad || "—"}
          readOnly
          aria-describedby="precio-unidad-hint"
          className={`${inputClass} bg-paper-mid`}
        />
        <input type="hidden" name="unidad_del_precio" value={unidad} />
      </Field>
      <Field id="precio-desde" label="Vigente desde">
        <input
          id="precio-desde"
          name="vigente_desde"
          type="date"
          required
          defaultValue={today}
          className={inputClass}
        />
      </Field>
      <Field id="precio-proveedor" label="Proveedor (opcional)">
        <input
          id="precio-proveedor"
          name="proveedor"
          autoComplete="off"
          className={inputClass}
        />
      </Field>
      <Field id="precio-nota" label="Nota (opcional)">
        <input
          id="precio-nota"
          name="nota_fuente"
          autoComplete="off"
          className={inputClass}
        />
      </Field>
    </div>
  );
}
