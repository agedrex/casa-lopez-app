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
import { createPrecioDeProveedor } from "../actions";

export type MaterialOption = {
  codigo: string;
  label: string;
  unidad: string;
  group: string;
};

export function PrecioForm({
  codigo,
  materials,
  colores,
  today,
}: {
  codigo: string;
  materials: MaterialOption[];
  colores: string[];
  today: string;
}) {
  const { state, pending, formKey, onSubmit } = useActionForm(
    createPrecioDeProveedor.bind(null, codigo),
  );
  return (
    <form key={formKey} onSubmit={onSubmit} className="space-y-5">
      <Fields materials={materials} colores={colores} today={today} />
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
            {pending ? "Cargando…" : "Cargar precio"}
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
}: {
  materials: MaterialOption[];
  colores: string[];
  today: string;
}) {
  const [material, setMaterial] = useState("");
  const unidad = materials.find((m) => m.codigo === material)?.unidad ?? "";
  const groups = [...new Set(materials.map((m) => m.group))];

  return (
    <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-4">
      <Field id="prov-precio-material" label="Material">
        <select
          id="prov-precio-material"
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
      <Field id="prov-precio-color" label="Color (opcional)">
        <select
          id="prov-precio-color"
          name="color"
          defaultValue=""
          disabled={colores.length === 0}
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
      <Field id="prov-precio-precio" label="Precio">
        <input
          id="prov-precio-precio"
          name="precio"
          inputMode="decimal"
          autoComplete="off"
          required
          className={inputClass}
        />
      </Field>
      <Field id="prov-precio-moneda" label="Moneda">
        <select
          id="prov-precio-moneda"
          name="moneda"
          required
          defaultValue="ARS"
          className={inputClass}
        >
          <option value="ARS">ARS</option>
          <option value="USD">USD</option>
        </select>
      </Field>
      <Field
        id="prov-precio-unidad"
        label="Unidad del precio"
        hint="Siempre es la unidad de consumo del material."
      >
        <input
          id="prov-precio-unidad"
          value={unidad || "—"}
          readOnly
          aria-describedby="prov-precio-unidad-hint"
          className={`${inputClass} bg-paper-mid`}
        />
      </Field>
      <Field id="prov-precio-desde" label="Vigente desde">
        <input
          id="prov-precio-desde"
          name="vigente_desde"
          type="date"
          required
          defaultValue={today}
          className={inputClass}
        />
      </Field>
      <Field id="prov-precio-nota" label="Nota (opcional)">
        <input
          id="prov-precio-nota"
          name="nota_fuente"
          autoComplete="off"
          placeholder="Por ejemplo: lista de noviembre"
          className={inputClass}
        />
      </Field>
      <div className="flex items-end pb-2">
        <label className="flex items-center gap-2 text-sm">
          <input type="checkbox" name="iva_incluido" className="size-4" />
          El precio incluye IVA
        </label>
      </div>
    </div>
  );
}
