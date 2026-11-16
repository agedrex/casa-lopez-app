"use client";

import { useState, useTransition } from "react";
import {
  FormFeedback,
  inputClass,
  PrimaryButton,
  SecondaryButton,
} from "@/components/form";
import { type FormState, IDLE } from "@/lib/action-state";
import { devolverHoja, validarHoja } from "../actions";

/**
 * The two decisions of the admin on a completed sheet: validate it (the measures go to the model) or send it back to the
 * taller with a comment. Rendered only for an admin and a COMPLETADO sheet; the actions and the API check the role again.
 */
export function RevisionHoja({ codigo }: { codigo: string }) {
  const [comentario, setComentario] = useState("");
  const [state, setState] = useState<FormState>(IDLE);
  const [pending, startTransition] = useTransition();

  const decidir = (accion: () => Promise<FormState>) =>
    startTransition(async () => {
      setState(await accion());
    });

  return (
    <form
      className="space-y-4"
      onSubmit={(event) => {
        event.preventDefault();
        const submitter = (event.nativeEvent as SubmitEvent).submitter;
        const devolver =
          submitter instanceof HTMLButtonElement &&
          submitter.value === "devolver";
        decidir(() =>
          devolver ? devolverHoja(codigo, comentario) : validarHoja(codigo),
        );
      }}
    >
      <div>
        <label
          htmlFor="revision-comentario"
          className="mb-1.5 block text-sm uppercase tracking-caps-sm text-muted sm:text-xs"
        >
          Comentario para el taller
        </label>
        <textarea
          id="revision-comentario"
          rows={3}
          maxLength={2000}
          value={comentario}
          onChange={(event) => setComentario(event.target.value)}
          aria-describedby="revision-comentario-hint"
          className={inputClass}
        />
        <p
          id="revision-comentario-hint"
          className="mt-1 text-sm text-muted sm:text-xs"
        >
          Solo hace falta para devolver la hoja: el taller lo lee arriba de la
          hoja.
        </p>
      </div>
      <FormFeedback state={state} />
      <div className="flex flex-col gap-3 sm:flex-row">
        <PrimaryButton pending={pending} name="accion" value="validar">
          Validar
        </PrimaryButton>
        <SecondaryButton pending={pending} name="accion" value="devolver">
          Devolver al taller
        </SecondaryButton>
      </div>
    </form>
  );
}
