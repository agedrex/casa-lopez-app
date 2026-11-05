"use client";

import {
  Field,
  FormFeedback,
  inputClass,
  SecondaryButton,
} from "@/components/form";
import { decimalInputText } from "@/lib/format";
import { DOCUMENT_TYPES } from "@/lib/proveedores";
import type { DocumentoProveedor } from "@/lib/types";
import { useActionForm } from "@/lib/use-action-form";
import { confirmarDatos } from "../actions";

const ISO_DATE = /^\d{4}-\d{2}-\d{2}$/;

/**
 * Number, date, total and currency typed or confirmed by a person. Empty fields start from
 * what the OCR suggested, so the person only has to check them against the document.
 */
export function ConfirmarDatosForm({
  documento,
}: {
  documento: DocumentoProveedor;
}) {
  const { state, pending, formKey, onSubmit } = useActionForm(
    confirmarDatos.bind(null, documento.id),
  );
  const sugerencia = documento.ocr_sugerencia;
  const suggestedDate =
    sugerencia?.fecha && ISO_DATE.test(sugerencia.fecha)
      ? sugerencia.fecha
      : "";
  const id = `doc-${documento.id}`;
  const totalValue = documento.total ?? sugerencia?.total ?? null;
  const monedaValue = documento.moneda ?? sugerencia?.moneda ?? "";

  return (
    <form key={formKey} onSubmit={onSubmit} className="space-y-4">
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
        <Field id={`${id}-tipo`} label="Tipo">
          <select
            id={`${id}-tipo`}
            name="tipo"
            defaultValue={documento.tipo}
            className={inputClass}
          >
            {DOCUMENT_TYPES.map((item) => (
              <option key={item.value} value={item.value}>
                {item.label}
              </option>
            ))}
          </select>
        </Field>
        <Field id={`${id}-numero`} label="Número">
          <input
            id={`${id}-numero`}
            name="numero"
            autoComplete="off"
            defaultValue={documento.numero ?? sugerencia?.numero ?? ""}
            className={inputClass}
          />
        </Field>
        <Field id={`${id}-fecha`} label="Fecha">
          <input
            id={`${id}-fecha`}
            name="fecha_documento"
            type="date"
            defaultValue={documento.fecha_documento ?? suggestedDate}
            className={inputClass}
          />
        </Field>
        <Field id={`${id}-total`} label="Total">
          <input
            id={`${id}-total`}
            name="total"
            inputMode="decimal"
            autoComplete="off"
            defaultValue={
              totalValue === null ? "" : decimalInputText(totalValue)
            }
            className={inputClass}
          />
        </Field>
        <Field id={`${id}-moneda`} label="Moneda">
          <select
            id={`${id}-moneda`}
            name="moneda"
            defaultValue={monedaValue}
            className={inputClass}
          >
            <option value="">—</option>
            <option value="ARS">Pesos (ARS)</option>
            <option value="USD">Dólares (USD)</option>
          </select>
        </Field>
      </div>
      <FormFeedback state={state} />
      <SecondaryButton pending={pending}>
        {pending ? "Guardando…" : "Confirmar datos"}
      </SecondaryButton>
    </form>
  );
}
