"use client";

import { useState } from "react";
import {
  Field,
  FormFeedback,
  inputClass,
  PrimaryButton,
} from "@/components/form";
import { formatRate } from "@/lib/format";
import { PRESENTACIONES, unitPricePreview } from "@/lib/pedidos";
import { useActionForm } from "@/lib/use-action-form";
import { createPedidoDeProveedor } from "./pedido-actions";
import type { MaterialOption } from "./precio-form";

const PRESENTACIONES_LIST = "pedido-presentaciones";

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
    <form key={formKey} onSubmit={onSubmit} className="space-y-5">
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
    <div className="space-y-5">
      <div className="grid gap-5 sm:grid-cols-3">
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
        <Field id="pedido-remito" label="Remito o factura (opcional)">
          <input
            id="pedido-remito"
            name="remito"
            autoComplete="off"
            className={inputClass}
          />
        </Field>
        <Field id="pedido-nota" label="Nota (opcional)">
          <input
            id="pedido-nota"
            name="nota"
            autoComplete="off"
            className={inputClass}
          />
        </Field>
      </div>

      <datalist id={PRESENTACIONES_LIST}>
        {PRESENTACIONES.map((item) => (
          <option key={item} value={item} />
        ))}
      </datalist>

      <ol className="space-y-4">
        {rows.map((id, index) => (
          <li key={id} className="rounded-card border border-line p-4">
            <div className="mb-3 flex items-center justify-between gap-3">
              <h4 className="font-bold">Material {index + 1}</h4>
              {rows.length > 1 ? (
                <button
                  type="button"
                  onClick={() => setRows(rows.filter((row) => row !== id))}
                  className="text-sm text-muted underline decoration-gold underline-offset-4"
                >
                  Quitar
                </button>
              ) : null}
            </div>
            <LineFields id={id} index={index} materials={materials} />
          </li>
        ))}
      </ol>

      <button
        type="button"
        onClick={() => {
          setRows([...rows, nextId]);
          setNextId(nextId + 1);
        }}
        className="min-h-12 rounded-card border border-ink px-5 py-2.5 text-sm uppercase tracking-caps-sm hover:bg-ink hover:text-white sm:min-h-0"
      >
        Agregar otro material
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
  const [precio, setPrecio] = useState("");
  const [contenido, setContenido] = useState("");
  const [moneda, setMoneda] = useState("ARS");
  const unidad = materials.find((m) => m.codigo === material)?.unidad ?? "";
  const groups = [...new Set(materials.map((m) => m.group))];
  const unitPrice = unitPricePreview(precio, contenido);

  const name = (field: string) => `lineas.${index}.${field}`;
  const fieldId = (field: string) => `pedido-${id}-${field}`;

  return (
    <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-4">
      <Field
        id={fieldId("material")}
        label="Material"
        hint={unidad ? `Se consume en ${unidad}.` : undefined}
      >
        <select
          id={fieldId("material")}
          name={name("material")}
          required
          value={material}
          onChange={(event) => setMaterial(event.target.value)}
          aria-describedby={unidad ? `${fieldId("material")}-hint` : undefined}
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
      <Field id={fieldId("cantidad")} label="Cantidad de presentaciones">
        <input
          id={fieldId("cantidad")}
          name={name("cantidad_presentaciones")}
          inputMode="decimal"
          autoComplete="off"
          required
          className={inputClass}
        />
      </Field>
      <Field id={fieldId("presentacion")} label="Presentación">
        <input
          id={fieldId("presentacion")}
          name={name("presentacion")}
          list={PRESENTACIONES_LIST}
          autoComplete="off"
          required
          placeholder="CARRETE, CAJA, ROLLO…"
          className={inputClass}
        />
      </Field>
      <Field
        id={fieldId("contenido")}
        label="Contenido por presentación"
        hint={`en ${unidad || "la unidad de consumo del material"}`}
      >
        <input
          id={fieldId("contenido")}
          name={name("contenido_por_presentacion")}
          inputMode="decimal"
          autoComplete="off"
          required
          value={contenido}
          onChange={(event) => setContenido(event.target.value)}
          aria-describedby={`${fieldId("contenido")}-hint`}
          className={inputClass}
        />
      </Field>
      <Field id={fieldId("precio")} label="Precio por presentación">
        <input
          id={fieldId("precio")}
          name={name("precio_por_presentacion")}
          inputMode="decimal"
          autoComplete="off"
          required
          value={precio}
          onChange={(event) => setPrecio(event.target.value)}
          className={inputClass}
        />
      </Field>
      <Field id={fieldId("moneda")} label="Moneda">
        <select
          id={fieldId("moneda")}
          name={name("moneda")}
          required
          value={moneda}
          onChange={(event) => setMoneda(event.target.value)}
          className={inputClass}
        >
          <option value="ARS">ARS</option>
          <option value="USD">USD</option>
        </select>
      </Field>
      <div className="flex items-end pb-2">
        <label className="flex items-center gap-2 text-sm">
          <input
            type="checkbox"
            name={name("iva_incluido")}
            className="size-4"
          />
          Incluye IVA
        </label>
      </div>
      <Field
        id={fieldId("unitario")}
        label={`Precio por ${unidad || "unidad de consumo"}`}
        hint="Solo orientativo: el sistema lo calcula al guardar."
      >
        <input
          id={fieldId("unitario")}
          value={unitPrice ? `${moneda} ${formatRate(unitPrice)}` : "—"}
          readOnly
          aria-describedby={`${fieldId("unitario")}-hint`}
          className={`${inputClass} bg-paper-mid`}
        />
      </Field>
    </div>
  );
}
