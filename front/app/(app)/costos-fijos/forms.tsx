"use client";

import { ConfirmForm } from "@/components/confirm-form";
import {
  Field,
  FormFeedback,
  inputClass,
  PrimaryButton,
} from "@/components/form";
import {
  EXPENSE_CATEGORIES,
  expenseCategoryLabel,
  formatPeriod,
} from "@/lib/format";
import { useActionForm } from "@/lib/use-action-form";
import { copiarMes, createGasto } from "./actions";

export function GastoForm({
  periodo,
  personas,
}: {
  periodo: string;
  personas: { codigo: string; label: string }[];
}) {
  const { state, pending, formKey, onSubmit } = useActionForm(createGasto);
  return (
    <form key={formKey} onSubmit={onSubmit} className="space-y-5">
      <p className="text-sm text-muted">
        Para cargar varios gastos de una vez, use la grilla de arriba. Acá puede
        cargar uno solo, por ejemplo uno con monto ficticio. Un gasto cargado no
        se pisa: el monto se corrige desde la grilla y el anterior queda en el
        historial. Un gasto sin monto queda pendiente hasta que se conozca.
      </p>
      <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
        <Field id="gasto-periodo" label="Período (AAAA-MM)">
          <input
            id="gasto-periodo"
            name="periodo"
            required
            pattern="[0-9]{4}-(0[1-9]|1[0-2])"
            defaultValue={periodo}
            autoComplete="off"
            className={inputClass}
          />
        </Field>
        <Field id="gasto-concepto" label="Concepto">
          <input
            id="gasto-concepto"
            name="concepto"
            required
            autoComplete="off"
            placeholder="Alquiler de la fábrica"
            className={inputClass}
          />
        </Field>
        <Field id="gasto-lado" label="¿Fábrica o tienda?">
          <select
            id="gasto-lado"
            name="fabrica_o_tienda"
            required
            defaultValue=""
            className={inputClass}
          >
            <option value="">Elegir…</option>
            <option value="FABRICA">Fábrica</option>
            <option value="TIENDA">Tienda</option>
          </select>
        </Field>
        <Field id="gasto-categoria" label="Categoría">
          <select
            id="gasto-categoria"
            name="categoria"
            required
            defaultValue=""
            className={inputClass}
          >
            <option value="">Elegir…</option>
            {EXPENSE_CATEGORIES.map((code) => (
              <option key={code} value={code}>
                {expenseCategoryLabel(code)}
              </option>
            ))}
          </select>
        </Field>
        <Field id="gasto-persona" label="Persona (opcional)">
          <select
            id="gasto-persona"
            name="persona"
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
          id="gasto-monto"
          label="Monto del mes (ARS)"
          hint="Vacío = pendiente de monto."
        >
          <input
            id="gasto-monto"
            name="monto"
            inputMode="decimal"
            autoComplete="off"
            aria-describedby="gasto-monto-hint"
            className={inputClass}
          />
        </Field>
      </div>
      <Field id="gasto-nota" label="Nota o fuente (opcional)">
        <input
          id="gasto-nota"
          name="nota_fuente"
          autoComplete="off"
          className={inputClass}
        />
      </Field>
      <div className="flex items-start gap-3">
        <input
          id="gasto-ficticio"
          name="ficticio"
          type="checkbox"
          className="mt-0.5 size-5 accent-ink"
        />
        <label htmlFor="gasto-ficticio" className="text-sm">
          Monto ficticio
          <span className="block text-xs text-muted">
            Un valor de prueba que se reemplaza por el real.
          </span>
        </label>
      </div>
      <FormFeedback state={state} />
      <PrimaryButton pending={pending}>
        {pending ? "Cargando…" : "Cargar gasto"}
      </PrimaryButton>
    </form>
  );
}

/** Copies last month's rows into an empty month. Asks twice (ConfirmForm) before writing. */
export function CopiarMesForm({
  desde,
  hasta,
}: {
  desde: string;
  hasta: string;
}) {
  return (
    <ConfirmForm
      action={copiarMes}
      reviewLabel={`Copiar el mes anterior (${formatPeriod(desde)})`}
      confirmLabel="Sí, copiar"
      pendingLabel="Copiando…"
      summary={(formData) => (
        <p>
          Se van a crear los gastos de <strong>{formatPeriod(hasta)}</strong> a
          partir de los de <strong>{formatPeriod(desde)}</strong>.{" "}
          {formData.get("modo") === "con_montos"
            ? "Cada gasto se copia con su monto."
            : "Los montos quedan pendientes hasta que los cargue."}
        </p>
      )}
    >
      <input type="hidden" name="desde" value={desde} />
      <input type="hidden" name="hasta" value={hasta} />
      <fieldset className="space-y-2">
        <legend className="mb-2 text-sm text-muted">
          ¿Cómo quiere copiarlos?
        </legend>
        <label className="flex min-h-11 items-start gap-3 text-sm">
          <input
            type="radio"
            name="modo"
            value="pendientes"
            defaultChecked
            className="mt-0.5 size-5 accent-ink"
          />
          <span>
            Dejar los montos pendientes
            <span className="block text-xs text-muted">
              Se copian los conceptos y usted carga el monto de cada uno.
            </span>
          </span>
        </label>
        <label className="flex min-h-11 items-start gap-3 text-sm">
          <input
            type="radio"
            name="modo"
            value="con_montos"
            className="mt-0.5 size-5 accent-ink"
          />
          <span>
            Copiar también los montos
            <span className="block text-xs text-muted">
              Después puede corregir los que cambiaron.
            </span>
          </span>
        </label>
      </fieldset>
    </ConfirmForm>
  );
}
