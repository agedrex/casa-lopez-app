"use client";

import { ConfirmForm } from "@/components/confirm-form";
import { Field, inputClass } from "@/components/form";
import { PARAMETER_STATES, splitStatus, unitLabel } from "@/lib/parametros";
import type { Parametro } from "@/lib/types";
import { updateParametro } from "./actions";

export function ParametroForm({
  parametro,
  currentLabel,
}: {
  parametro: Parametro;
  currentLabel: string;
}) {
  const isText =
    parametro.valor_texto !== null || parametro.unidad === "AAAA-MM";
  const status = splitStatus(parametro.fuente_estado);
  const id = `parametro-${parametro.codigo}`;

  return (
    <ConfirmForm
      action={updateParametro.bind(null, parametro.codigo)}
      reviewLabel="Revisar el cambio"
      confirmLabel="Confirmar y guardar"
      pendingLabel="Guardando…"
      summary={(data) => {
        const next = String(data.get(isText ? "valor_texto" : "valor") ?? "");
        return (
          <>
            <p className="font-bold text-ink-soft">
              {parametro.constante}: de {currentLabel} a {next || "—"}
            </p>
            <p className="mt-1 text-muted">
              El valor anterior no se guarda: si se equivoca, hay que volver a
              cargarlo a mano. Las cotizaciones ya guardadas no cambian; las
              próximas usan el valor nuevo.
            </p>
          </>
        );
      }}
    >
      <div className="grid gap-5 sm:grid-cols-3">
        <Field
          id={`${id}-valor`}
          label={isText ? "Nuevo período" : "Nuevo valor"}
          hint={unitLabel(parametro.unidad)}
        >
          <input
            id={`${id}-valor`}
            name={isText ? "valor_texto" : "valor"}
            required
            autoComplete="off"
            inputMode={isText ? "numeric" : "decimal"}
            placeholder={isText ? "2026-11" : undefined}
            defaultValue={isText ? (parametro.valor_texto ?? "") : currentLabel}
            aria-describedby={`${id}-valor-hint`}
            className={inputClass}
          />
        </Field>
        <Field id={`${id}-estado`} label="Estado">
          <select
            id={`${id}-estado`}
            name="fuente_estado"
            required
            defaultValue={status.state}
            className={inputClass}
          >
            <option value="" disabled>
              Elegir…
            </option>
            {PARAMETER_STATES.map((state) => (
              <option key={state} value={state}>
                {state}
              </option>
            ))}
          </select>
        </Field>
        <Field
          id={`${id}-nota`}
          label="Nota (opcional)"
          hint="Quién lo definió y cuándo."
        >
          <input
            id={`${id}-nota`}
            name="nota"
            maxLength={300}
            autoComplete="off"
            defaultValue={status.note}
            aria-describedby={`${id}-nota-hint`}
            className={inputClass}
          />
        </Field>
      </div>
    </ConfirmForm>
  );
}
