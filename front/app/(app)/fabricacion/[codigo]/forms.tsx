"use client";

import type { ReactNode } from "react";
import {
  Field,
  FormFeedback,
  inputClass,
  PrimaryButton,
  SecondaryButton,
} from "@/components/form";
import { LOT_STATES, lotStateLabel } from "@/lib/format";
import { useActionForm } from "@/lib/use-action-form";
import { addItem, changeEstado, savePrecios } from "../actions";
import { type ProductoOption, ProductRows } from "../product-rows";

export type Option = { codigo: string; label: string };

export function EstadoForm({
  codigo,
  actual,
  personas,
  today,
  entrega,
}: {
  codigo: string;
  actual: string;
  personas: Option[];
  today: string;
  entrega: string | null;
}) {
  const { state, pending, formKey, onSubmit } = useActionForm(
    changeEstado.bind(null, codigo),
  );
  return (
    <form key={formKey} onSubmit={onSubmit} className="space-y-4">
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Field id="estado-nuevo" label="Nuevo estado">
          <select
            id="estado-nuevo"
            name="estado"
            required
            defaultValue=""
            className={inputClass}
          >
            <option value="">Elegir…</option>
            {LOT_STATES.filter((code) => code !== actual).map((code) => (
              <option key={code} value={code}>
                {lotStateLabel(code)}
              </option>
            ))}
          </select>
        </Field>
        <Field id="estado-fecha" label="Fecha del cambio">
          <input
            id="estado-fecha"
            name="fecha"
            type="date"
            required
            defaultValue={today}
            className={inputClass}
          />
        </Field>
        <Field id="estado-quien" label="Quién (opcional)">
          <select
            id="estado-quien"
            name="quien"
            defaultValue=""
            className={inputClass}
          >
            <option value="">Sin indicar</option>
            {personas.map((persona) => (
              <option key={persona.codigo} value={persona.codigo}>
                {persona.label}
              </option>
            ))}
          </select>
        </Field>
        <Field
          id="estado-entrega"
          label="Fecha de entrega"
          hint="Obligatoria para cerrar: cierra la cotización final."
        >
          <input
            id="estado-entrega"
            name="fecha_de_entrega"
            type="date"
            defaultValue={entrega ?? ""}
            aria-describedby="estado-entrega-hint"
            className={inputClass}
          />
        </Field>
      </div>
      <p className="text-sm text-muted">
        Un lote cerrado no se puede reabrir. Cada cambio queda en el historial.
      </p>
      <FormFeedback state={state} />
      <PrimaryButton pending={pending}>
        {pending ? "Guardando…" : "Cambiar estado"}
      </PrimaryButton>
    </form>
  );
}

export function ItemForm({
  codigo,
  productos,
}: {
  codigo: string;
  productos: ProductoOption[];
}) {
  const { state, pending, formKey, onSubmit } = useActionForm(
    addItem.bind(null, codigo),
  );
  return (
    <form key={formKey} onSubmit={onSubmit} className="space-y-4">
      <ProductRows productos={productos} idPrefix="agregar" fixedRows />
      <FormFeedback state={state} />
      <SecondaryButton pending={pending}>
        {pending ? "Agregando…" : "Agregar al lote"}
      </SecondaryButton>
    </form>
  );
}

export function PreciosForm({
  codigo,
  item,
  producto,
  cotizado,
  pagado,
  referencia,
}: {
  codigo: string;
  item: string;
  producto: string;
  cotizado: string | null;
  pagado: string | null;
  referencia?: ReactNode;
}) {
  const { state, pending, formKey, onSubmit } = useActionForm(
    savePrecios.bind(null, codigo, item),
  );
  return (
    <form
      key={formKey}
      onSubmit={onSubmit}
      aria-label={`Precios del taller para ${producto}`}
      className="space-y-3"
    >
      <p className="text-base font-bold">{producto}</p>
      {referencia}
      <div className="grid gap-4 sm:grid-cols-[1fr_auto] sm:items-end">
        <Field
          id={`precio-pagado-${item}`}
          label="Precio pagado por unidad (al retirar)"
        >
          <input
            id={`precio-pagado-${item}`}
            name="pagado"
            inputMode="decimal"
            autoComplete="off"
            defaultValue={pagado ?? ""}
            className={inputClass}
          />
        </Field>
        <SecondaryButton pending={pending}>
          {pending ? "Guardando…" : "Guardar precios"}
        </SecondaryButton>
      </div>
      <details open={cotizado !== null} className="sm:max-w-sm">
        <summary className="min-h-11 cursor-pointer py-2 text-base text-muted">
          Lo que pidió el taller (opcional)
        </summary>
        <Field id={`precio-cotizado-${item}`} label="Cotizado por unidad">
          <input
            id={`precio-cotizado-${item}`}
            name="cotizado"
            inputMode="decimal"
            autoComplete="off"
            defaultValue={cotizado ?? ""}
            className={inputClass}
          />
        </Field>
      </details>
      <FormFeedback state={state} />
    </form>
  );
}
