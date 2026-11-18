"use client";

import { useEffect, useState } from "react";
import { Notice } from "@/components/ui";
import { parseDecimalInput } from "@/lib/format";
import { resumenDeCuero, type TarjetaDeCuero } from "@/lib/lote-cuero";
import type { AlcanzaLote } from "@/lib/types";
import { consultarAlcanzaLote } from "../actions";
import type { Fila } from "./lote-product-rows";

/** Wait this long after the last keystroke before asking the API. */
export const DEBOUNCE_MS = 500;

type PanelState =
  | { status: "idle" }
  | { status: "loading" }
  | { status: "ok"; resultado: AlcanzaLote }
  | { status: "error"; message: string };

/** The quantity as the API wants it, or null while it is empty, not a number or zero. */
function cantidadValida(texto: string): string | null {
  const cantidad = parseDecimalInput(texto);
  return cantidad !== null && /[1-9]/.test(cantidad) ? cantidad : null;
}

/**
 * Leather availability of the lot being built, calculated by the API for the whole lot at once: the same answer the
 * detail of the lot gives once it is created (stock minus what the other open lots reserve, rows that share a leather
 * added up). It is informative only: whatever it says (or if it fails) the lot can still be created.
 */
export function CueroPanel({ filas }: { filas: Fila[] }) {
  const lineas = filas.flatMap((fila) => {
    const cantidad = cantidadValida(fila.cantidad);
    return cantidad === null ? [] : [{ producto: fila.producto, cantidad }];
  });
  // A string key: the effect re-runs only when a product or a quantity really changes.
  const clave = JSON.stringify(lineas);
  const [state, setState] = useState<PanelState>({ status: "idle" });
  // Bumped by "Volver a calcular" (for example after loading new leather).
  const [intento, setIntento] = useState(0);

  // biome-ignore lint/correctness/useExhaustiveDependencies: `clave` stands for `lineas`; `intento` only re-runs the query.
  useEffect(() => {
    if (lineas.length === 0) {
      setState({ status: "idle" });
      return;
    }
    let current = true;
    setState({ status: "loading" });
    const timer = setTimeout(() => {
      consultarAlcanzaLote(lineas)
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
  }, [clave, intento]);

  if (filas.length === 0) return null;
  return (
    <section
      aria-label="Cuero del lote"
      className="space-y-4 rounded-card border border-line px-4 py-4"
    >
      <div className="space-y-1">
        <h2 className="text-xs uppercase tracking-caps-sm text-muted">Cuero</h2>
        <p className="text-sm text-muted">
          Solo informativo: no impide crear el lote. Descuenta el cuero que ya
          tienen reservado los otros lotes abiertos, igual que lo va a mostrar
          el lote una vez creado.
        </p>
      </div>
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
          <ResumenDeCuero resultado={state.resultado} />
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
    </section>
  );
}

function ResumenDeCuero({ resultado }: { resultado: AlcanzaLote }) {
  const resumen = resumenDeCuero(resultado);
  return (
    <div className="space-y-3">
      <p
        className={`text-sm ${resumen.faltan > 0 ? "font-bold text-bordeaux" : "text-muted"}`}
        role={resumen.faltan > 0 ? "alert" : undefined}
      >
        {resumen.titular}
      </p>
      <ul className="space-y-3">
        {resumen.tarjetas.map((tarjeta) => (
          <li key={tarjeta.key}>
            <Tarjeta tarjeta={tarjeta} />
          </li>
        ))}
      </ul>
      {resumen.sinConsumo.length > 0 ? (
        <Notice title="Sin consumo de cuero (no entran en el cálculo)">
          {resumen.sinConsumo.map((p) => p.producto).join(", ")}
        </Notice>
      ) : null}
    </div>
  );
}

function Tarjeta({ tarjeta }: { tarjeta: TarjetaDeCuero }) {
  return (
    <div className="space-y-2 rounded-card border border-line px-4 py-3">
      <p className="text-base font-bold">{tarjeta.titulo}</p>
      <p
        className={`text-sm ${tarjeta.estado === "FALTA" ? "font-bold text-bordeaux" : ""}`}
      >
        {tarjeta.mensaje}
      </p>
      <dl className="grid grid-cols-[1fr_auto] gap-x-4 gap-y-1 text-sm">
        {tarjeta.cifras.map((cifra) => (
          <div key={cifra.label} className="contents">
            <dt className="text-muted">{cifra.label}</dt>
            <dd className="tabular-nums">{cifra.value}</dd>
          </div>
        ))}
      </dl>
      {tarjeta.aviso ? (
        <p className="text-sm text-muted">{tarjeta.aviso}</p>
      ) : null}
      <p className="text-xs text-muted">{tarjeta.productos.join(", ")}</p>
    </div>
  );
}
