"use client";

import { type ReactNode, useEffect, useId, useRef, useState } from "react";

/**
 * A "?" button that opens a short note (3 lines at most) under it. Esc or a click outside closes it.
 * For what a screen is for: the detail lives one tap away instead of on the page.
 */
export function Ayuda({ children }: { children: ReactNode }) {
  const [open, setOpen] = useState(false);
  const id = useId();
  const root = useRef<HTMLSpanElement>(null);
  const button = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    if (!open) return;
    function onPointerDown(event: PointerEvent) {
      if (!root.current?.contains(event.target as Node)) setOpen(false);
    }
    function onKeyDown(event: globalThis.KeyboardEvent) {
      if (event.key !== "Escape") return;
      setOpen(false);
      button.current?.focus();
    }
    document.addEventListener("pointerdown", onPointerDown);
    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("pointerdown", onPointerDown);
      document.removeEventListener("keydown", onKeyDown);
    };
  }, [open]);

  return (
    <span ref={root} className="relative inline-flex">
      <button
        ref={button}
        type="button"
        aria-label="Ayuda"
        aria-expanded={open}
        aria-controls={id}
        onClick={() => setOpen((current) => !current)}
        className="inline-flex size-9 items-center justify-center rounded-full border border-line bg-surface text-sm font-bold text-muted hover:border-gold hover:text-ink sm:size-7 sm:text-xs"
      >
        ?
      </button>
      {open ? (
        <div
          id={id}
          role="note"
          className="absolute left-0 top-full z-40 mt-2 w-72 space-y-1 max-w-[calc(100vw-2rem)] rounded-card border border-line bg-surface p-3 text-sm font-normal normal-case tracking-normal text-ink-soft shadow-card"
        >
          {children}
        </div>
      ) : null}
    </span>
  );
}
