"use client";

import { Field, inputClass } from "@/components/form";

export type ProductoOption = { codigo: string; label: string };
export type Fila = { id: number; producto: string; cantidad: string };

/**
 * Visible rows of a new lot: product and quantity only. The values live in the parent so the
 * comparison panel can read them. The fields keep a shared name per column (`producto`, `cantidad`)
 * and `PreciosPorFila` renders `pagado` / `cotizado` once per row, so the server action reads
 * parallel lists of the same length.
 */
export function FilasDeProductos({
  productos,
  filas,
  onChange,
  onAdd,
  onRemove,
}: {
  productos: ProductoOption[];
  filas: Fila[];
  onChange: (id: number, campo: "producto" | "cantidad", valor: string) => void;
  onAdd: () => void;
  onRemove: (id: number) => void;
}) {
  return (
    <fieldset className="space-y-4">
      <legend className="mb-2 text-xs uppercase tracking-caps-sm text-muted">
        Productos del lote
      </legend>
      <datalist id="lote-productos">
        {productos.map((producto) => (
          <option key={producto.codigo} value={producto.codigo}>
            {producto.label}
          </option>
        ))}
      </datalist>
      <ul className="space-y-4">
        {filas.map((fila, index) => (
          <li
            key={fila.id}
            className="grid items-end gap-4 sm:grid-cols-[2fr_1fr_auto]"
          >
            <Field
              id={`lote-producto-${fila.id}`}
              label={`Producto ${index + 1}`}
            >
              <input
                id={`lote-producto-${fila.id}`}
                name="producto"
                list="lote-productos"
                autoComplete="off"
                placeholder="PRD-0001"
                value={fila.producto}
                onChange={(event) =>
                  onChange(fila.id, "producto", event.target.value)
                }
                className={inputClass}
              />
            </Field>
            <Field id={`lote-cantidad-${fila.id}`} label="Cantidad">
              <input
                id={`lote-cantidad-${fila.id}`}
                name="cantidad"
                inputMode="decimal"
                autoComplete="off"
                placeholder="10"
                value={fila.cantidad}
                onChange={(event) =>
                  onChange(fila.id, "cantidad", event.target.value)
                }
                className={inputClass}
              />
            </Field>
            <button
              type="button"
              onClick={() => onRemove(fila.id)}
              disabled={filas.length <= 1}
              aria-label={`Quitar el producto ${index + 1}`}
              className="inline-flex min-h-11 items-center sm:min-h-0 rounded-card border border-line px-3 py-2 text-sm text-muted hover:border-ink hover:text-ink disabled:opacity-40"
            >
              Quitar
            </button>
          </li>
        ))}
      </ul>
      <button
        type="button"
        onClick={onAdd}
        className="inline-flex min-h-11 items-center justify-center sm:min-h-0 rounded-card border border-ink px-4 py-2 text-sm uppercase tracking-caps-sm hover:bg-ink hover:text-white"
      >
        Agregar otro producto
      </button>
    </fieldset>
  );
}

/** The optional prices of each row, kept apart from the main rows (inside "Más opciones"). */
export function PreciosPorFila({ filas }: { filas: Fila[] }) {
  return (
    <ul className="space-y-4">
      {filas.map((fila, index) => (
        <li key={fila.id} className="grid gap-4 sm:grid-cols-2">
          <Field
            id={`lote-cotizado-${fila.id}`}
            label={`Producto ${index + 1}: precio cotizado por unidad`}
          >
            <input
              id={`lote-cotizado-${fila.id}`}
              name="cotizado"
              inputMode="decimal"
              autoComplete="off"
              placeholder="Lo que pidió el taller"
              className={inputClass}
            />
          </Field>
          <Field
            id={`lote-pagado-${fila.id}`}
            label={`Producto ${index + 1}: precio pagado por unidad`}
          >
            <input
              id={`lote-pagado-${fila.id}`}
              name="pagado"
              inputMode="decimal"
              autoComplete="off"
              placeholder="Se carga al retirar"
              className={inputClass}
            />
          </Field>
        </li>
      ))}
    </ul>
  );
}
