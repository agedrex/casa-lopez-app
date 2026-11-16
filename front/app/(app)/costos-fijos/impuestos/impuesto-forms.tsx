"use client";

import {
  Field,
  FormFeedback,
  inputClass,
  PrimaryButton,
  SecondaryButton,
} from "@/components/form";
import { useActionForm } from "@/lib/use-action-form";
import {
  createImpuesto,
  setImpuestoActivo,
  setImpuestoAlicuota,
} from "./actions";
import { fractionToPercentInput } from "./percent";

export function ImpuestoForm() {
  const { state, pending, formKey, onSubmit } = useActionForm(createImpuesto);
  return (
    <form key={formKey} onSubmit={onSubmit} className="space-y-5">
      <div className="grid gap-5 sm:grid-cols-2">
        <Field id="impuesto-nombre" label="Nombre">
          <input
            id="impuesto-nombre"
            name="nombre"
            required
            maxLength={120}
            autoComplete="off"
            className={inputClass}
          />
        </Field>
        <Field
          id="impuesto-porcentaje"
          label="Porcentaje (%)"
          hint="Se calcula sobre el precio de venta. Por ejemplo 21 o 3,5."
        >
          <input
            id="impuesto-porcentaje"
            name="porcentaje"
            required
            inputMode="decimal"
            autoComplete="off"
            aria-describedby="impuesto-porcentaje-hint"
            className={inputClass}
          />
        </Field>
      </div>
      <FormFeedback state={state} />
      <PrimaryButton pending={pending}>
        {pending ? "Cargando…" : "Agregar impuesto"}
      </PrimaryButton>
    </form>
  );
}

export function AlicuotaForm({
  codigo,
  nombre,
  alicuota,
}: {
  codigo: string;
  nombre: string;
  alicuota: string | null;
}) {
  const { state, pending, onSubmit } = useActionForm(
    setImpuestoAlicuota.bind(null, codigo),
  );
  const id = `porcentaje-${codigo}`;
  return (
    <form onSubmit={onSubmit} className="space-y-2">
      <div className="flex items-center gap-2">
        <label htmlFor={id} className="sr-only">
          Porcentaje de {nombre}
        </label>
        <input
          id={id}
          name="porcentaje"
          required
          inputMode="decimal"
          autoComplete="off"
          defaultValue={fractionToPercentInput(alicuota)}
          placeholder="A confirmar"
          className={`${inputClass} w-28`}
        />
        <span aria-hidden="true">%</span>
        <SecondaryButton pending={pending}>
          {pending ? "Guardando…" : "Guardar"}
          <span className="sr-only"> el porcentaje de {nombre}</span>
        </SecondaryButton>
      </div>
      <FormFeedback state={state} />
    </form>
  );
}

export function ImpuestoActivoForm({
  codigo,
  nombre,
  activo,
}: {
  codigo: string;
  nombre: string;
  activo: boolean;
}) {
  const { state, pending, onSubmit } = useActionForm(
    setImpuestoActivo.bind(null, codigo, !activo),
  );
  return (
    <form onSubmit={onSubmit} className="space-y-2">
      <FormFeedback state={state} />
      <SecondaryButton pending={pending}>
        {pending ? "Guardando…" : activo ? "Desactivar" : "Activar"}
        <span className="sr-only"> {nombre}</span>
      </SecondaryButton>
    </form>
  );
}
