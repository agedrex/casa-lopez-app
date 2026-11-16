"use client";

import { useEffect, useState } from "react";
import { AlcanzaResumen } from "@/components/cueros/alcanza-resumen";
import { Notice } from "@/components/ui";
import { parseDecimalInput } from "@/lib/format";
import type { AlcanzaCuero } from "@/lib/types";
import { consultarAlcanzaCuero } from "../actions";
import type { Fila } from "./lote-product-rows";

/** Wait this long after the last keystroke before asking the API. */
export const DEBOUNCE_MS = 500;

type FilaState =
  | { status: "idle" }
  | { status: "loading" }
  | { status: "ok"; resultado: AlcanzaCuero }
  | { status: "error"; message: string };

/** The quantity as the API wants it, or null while it is empty, not a number or zero. */
function cantidadValida(texto: string): string | null {
  const cantidad = parseDecimalInput(texto);
  return cantidad !== null && /[1-9]/.test(cantidad) ? cantidad : null;
}

/**
 * Leather availability of the lot being built: one answer per product row, calculated by the API.
 * It is informative only: whatever it says (or if it fails) the lot can still be created.
 */
export function CueroPanel({
  filas,
  nombres,
}: {
  filas: Fila[];
  nombres: Record<string, string>;
}) {
  if (filas.length === 0) return null;
  return (
    <section
      aria-label="Cuero del lote"
      className="space-y-4 rounded-card border border-line px-4 py-4"
    >
      <div className="space-y-1">
        <h2 className="text-xs uppercase tracking-caps-sm text-muted">Cuero</h2>
        <p className="text-sm text-muted">
          Es solo informativo: no impide crear el lote. Cada producto se calcula
          por separado; si dos usan el mismo cuero, sumá los m².
        </p>
      </div>
      <ul className="space-y-4">
        {filas.map((fila) => (
          <li key={fila.id}>
            <CueroDeFila fila={fila} nombres={nombres} />
          </li>
        ))}
      </ul>
    </section>
  );
}

function CueroDeFila({
  fila,
  nombres,
}: {
  fila: Fila;
  nombres: Record<string, string>;
}) {
  const cantidad = cantidadValida(fila.cantidad);
  const [state, setState] = useState<FilaState>({ status: "idle" });
  // Bumped by "Volver a calcular" (for example after loading new leather).
  const [intento, setIntento] = useState(0);

  // biome-ignore lint/correctness/useExhaustiveDependencies: `intento` only re-runs the query.
  useEffect(() => {
    if (cantidad === null) {
      setState({ status: "idle" });
      return;
    }
    let current = true;
    setState({ status: "loading" });
    const timer = setTimeout(() => {
      consultarAlcanzaCuero(fila.producto, cantidad)
        .then((result) => {
          if (current) setState(result);
        })
        .catch(() => {
          if (current) {
            setState({
              status: "error",
              message: "No pudimos consultar el cuero. Probá de nuevo.",
            });
          }
        });
    }, DEBOUNCE_MS);
    return () => {
      current = false;
      clearTimeout(timer);
    };
  }, [fila.producto, cantidad, intento]);

  return (
    <div className="space-y-3">
      <p className="text-base font-bold">
        {fila.nombre}
        <span className="block text-xs font-normal text-muted">
          {fila.producto}
        </span>
      </p>
      <div aria-live="polite">
        {state.status === "idle" ? (
          <p className="text-sm text-muted">
            Indicá la cantidad para ver si alcanza el cuero.
          </p>
        ) : state.status === "loading" ? (
          <p className="text-sm text-muted">Calculando el cuero…</p>
        ) : state.status === "error" ? (
          <Notice title="No pudimos revisar el cuero.">
            {state.message} Podés crear el lote igual.
          </Notice>
        ) : (
          <AlcanzaResumen
            resultado={state.resultado}
            nombres={nombres}
            enPestanaNueva
          />
        )}
      </div>
      {state.status === "ok" || state.status === "error" ? (
        <button
          type="button"
          onClick={() => setIntento((actual) => actual + 1)}
          className="inline-flex min-h-11 items-center rounded-card border border-line px-3 py-2 text-sm text-muted hover:border-ink hover:text-ink"
        >
          Volver a calcular
        </button>
      ) : null}
    </div>
  );
}
