"use client";

import { ConfirmForm } from "@/components/confirm-form";
import {
  Field,
  FormFeedback,
  inputClass,
  PrimaryButton,
  SecondaryButton,
} from "@/components/form";
import {
  EXPENSE_CATEGORIES,
  expenseCategoryLabel,
  formatPeriod,
} from "@/lib/format";
import { useActionForm } from "@/lib/use-action-form";
import { copiarMes, corregirGasto, createGasto, setMonto } from "./actions";

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
        Un gasto cargado no se edita: si el monto estaba mal, use «Corregir
        monto» en su fila. Un gasto sin monto queda pendiente hasta que se
        conozca.
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

export function MontoForm({
  codigo,
  concepto,
}: {
  codigo: string;
  concepto: string;
}) {
  const { state, pending, formKey, onSubmit } = useActionForm(
    setMonto.bind(null, codigo),
  );
  return (
    <form
      key={formKey}
      onSubmit={onSubmit}
      aria-label={`Cargar el monto de ${concepto}`}
      className="flex w-full flex-col gap-2 sm:w-auto sm:min-w-56"
    >
      <div className="flex items-end gap-2">
        <div className="flex-1">
          <label
            htmlFor={`monto-${codigo}`}
            className="mb-1 block text-xs uppercase tracking-caps-sm text-muted"
          >
            Monto
          </label>
          <input
            id={`monto-${codigo}`}
            name="monto"
            inputMode="decimal"
            autoComplete="off"
            required
            className={inputClass}
          />
        </div>
        <SecondaryButton pending={pending}>
          {pending ? "…" : "Cargar"}
        </SecondaryButton>
      </div>
      <FormFeedback state={state} />
    </form>
  );
}

/** Small collapsible form in the row: a correction adds a new row, it never edits the old one. */
export function CorregirForm({
  codigo,
  concepto,
}: {
  codigo: string;
  concepto: string;
}) {
  const { state, pending, formKey, onSubmit } = useActionForm(
    corregirGasto.bind(null, codigo),
  );
  return (
    <details className="mt-2 text-left">
      <summary
        aria-label={`Corregir el monto de ${concepto}`}
        className="inline-flex min-h-11 cursor-pointer items-center text-sm underline decoration-gold underline-offset-4 sm:min-h-0"
      >
        Corregir monto
      </summary>
      <form
        key={formKey}
        onSubmit={onSubmit}
        aria-label={`Corregir el monto de ${concepto}`}
        className="mt-2 flex w-full flex-col gap-3 sm:min-w-64"
      >
        <p className="text-xs text-muted">
          El monto anterior queda en el historial y deja de sumarse.
        </p>
        <div>
          <label
            htmlFor={`corregir-monto-${codigo}`}
            className="mb-1 block text-xs uppercase tracking-caps-sm text-muted"
          >
            Monto nuevo (ARS)
          </label>
          <input
            id={`corregir-monto-${codigo}`}
            name="monto"
            inputMode="decimal"
            autoComplete="off"
            required
            className={inputClass}
          />
        </div>
        <div>
          <label
            htmlFor={`corregir-nota-${codigo}`}
            className="mb-1 block text-xs uppercase tracking-caps-sm text-muted"
          >
            Nota (opcional)
          </label>
          <input
            id={`corregir-nota-${codigo}`}
            name="nota"
            autoComplete="off"
            placeholder="Por qué se corrige"
            className={inputClass}
          />
        </div>
        <div className="flex items-start gap-3">
          <input
            id={`corregir-ficticio-${codigo}`}
            name="ficticio"
            type="checkbox"
            className="mt-0.5 size-5 accent-ink"
          />
          <label htmlFor={`corregir-ficticio-${codigo}`} className="text-sm">
            Es un monto de ejemplo
          </label>
        </div>
        <FormFeedback state={state} />
        <SecondaryButton pending={pending}>
          {pending ? "Corrigiendo…" : "Corregir"}
        </SecondaryButton>
      </form>
    </details>
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
