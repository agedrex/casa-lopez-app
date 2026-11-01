"use client";

import { useState } from "react";
import {
  Field,
  FormFeedback,
  inputClass,
  PrimaryButton,
} from "@/components/form";
import { useActionForm } from "@/lib/use-action-form";
import { createCuero } from "./actions";

export type Opcion = { value: string; label: string };

const radioClass =
  "flex min-h-12 cursor-pointer items-center gap-3 rounded-card border border-line px-4 text-base has-checked:border-ink has-checked:bg-parchment";

export function CargarCueroForm({
  materiales,
  colores,
  today,
}: {
  materiales: Opcion[];
  colores: Opcion[];
  today: string;
}) {
  const { state, pending, formKey, onSubmit } = useActionForm(createCuero);
  const [origen, setOrigen] = useState("COMPRA");
  const comprado = origen === "COMPRA";

  return (
    <form
      key={formKey}
      onSubmit={onSubmit}
      className="space-y-5"
      aria-describedby="cuero-form-help"
    >
      <fieldset className="space-y-2">
        <legend className="mb-2 text-base font-bold">
          ¿Es cuero comprado o un sobrante que ya tenían?
        </legend>
        <label className={radioClass}>
          <input
            type="radio"
            name="origen"
            value="COMPRA"
            checked={comprado}
            onChange={() => setOrigen("COMPRA")}
            className="size-5"
          />
          Cuero comprado
        </label>
        <label className={radioClass}>
          <input
            type="radio"
            name="origen"
            value="SOBRANTE_EXISTENTE"
            checked={!comprado}
            onChange={() => setOrigen("SOBRANTE_EXISTENTE")}
            className="size-5"
          />
          Sobrante que ya tenían
        </label>
      </fieldset>
      <p id="cuero-form-help" className="text-sm text-muted">
        {comprado
          ? "Al cargar un cuero comprado se descuenta solo el 10 % de desperdicio natural."
          : "Indicá los m² que quedan hoy: no se descuenta desperdicio natural."}
      </p>
      <div className="grid gap-5 sm:grid-cols-2">
        <Field id="cuero-material" label="Cuero">
          <select
            id="cuero-material"
            name="material"
            required
            defaultValue=""
            className={inputClass}
          >
            <option value="" disabled>
              Elegí el cuero
            </option>
            {materiales.map((opcion) => (
              <option key={opcion.value} value={opcion.value}>
                {opcion.label}
              </option>
            ))}
          </select>
        </Field>
        <Field id="cuero-color" label="Color">
          <select
            id="cuero-color"
            name="color"
            defaultValue=""
            className={inputClass}
          >
            <option value="">Sin color</option>
            {colores.map((opcion) => (
              <option key={opcion.value} value={opcion.value}>
                {opcion.label}
              </option>
            ))}
          </select>
        </Field>
        <Field
          id="cuero-m2"
          label={comprado ? "Metros cuadrados comprados" : "m² de hoy"}
        >
          <input
            id="cuero-m2"
            name="m2"
            inputMode="decimal"
            autoComplete="off"
            required
            placeholder="12,5"
            className={inputClass}
          />
        </Field>
        {comprado ? (
          <Field id="cuero-fecha" label="Fecha de compra">
            <input
              id="cuero-fecha"
              name="fecha"
              type="date"
              required
              defaultValue={today}
              className={inputClass}
            />
          </Field>
        ) : null}
      </div>
      {comprado ? (
        <div className="grid gap-5 sm:grid-cols-3">
          <Field id="cuero-precio" label="Precio por m² (opcional)">
            <input
              id="cuero-precio"
              name="precio"
              inputMode="decimal"
              autoComplete="off"
              className={inputClass}
            />
          </Field>
          <Field
            id="cuero-moneda"
            label="Moneda"
            hint="Va junto con el precio."
          >
            <select
              id="cuero-moneda"
              name="moneda"
              defaultValue=""
              aria-describedby="cuero-moneda-hint"
              className={inputClass}
            >
              <option value="">Sin precio</option>
              <option value="ARS">Pesos (ARS)</option>
              <option value="USD">Dólares (USD)</option>
            </select>
          </Field>
          <Field id="cuero-proveedor" label="Proveedor (opcional)">
            <input
              id="cuero-proveedor"
              name="proveedor"
              autoComplete="off"
              className={inputClass}
            />
          </Field>
        </div>
      ) : null}
      <FormFeedback state={state} />
      <PrimaryButton pending={pending}>
        {pending ? "Cargando…" : "Cargar cuero"}
      </PrimaryButton>
    </form>
  );
}
