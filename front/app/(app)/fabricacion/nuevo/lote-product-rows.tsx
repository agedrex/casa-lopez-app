"use client";

import { Field, inputClass } from "@/components/form";
import type { FilaDeLote } from "@/lib/lote-buscador";

export type Fila = FilaDeLote;

/**
 * Products picked for a new lot, one row each, with its quantity. The values live in the parent so the
 * comparison panel can read them. The fields keep a shared name per column (`producto`, `cantidad`), so
 * the server action reads parallel lists of the same length. The product code travels in a hidden field:
 * it is picked in the finder, not typed.
 */
export function FilasDeProductos({
  filas,
  onChange,
  onRemove,
}: {
  filas: Fila[];
  onChange: (id: number, cantidad: string) => void;
  onRemove: (id: number) => void;
}) {
  if (filas.length === 0) {
    return (
      <p className="rounded-card border border-dashed border-line px-4 py-3 text-sm text-muted">
        Todavía no agregaste productos: buscalos arriba.
      </p>
    );
  }
  return (
    <ul className="space-y-4">
      {filas.map((fila, index) => (
        <li
          key={fila.id}
          className="grid items-end gap-4 sm:grid-cols-[2fr_1fr_auto]"
        >
          <div className="text-sm">
            <input type="hidden" name="producto" value={fila.producto} />
            {fila.nombre}
            <span className="block text-xs text-muted">{fila.producto}</span>
          </div>
          <Field
            id={`lote-cantidad-${fila.id}`}
            label={`Cantidad (${fila.producto})`}
          >
            <input
              id={`lote-cantidad-${fila.id}`}
              name="cantidad"
              inputMode="decimal"
              autoComplete="off"
              placeholder="10"
              value={fila.cantidad}
              onChange={(event) => onChange(fila.id, event.target.value)}
              className={inputClass}
            />
          </Field>
          <button
            type="button"
            onClick={() => onRemove(fila.id)}
            aria-label={`Quitar ${fila.nombre} (producto ${index + 1})`}
            className="inline-flex min-h-11 items-center sm:min-h-0 rounded-card border border-line px-3 py-2 text-sm text-muted hover:border-ink hover:text-ink"
          >
            Quitar
          </button>
        </li>
      ))}
    </ul>
  );
}
