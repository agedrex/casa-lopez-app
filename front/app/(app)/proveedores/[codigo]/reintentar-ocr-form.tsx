"use client";

import { FormFeedback, SecondaryButton } from "@/components/form";
import { useActionForm } from "@/lib/use-action-form";
import { retryOcr } from "../actions";

export function ReintentarOcrForm({ id }: { id: number }) {
  const { state, pending, onSubmit } = useActionForm(retryOcr.bind(null, id));
  return (
    <form onSubmit={onSubmit} className="space-y-3">
      <FormFeedback state={state} />
      <SecondaryButton pending={pending}>
        {pending ? "Leyendo…" : "Reintentar OCR"}
      </SecondaryButton>
    </form>
  );
}
