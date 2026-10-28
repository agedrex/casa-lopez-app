"use client";

import { useRef, useState } from "react";
import { Field, inputClass } from "@/components/form";

export type ProductoOption = { codigo: string; label: string };

/**
 * Dynamic list of products for a lot. The fields are plain uncontrolled inputs sharing a name per
 * column (`producto`, `cantidad`, `cotizado`): the server action reads them as parallel lists.
 */
export function ProductRows({
  productos,
  idPrefix,
  min = 1,
  fixedRows = false,
}: {
  productos: ProductoOption[];
  idPrefix: string;
  min?: number;
  fixedRows?: boolean;
}) {
  const next = useRef(min);
  const [rows, setRows] = useState<number[]>(() =>
    Array.from({ length: min }, (_, i) => i),
  );
  const listId = `${idPrefix}-productos`;

  return (
    <fieldset className="space-y-4">
      <legend className="mb-2 text-xs uppercase tracking-caps-sm text-muted">
        Productos del lote
      </legend>
      <datalist id={listId}>
        {productos.map((producto) => (
          <option key={producto.codigo} value={producto.codigo}>
            {producto.label}
          </option>
        ))}
      </datalist>
      <ul className="space-y-4">
        {rows.map((row, index) => (
          <li
            key={row}
            className="grid items-end gap-4 sm:grid-cols-[2fr_1fr_1fr_auto]"
          >
            <Field
              id={`${idPrefix}-producto-${row}`}
              label={`Producto ${index + 1}`}
            >
              <input
                id={`${idPrefix}-producto-${row}`}
                name="producto"
                list={listId}
                autoComplete="off"
                placeholder="PRD-0001"
                className={inputClass}
              />
            </Field>
            <Field id={`${idPrefix}-cantidad-${row}`} label="Cantidad">
              <input
                id={`${idPrefix}-cantidad-${row}`}
                name="cantidad"
                inputMode="decimal"
                autoComplete="off"
                placeholder="10"
                className={inputClass}
              />
            </Field>
            <Field
              id={`${idPrefix}-cotizado-${row}`}
              label="Precio cotizado por unidad"
            >
              <input
                id={`${idPrefix}-cotizado-${row}`}
                name="cotizado"
                inputMode="decimal"
                autoComplete="off"
                placeholder="Opcional"
                className={inputClass}
              />
            </Field>
            {fixedRows ? null : (
              <button
                type="button"
                onClick={() => setRows(rows.filter((r) => r !== row))}
                disabled={rows.length <= min}
                aria-label={`Quitar el producto ${index + 1}`}
                className="inline-flex min-h-11 items-center sm:min-h-0 rounded-card border border-line px-3 py-2 text-sm text-muted hover:border-ink hover:text-ink disabled:opacity-40"
              >
                Quitar
              </button>
            )}
          </li>
        ))}
      </ul>
      {fixedRows ? null : (
        <button
          type="button"
          onClick={() => {
            setRows([...rows, next.current]);
            next.current += 1;
          }}
          className="inline-flex min-h-11 items-center justify-center sm:min-h-0 rounded-card border border-ink px-4 py-2 text-sm uppercase tracking-caps-sm hover:bg-ink hover:text-white"
        >
          Agregar otro producto
        </button>
      )}
    </fieldset>
  );
}
