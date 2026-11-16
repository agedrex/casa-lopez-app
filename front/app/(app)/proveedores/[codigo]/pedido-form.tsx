"use client";

import { useState } from "react";
import {
  Field,
  FormFeedback,
  inputClass,
  PrimaryButton,
} from "@/components/form";
import type { MaterialOption } from "@/lib/proveedores";
import { useActionForm } from "@/lib/use-action-form";
import { createPedidoDeProveedor } from "./pedido-actions";

/**
 * A short form: the date, an optional remito and one row per material (what arrived, in the unit of the
 * material, and the price of one unit). The API turns each row into a price of that material.
 */
export function PedidoForm({
  codigo,
  materials,
  today,
}: {
  codigo: string;
  materials: MaterialOption[];
  today: string;
}) {
  const { state, pending, formKey, onSubmit } = useActionForm(
    createPedidoDeProveedor.bind(null, codigo),
  );
  return (
    <form key={formKey} onSubmit={onSubmit} className="space-y-4">
      <Fields materials={materials} today={today} />
      <FormFeedback state={state} />
      <PrimaryButton pending={pending}>
        {pending ? "Registrando…" : "Registrar pedido"}
      </PrimaryButton>
    </form>
  );
}

// Lives below the form key so the rows reset with the form after a saved order.
function Fields({
  materials,
  today,
}: {
  materials: MaterialOption[];
  today: string;
}) {
  // Each row has a stable id (its React key); the field names use the position, so they stay 0, 1, 2...
  const [rows, setRows] = useState([0]);
  const [nextId, setNextId] = useState(1);

  return (
    <div className="space-y-4">
      <div className="grid gap-4 sm:grid-cols-2">
        <Field id="pedido-fecha" label="Fecha de recepción">
          <input
            id="pedido-fecha"
            name="fecha_de_recepcion"
            type="date"
            required
            defaultValue={today}
            className={inputClass}
          />
        </Field>
        <Field id="pedido-remito" label="Remito (opcional)">
          <input
            id="pedido-remito"
            name="remito"
            autoComplete="off"
            className={inputClass}
          />
        </Field>
      </div>

      <ol className="space-y-3">
        {rows.map((id, index) => (
          <li key={id} className="flex items-end gap-2">
            <div className="min-w-0 flex-1">
              <LineFields id={id} index={index} materials={materials} />
            </div>
            {rows.length > 1 ? (
              <button
                type="button"
                onClick={() => setRows(rows.filter((row) => row !== id))}
                aria-label={`Quitar el material ${index + 1}`}
                className="min-h-12 px-2 text-sm text-muted underline decoration-gold underline-offset-4 sm:min-h-0 sm:pb-2"
              >
                Quitar
              </button>
            ) : null}
          </li>
        ))}
      </ol>

      <button
        type="button"
        onClick={() => {
          setRows([...rows, nextId]);
          setNextId(nextId + 1);
        }}
        className="text-sm underline decoration-gold underline-offset-4"
      >
        + Agregar otro material
      </button>
    </div>
  );
}

function LineFields({
  id,
  index,
  materials,
}: {
  id: number;
  index: number;
  materials: MaterialOption[];
}) {
  const [material, setMaterial] = useState("");
  const unidad = materials.find((m) => m.codigo === material)?.unidad ?? "";
  const groups = [...new Set(materials.map((m) => m.group))];

  const name = (field: string) => `lineas.${index}.${field}`;
  const fieldId = (field: string) => `pedido-${id}-${field}`;

  return (
    <div className="grid gap-3 sm:grid-cols-[2fr_1fr_1fr_auto_auto]">
      <Field id={fieldId("material")} label="Material">
        <select
          id={fieldId("material")}
          name={name("material")}
          required
          value={material}
          onChange={(event) => setMaterial(event.target.value)}
          className={inputClass}
        >
          <option value="">Elegir…</option>
          {groups.map((group) => (
            <optgroup key={group} label={group}>
              {materials
                .filter((m) => m.group === group)
                .map((m) => (
                  <option key={m.codigo} value={m.codigo}>
                    {m.label}
                  </option>
                ))}
            </optgroup>
          ))}
        </select>
      </Field>
      <Field
        id={fieldId("cantidad")}
        label={unidad ? `Cantidad (${unidad})` : "Cantidad"}
      >
        <input
          id={fieldId("cantidad")}
          name={name("cantidad")}
          inputMode="decimal"
          autoComplete="off"
          required
          className={inputClass}
        />
      </Field>
      <Field
        id={fieldId("precio")}
        label={unidad ? `Precio por ${unidad}` : "Precio por unidad"}
      >
        <input
          id={fieldId("precio")}
          name={name("precio")}
          inputMode="decimal"
          autoComplete="off"
          required
          className={inputClass}
        />
      </Field>
      <Field id={fieldId("moneda")} label="Moneda">
        <select
          id={fieldId("moneda")}
          name={name("moneda")}
          required
          defaultValue="ARS"
          className={inputClass}
        >
          <option value="ARS">ARS</option>
          <option value="USD">USD</option>
        </select>
      </Field>
      <label className="flex min-h-12 items-center gap-2 text-sm sm:min-h-0 sm:pb-2">
        <input type="checkbox" name={name("iva")} className="size-4" />
        Con IVA
      </label>
    </div>
  );
}
