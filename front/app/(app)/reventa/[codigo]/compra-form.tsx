"use client";

import {
  Field,
  FormFeedback,
  inputClass,
  PrimaryButton,
} from "@/components/form";
import { useActionForm } from "@/lib/use-action-form";
import { registrarCompra } from "../actions";

export function CompraForm({
  codigo,
  proveedor,
}: {
  codigo: string;
  proveedor: string | null;
}) {
  const { state, pending, formKey, onSubmit } = useActionForm(
    registrarCompra.bind(null, codigo),
  );
  return (
    <form key={formKey} onSubmit={onSubmit} className="space-y-5">
      <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
        <Field id="compra-unidades" label="Unidades compradas">
          <input
            id="compra-unidades"
            name="unidades"
            required
            inputMode="decimal"
            autoComplete="off"
            className={inputClass}
          />
        </Field>
        <Field id="compra-costo" label="Costo por unidad (ARS)">
          <input
            id="compra-costo"
            name="costo"
            required
            inputMode="decimal"
            autoComplete="off"
            className={inputClass}
          />
        </Field>
        <Field
          id="compra-precio-venta"
          label="Precio de venta por unidad (opcional)"
          hint="Si lo deja vacío, la compra queda sin precio de venta."
        >
          <input
            id="compra-precio-venta"
            name="precio_venta"
            inputMode="decimal"
            autoComplete="off"
            aria-describedby="compra-precio-venta-hint"
            className={inputClass}
          />
        </Field>
        <Field
          id="compra-fecha"
          label="Fecha (opcional)"
          hint="Si la deja vacía, se usa la de hoy."
        >
          <input
            id="compra-fecha"
            name="fecha"
            type="date"
            aria-describedby="compra-fecha-hint"
            className={inputClass}
          />
        </Field>
        <Field
          id="compra-proveedor"
          label="Proveedor (opcional)"
          hint={
            proveedor
              ? `Si lo deja vacío, se usa ${proveedor}.`
              : "A quién se la compró."
          }
        >
          <input
            id="compra-proveedor"
            name="proveedor"
            autoComplete="off"
            aria-describedby="compra-proveedor-hint"
            className={inputClass}
          />
        </Field>
        <Field id="compra-nota" label="Nota (opcional)">
          <input
            id="compra-nota"
            name="nota"
            autoComplete="off"
            className={inputClass}
          />
        </Field>
      </div>
      <FormFeedback state={state} />
      <PrimaryButton pending={pending}>
        {pending ? "Guardando…" : "Registrar compra"}
      </PrimaryButton>
    </form>
  );
}
