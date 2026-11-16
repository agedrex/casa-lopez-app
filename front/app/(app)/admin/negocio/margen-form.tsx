"use client";

import { useActionState } from "react";
import { FormFeedback, inputClass, PrimaryButton } from "@/components/form";
import { IDLE } from "@/lib/action-state";
import { guardarMargenTransferencia } from "./actions";

/** Admin edits the margin the factory earns selling to the store (percent of the transfer price). */
export function MargenForm({ pct }: { pct: string | null }) {
  const [state, dispatch, pending] = useActionState(
    guardarMargenTransferencia,
    IDLE,
  );
  return (
    <form action={dispatch} className="flex flex-wrap items-end gap-3">
      <label className="text-sm">
        <span className="mb-1 block text-muted">
          Margen de transferencia (%)
        </span>
        <input
          name="margen"
          inputMode="decimal"
          defaultValue={pct === null ? "" : String(Number(pct))}
          className={`${inputClass} w-28`}
        />
      </label>
      <label className="flex items-center gap-2 text-sm">
        <input type="checkbox" name="confirmado" /> Ya está confirmado
      </label>
      <PrimaryButton pending={pending}>Guardar margen</PrimaryButton>
      <FormFeedback state={state} />
    </form>
  );
}
