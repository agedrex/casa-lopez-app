"use client";

import { FormFeedback, PrimaryButton } from "@/components/form";
import { useActionForm } from "@/lib/use-action-form";
import { savePrecioPorMargen } from "./actions";

/**
 * Saves the price shown above (S4). It sends only the margin: the API computes the price again, so no amount travels from
 * the browser. Rendered for admin and gerente; the action and the API check the role again.
 */
export function PrecioForm({
  codigo,
  margen,
}: {
  codigo: string;
  /** The percentage the person is looking at, as typed ("30" or "32,5"). */
  margen: string;
}) {
  const { state, pending, formKey, onSubmit } = useActionForm(
    savePrecioPorMargen.bind(null, codigo),
  );
  return (
    <form key={formKey} onSubmit={onSubmit} className="space-y-3">
      <input type="hidden" name="margen" value={margen} />
      <PrimaryButton pending={pending} pendingLabel="Guardando…">
        Guardar este precio
      </PrimaryButton>
      <FormFeedback state={state} />
    </form>
  );
}
