"use client";

import {
  Field,
  FormFeedback,
  inputClass,
  SecondaryButton,
} from "@/components/form";
import { useActionForm } from "@/lib/use-action-form";
import { duplicarFormulario } from "../actions";

/** Admin only: a new BORRADOR for another article with the rows (names, quantities, comments) of this form. */
export function DuplicarForm({ codigo }: { codigo: string }) {
  const { state, pending, onSubmit } = useActionForm(
    duplicarFormulario.bind(null, codigo),
  );
  // No form key: on success the action redirects to the copy.
  return (
    <details className="rounded-card border border-line p-4 print:hidden">
      <summary className="cursor-pointer text-sm uppercase tracking-caps-sm text-muted">
        Duplicar para otro artículo
      </summary>
      <form onSubmit={onSubmit} className="mt-4 space-y-4">
        <Field
          id={`duplicar-${codigo}`}
          label="Artículo del formulario nuevo"
          hint="Copia las filas, cantidades y comentarios; el formulario nuevo arranca en borrador."
        >
          <input
            id={`duplicar-${codigo}`}
            name="articulo"
            required
            maxLength={200}
            autoComplete="off"
            aria-describedby={`duplicar-${codigo}-hint`}
            className={inputClass}
          />
        </Field>
        <FormFeedback state={state} />
        <SecondaryButton pending={pending}>
          {pending ? "Duplicando…" : "Duplicar"}
        </SecondaryButton>
      </form>
    </details>
  );
}
