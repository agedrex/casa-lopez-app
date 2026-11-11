"use client";

import { ConfirmForm } from "@/components/confirm-form";
import { formatPeriod } from "@/lib/format";
import { copiarMes } from "./actions";

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
