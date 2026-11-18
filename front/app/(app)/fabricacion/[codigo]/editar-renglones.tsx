"use client";

import { useState } from "react";
import { FormFeedback } from "@/components/form";
import { plainQuantity } from "@/lib/lote-editar";
import type { RenglonQuitado } from "@/lib/types";
import { useActionForm } from "@/lib/use-action-form";
import { changeCantidad, removeItem } from "./editar-actions";

// Every control is at least 44px tall (min-h-11) at every width: the admin edits lots from the phone.
const controlClass =
  "min-h-11 rounded-card border px-4 text-sm uppercase tracking-caps-sm disabled:opacity-60";

export function RenglonEditor({
  codigo,
  item,
  producto,
  cantidad,
}: {
  codigo: string;
  item: string;
  producto: string;
  cantidad: string;
}) {
  const cambiar = useActionForm(changeCantidad.bind(null, codigo, item));
  const quitar = useActionForm(removeItem.bind(null, codigo, item));
  const [confirmando, setConfirmando] = useState(false);
  const inputId = `cantidad-${item}`;
  return (
    <li className="space-y-3 py-4 first:pt-0 last:pb-0">
      <p className="break-words text-base font-bold">{producto}</p>
      <form
        key={cambiar.formKey}
        onSubmit={cambiar.onSubmit}
        aria-label={`Cambiar la cantidad de ${producto}`}
        className="flex flex-wrap items-end gap-3"
      >
        <div>
          <label
            htmlFor={inputId}
            className="mb-1.5 block text-sm uppercase tracking-caps-sm text-muted"
          >
            Cantidad
          </label>
          <input
            id={inputId}
            name="cantidad"
            type="text"
            inputMode="decimal"
            required
            defaultValue={plainQuantity(cantidad)}
            className="min-h-11 w-32 rounded-card border border-line bg-surface px-3 py-2 text-base outline-none focus:border-gold disabled:opacity-60"
          />
        </div>
        <button
          type="submit"
          disabled={cambiar.pending}
          className={`${controlClass} border-ink hover:bg-ink hover:text-white`}
        >
          {cambiar.pending ? "Guardando…" : "Guardar cantidad"}
        </button>
        {confirmando ? null : (
          <button
            type="button"
            onClick={() => setConfirmando(true)}
            className={`${controlClass} border-bordeaux/60 text-bordeaux hover:bg-bordeaux hover:text-white`}
          >
            Quitar
          </button>
        )}
      </form>
      <FormFeedback state={cambiar.state} />
      {confirmando ? (
        <form
          key={quitar.formKey}
          onSubmit={quitar.onSubmit}
          role="alertdialog"
          aria-label={`Confirmar quitar ${producto}`}
          className="space-y-3 rounded-card border border-bordeaux/40 bg-bordeaux/5 p-4"
        >
          <p className="text-sm">
            ¿Quitar este producto del lote? El renglón queda guardado: no se
            borra.
          </p>
          <div className="flex flex-wrap gap-3">
            <button
              type="submit"
              disabled={quitar.pending}
              className={`${controlClass} border-bordeaux bg-bordeaux text-white hover:opacity-90`}
            >
              {quitar.pending ? "Quitando…" : "Sí, quitar"}
            </button>
            <button
              type="button"
              onClick={() => setConfirmando(false)}
              disabled={quitar.pending}
              className={`${controlClass} border-line hover:bg-paper-mid`}
            >
              Cancelar
            </button>
          </div>
          <FormFeedback state={quitar.state} />
        </form>
      ) : null}
    </li>
  );
}

/** The lines taken out of the lot, kept for the record: what each one had and who removed it (its log). */
export function RenglonesQuitados({
  quitados,
}: {
  quitados: RenglonQuitado[];
}) {
  if (quitados.length === 0) return null;
  return (
    <details className="mt-4 rounded-card border border-line bg-surface">
      <summary className="flex min-h-11 cursor-pointer items-center px-4 text-sm">
        Productos quitados de este lote ({quitados.length})
      </summary>
      <ul className="divide-y divide-line/70 px-4 pb-3">
        {quitados.map((quitado) => (
          <li key={quitado.codigo} className="py-3 text-sm">
            <p className="break-words font-bold">
              {quitado.producto} · {quitado.producto_nombre}
            </p>
            <p className="whitespace-pre-line break-words text-xs text-muted">
              {quitado.nota}
            </p>
          </li>
        ))}
      </ul>
    </details>
  );
}
