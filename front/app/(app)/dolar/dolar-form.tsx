"use client";

import {
  Field,
  FormFeedback,
  inputClass,
  PrimaryButton,
  SecondaryButton,
} from "@/components/form";
import { useActionForm } from "@/lib/use-action-form";
import { actualizarDolarBna, createDolar } from "./actions";

export function DolarForm({ today }: { today: string }) {
  const { state, pending, formKey, onSubmit } = useActionForm(createDolar);
  return (
    <form
      key={formKey}
      onSubmit={onSubmit}
      className="space-y-5"
      aria-describedby="dolar-form-help"
    >
      <p id="dolar-form-help" className="text-sm text-muted">
        Cada valor queda guardado con su fecha: no se edita ni se borra, se
        carga uno nuevo.
      </p>
      <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-4">
        <Field id="dolar-fecha" label="Fecha">
          <input
            id="dolar-fecha"
            name="fecha"
            type="date"
            required
            defaultValue={today}
            className={inputClass}
          />
        </Field>
        <Field id="dolar-valor" label="Pesos por dólar">
          <input
            id="dolar-valor"
            name="valor"
            inputMode="decimal"
            autoComplete="off"
            required
            placeholder="1545"
            className={inputClass}
          />
        </Field>
        <Field
          id="dolar-tipo"
          label="Tipo"
          hint="SUPUESTO: validar qué tipo usa Casa López."
        >
          <select
            id="dolar-tipo"
            name="tipo"
            defaultValue="VENDEDOR"
            aria-describedby="dolar-tipo-hint"
            className={inputClass}
          >
            <option value="VENDEDOR">Vendedor</option>
            <option value="COMPRADOR">Comprador</option>
          </select>
        </Field>
        <Field id="dolar-fuente" label="Fuente">
          <input
            id="dolar-fuente"
            value="MANUAL"
            readOnly
            className={`${inputClass} bg-paper-mid`}
          />
        </Field>
      </div>
      <Field id="dolar-nota" label="Nota (opcional)">
        <input
          id="dolar-nota"
          name="nota"
          autoComplete="off"
          className={inputClass}
        />
      </Field>
      <FormFeedback state={state} />
      <PrimaryButton pending={pending}>
        {pending ? "Cargando…" : "Cargar dólar"}
      </PrimaryButton>
    </form>
  );
}

export function DolarBnaForm() {
  const { state, pending, onSubmit } = useActionForm(actualizarDolarBna);
  return (
    <form
      onSubmit={onSubmit}
      className="space-y-3"
      aria-describedby="dolar-bna-help"
    >
      <p id="dolar-bna-help" className="text-sm text-muted">
        Trae la cotización vendedor del Banco Nación (bna.com.ar) y la guarda
        con su fecha. Si esa fecha ya estaba cargada, no cambia nada. SUPUESTO:
        validar con Gerardo que el costo use el dólar vendedor.
      </p>
      <FormFeedback state={state} />
      <SecondaryButton pending={pending}>
        {pending ? "Consultando al BNA…" : "Actualizar desde BNA"}
      </SecondaryButton>
    </form>
  );
}
