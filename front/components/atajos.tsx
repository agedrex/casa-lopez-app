"use client";

import { useRouter } from "next/navigation";
import { useEffect } from "react";

/** Fields where a key is text, not a shortcut. */
function estaEscribiendo(target: EventTarget | null): boolean {
  if (!(target instanceof HTMLElement)) return false;
  return (
    target.isContentEditable ||
    target.closest("input, textarea, select, [contenteditable]") !== null
  );
}

/**
 * Keyboard shortcuts of a list page: "/" focuses the search box, "n" goes to the "Nuevo …" page.
 * Renders nothing. They are ignored while typing in a field and with Ctrl, Alt or Cmd pressed.
 * `nuevo` is the href of the page's "Nuevo …" link; without it (a role that cannot create) "n" does nothing.
 */
export function Atajos({ nuevo }: { nuevo?: string }) {
  const router = useRouter();

  useEffect(() => {
    function onKeyDown(event: KeyboardEvent) {
      if (event.defaultPrevented || event.isComposing) return;
      if (event.ctrlKey || event.metaKey || event.altKey) return;
      if (estaEscribiendo(event.target)) return;
      if (event.key === "/") {
        const buscador = document.querySelector<HTMLInputElement>(
          'main input[type="search"], input[type="search"]',
        );
        if (!buscador) return;
        event.preventDefault();
        buscador.focus();
        buscador.select();
      } else if (event.key === "n" && nuevo) {
        event.preventDefault();
        router.push(nuevo);
      }
    }
    document.addEventListener("keydown", onKeyDown);
    return () => document.removeEventListener("keydown", onKeyDown);
  }, [nuevo, router]);

  return null;
}
