"use client";

import { useActionState } from "react";
import {
  Field,
  FormFeedback,
  inputClass,
  PrimaryButton,
} from "@/components/form";
import { IDLE } from "@/lib/action-state";
import { registrarTransferencia, registrarVenta } from "./actions";

export type ProductOption = { codigo: string; nombre: string };

function ProductPicker({
  id,
  options,
  placeholder,
}: {
  id: string;
  options: ProductOption[];
  placeholder: string;
}) {
  return (
    <>
      <datalist id={`${id}-lista`}>
        {options.map((option) => (
          <option key={option.codigo} value={option.codigo}>
            {option.nombre}
          </option>
        ))}
      </datalist>
      <input
        id={id}
        name="producto"
        list={`${id}-lista`}
        autoComplete="off"
        placeholder={placeholder}
        required
        className={inputClass}
      />
    </>
  );
}

/** Registers one real sale. Admin only (the page checks it; the action and the API check it again). */
export function VentaForm({
  productos,
  hoy,
}: {
  productos: ProductOption[];
  hoy: string;
}) {
  const [state, dispatch, pending] = useActionState(registrarVenta, IDLE);
  return (
    <form action={dispatch} className="space-y-4">
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Field
          id="venta-producto"
          label="Producto"
          hint="Elegí uno de la lista o escribí su código (PRD- o MER-)."
        >
          <ProductPicker
            id="venta-producto"
            options={productos}
            placeholder="Producto o Mercadería"
          />
        </Field>
        <Field id="venta-unidades" label="Unidades">
          <input
            id="venta-unidades"
            name="unidades"
            inputMode="decimal"
            required
            className={inputClass}
          />
        </Field>
        <Field
          id="venta-precio"
          label="Precio cobrado por unidad ($)"
          hint="Lo que se cobró de verdad, sin IVA."
        >
          <input
            id="venta-precio"
            name="precio"
            inputMode="decimal"
            required
            className={inputClass}
          />
        </Field>
        <Field id="venta-fecha" label="Fecha">
          <input
            id="venta-fecha"
            name="fecha"
            type="date"
            defaultValue={hoy}
            className={inputClass}
          />
        </Field>
        <Field id="venta-canal" label="Canal (opcional)">
          <input
            id="venta-canal"
            name="canal"
            maxLength={100}
            placeholder="Tienda, web, mayorista…"
            className={inputClass}
          />
        </Field>
        <div className="sm:col-span-2 lg:col-span-3">
          <Field id="venta-nota" label="Nota (opcional)">
            <input
              id="venta-nota"
              name="nota"
              maxLength={500}
              className={inputClass}
            />
          </Field>
        </div>
      </div>
      <div className="flex flex-wrap items-center gap-3">
        <PrimaryButton pending={pending}>Registrar venta</PrimaryButton>
      </div>
      <FormFeedback state={state} />
    </form>
  );
}

/** Registers one transfer from the factory to the store. Only own products (PRD-), never Mercadería. */
export function TransferenciaForm({
  productos,
  hoy,
}: {
  productos: ProductOption[];
  hoy: string;
}) {
  const [state, dispatch, pending] = useActionState(
    registrarTransferencia,
    IDLE,
  );
  return (
    <form action={dispatch} className="space-y-4">
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Field
          id="pase-producto"
          label="Producto"
          hint="Elegí uno de la lista o escribí su código (PRD-)."
        >
          <ProductPicker
            id="pase-producto"
            options={productos}
            placeholder="Producto"
          />
        </Field>
        <Field id="pase-unidades" label="Unidades">
          <input
            id="pase-unidades"
            name="unidades"
            inputMode="decimal"
            required
            className={inputClass}
          />
        </Field>
        <Field id="pase-fecha" label="Fecha">
          <input
            id="pase-fecha"
            name="fecha"
            type="date"
            defaultValue={hoy}
            className={inputClass}
          />
        </Field>
        <Field id="pase-nota" label="Nota (opcional)">
          <input
            id="pase-nota"
            name="nota"
            maxLength={500}
            className={inputClass}
          />
        </Field>
      </div>
      <div className="flex flex-wrap items-center gap-3">
        <PrimaryButton pending={pending}>Pasar a la tienda</PrimaryButton>
      </div>
      <FormFeedback state={state} />
    </form>
  );
}
