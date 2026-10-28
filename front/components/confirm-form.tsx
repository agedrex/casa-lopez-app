"use client";

import {
  type FormEvent,
  type ReactNode,
  useEffect,
  useRef,
  useState,
} from "react";
import type { FormState } from "@/lib/action-state";
import { useActionForm } from "@/lib/use-action-form";
import { FormFeedback, PrimaryButton, SecondaryButton } from "./form";

type Action = (previous: FormState, formData: FormData) => Promise<FormState>;

/**
 * A form that asks twice. The first press of the button only shows `summary(formData)`
 * (what will change, built by the caller from the typed values); the second press, on
 * "Confirm", sends the form. Editing any field after the summary appeared takes it back,
 * so the person always confirms what is actually going to be saved.
 */
export function ConfirmForm({
  action,
  summary,
  reviewLabel,
  confirmLabel,
  pendingLabel,
  children,
}: {
  action: Action;
  summary: (formData: FormData) => ReactNode;
  reviewLabel: string;
  confirmLabel: string;
  pendingLabel: string;
  children: ReactNode;
}) {
  const { state, pending, formKey, onSubmit } = useActionForm(action);
  const [review, setReview] = useState<ReactNode | null>(null);
  const panel = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (state.status === "ok") setReview(null);
  }, [state]);

  useEffect(() => {
    if (review !== null) panel.current?.focus();
  }, [review]);

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    if (review === null) {
      event.preventDefault();
      setReview(summary(new FormData(event.currentTarget)));
      return;
    }
    onSubmit(event);
  }

  return (
    <form
      key={formKey}
      onSubmit={handleSubmit}
      onChange={() => setReview(null)}
      className="space-y-5"
    >
      {children}
      <div
        ref={panel}
        tabIndex={-1}
        aria-live="polite"
        className="outline-none"
      >
        {review !== null ? (
          <fieldset className="min-w-0 rounded-card border border-blush-deep bg-blush/30 px-4 py-3 text-sm">
            <legend className="sr-only">Confirmar el cambio</legend>
            {review}
          </fieldset>
        ) : null}
      </div>
      <FormFeedback state={state} />
      {review === null ? (
        <SecondaryButton pending={pending}>{reviewLabel}</SecondaryButton>
      ) : (
        <PrimaryButton pending={pending}>
          {pending ? pendingLabel : confirmLabel}
        </PrimaryButton>
      )}
    </form>
  );
}
