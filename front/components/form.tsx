import type { ReactNode } from "react";
import type { FormState } from "@/lib/action-state";

export const inputClass =
  "min-h-12 w-full rounded-card border border-line bg-surface px-3 py-2 text-base outline-none focus:border-gold disabled:opacity-60 sm:min-h-0 sm:text-sm";

export function Field({
  id,
  label,
  hint,
  children,
}: {
  id: string;
  label: string;
  hint?: string;
  children: ReactNode;
}) {
  return (
    <div>
      <label
        htmlFor={id}
        className="mb-1.5 block text-sm uppercase tracking-caps-sm text-muted sm:text-xs"
      >
        {label}
      </label>
      {children}
      {hint ? (
        <p id={`${id}-hint`} className="mt-1 text-sm text-muted sm:text-xs">
          {hint}
        </p>
      ) : null}
    </div>
  );
}

export function PrimaryButton({
  children,
  pending,
  name,
  value,
}: {
  children: ReactNode;
  pending: boolean;
  name?: string;
  value?: string;
}) {
  return (
    <button
      type="submit"
      name={name}
      value={value}
      disabled={pending}
      className="min-h-12 w-full rounded-card bg-ink px-5 py-2.5 text-sm uppercase tracking-caps-sm text-white transition-colors hover:bg-ink-soft disabled:opacity-60 sm:min-h-0 sm:w-auto"
    >
      {children}
    </button>
  );
}

export function SecondaryButton({
  children,
  pending,
  name,
  value,
}: {
  children: ReactNode;
  pending: boolean;
  name?: string;
  value?: string;
}) {
  return (
    <button
      type="submit"
      name={name}
      value={value}
      disabled={pending}
      className="min-h-12 w-full rounded-card border border-ink px-5 py-2.5 text-sm uppercase tracking-caps-sm hover:bg-ink hover:text-white disabled:opacity-60 sm:min-h-0 sm:w-auto"
    >
      {children}
    </button>
  );
}

/**
 * Result of the last submission. The wrapper is always in the DOM so screen readers
 * announce what appears inside it (aria-live).
 */
export function FormFeedback({ state }: { state: FormState }) {
  const tone =
    state.status === "ok"
      ? "border-sage bg-sage/10"
      : state.status === "warning"
        ? "border-blush-deep bg-blush/30"
        : "border-bordeaux/30 bg-bordeaux/5";
  const titleTone =
    state.status === "error" ? "text-bordeaux" : "text-ink-soft";
  return (
    <div aria-live="polite" aria-atomic="true">
      {state.message ? (
        <div
          role={state.status === "error" ? "alert" : "status"}
          className={`rounded-card border px-4 py-3 text-sm ${tone}`}
        >
          <p className={`font-bold ${titleTone}`}>{state.message}</p>
          {state.avisos && state.avisos.length > 0 ? (
            <ul className="mt-2 list-disc space-y-1 pl-5 text-muted">
              {[...new Set(state.avisos)].map((aviso) => (
                <li key={aviso}>{aviso}</li>
              ))}
            </ul>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}

export function ReadOnlyNote() {
  return (
    <p className="rounded-card border border-line bg-paper-mid px-4 py-3 text-sm text-muted">
      Su rol es de solo consulta: puede ver estos datos, pero no cargarlos.
    </p>
  );
}
