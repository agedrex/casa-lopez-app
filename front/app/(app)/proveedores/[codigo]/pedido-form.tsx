"use client";

import { useState } from "react";
import {
  Field,
  FormFeedback,
  inputClass,
  PrimaryButton,
} from "@/components/form";
import { formatQuantity } from "@/lib/format";
import { resumenDePieles } from "@/lib/pedidos";
import type { MaterialOption } from "@/lib/proveedores";
import { useActionForm } from "@/lib/use-action-form";
import { crearMaterialRapido, createPedidoDeProveedor } from "./pedido-actions";

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
  // Materials created from this form are added to the list without reloading the page.
  const [extra, setExtra] = useState<MaterialOption[]>([]);
  const all = [
    ...materials,
    ...extra.filter((e) => !materials.some((m) => m.codigo === e.codigo)),
  ];
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
              <LineFields id={id} index={index} materials={all} />
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
        className="min-h-11 text-sm underline decoration-gold underline-offset-4"
      >
        + Agregar otro material
      </button>
      <MaterialNuevo
        onCreated={(option) => setExtra((current) => [...current, option])}
      />
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
  const [tamanos, setTamanos] = useState("");
  const selected = materials.find((m) => m.codigo === material);
  const unidad = selected?.unidad ?? "";
  const esCuero = selected?.esCuero ?? false;
  const groups = [...new Set(materials.map((m) => m.group))];

  const name = (field: string) => `lineas.${index}.${field}`;
  const fieldId = (field: string) => `pedido-${id}-${field}`;

  const materialField = (
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
  );
  const monedaField = (
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
  );
  const ivaField = (
    <label className="flex min-h-12 items-center gap-2 text-sm sm:min-h-0 sm:pb-2">
      <input type="checkbox" name={name("iva")} className="size-5" />
      Con IVA
    </label>
  );

  if (esCuero) {
    // Leather arrives in skins of different sizes: one text with every size, one price per m².
    return (
      <div className="space-y-2">
        <div className="grid gap-3 sm:grid-cols-[2fr_2fr_1fr_1fr_auto_auto]">
          {materialField}
          <Field id={fieldId("tamanos")} label="Tamaño de cada piel en m²">
            <input
              id={fieldId("tamanos")}
              name={name("tamanos")}
              value={tamanos}
              onChange={(event) => setTamanos(event.target.value)}
              autoComplete="off"
              required
              placeholder="1, 2, 2, 5"
              aria-describedby={fieldId("tamanos-ayuda")}
              className={inputClass}
            />
          </Field>
          <Field id={fieldId("precio_por_m2")} label="Precio por m²">
            <input
              id={fieldId("precio_por_m2")}
              name={name("precio_por_m2")}
              inputMode="decimal"
              autoComplete="off"
              required
              className={inputClass}
            />
          </Field>
          <Field id={fieldId("color")} label="Color (opcional)">
            <input
              id={fieldId("color")}
              name={name("color")}
              autoComplete="off"
              className={inputClass}
            />
          </Field>
          {monedaField}
          {ivaField}
        </div>
        <p id={fieldId("tamanos-ayuda")} className="text-sm text-muted">
          Escribí el tamaño de cada piel separado por comas o espacios (1, 2, 2,
          5). Para varias iguales usá 3x2 (tres pieles de 2 m²). Usá punto para
          los decimales: 2.5.
        </p>
        <PielesResumen text={tamanos} />
      </div>
    );
  }

  return (
    <div className="grid gap-3 sm:grid-cols-[2fr_1fr_1fr_auto_auto]">
      {materialField}
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
      {monedaField}
      {ivaField}
    </div>
  );
}

/** Live hint from the sizes text only (count and m²); the API creates the pieces and prices them. */
function PielesResumen({ text }: { text: string }) {
  if (!text.trim()) return null;
  const summary = resumenDePieles(text);
  if (!summary.ok) {
    return <p className="text-sm text-muted">Revisá: {summary.message}</p>;
  }
  const unit = summary.pieles === 1 ? "piel" : "pieles";
  return (
    <p className="text-sm font-medium" aria-live="polite">
      {summary.pieles} {unit} · {formatQuantity(summary.m2)} m² en total
    </p>
  );
}

const ETAPAS_NUEVAS = [
  { value: "CUERO", label: "Cuero" },
  { value: "FORRO", label: "Forro" },
  { value: "FLEX", label: "Flex" },
  { value: "GOMA_EVA", label: "Goma EVA" },
  { value: "HERRAJES", label: "Herrajes" },
  { value: "HILO_CEMENTO", label: "Hilo y cemento" },
];

/** "¿No está el cuero o el material?": creates it (no price) and makes it available in every row of the order. */
function MaterialNuevo({
  onCreated,
}: {
  onCreated: (option: MaterialOption) => void;
}) {
  const [open, setOpen] = useState(false);
  const [nombre, setNombre] = useState("");
  const [etapa, setEtapa] = useState("CUERO");
  const [message, setMessage] = useState("");
  const [pending, setPending] = useState(false);

  if (!open) {
    return (
      <button
        type="button"
        onClick={() => setOpen(true)}
        className="block min-h-11 text-sm underline decoration-gold underline-offset-4"
      >
        ¿No está el cuero o el material? Crearlo
      </button>
    );
  }
  return (
    <div className="space-y-3 rounded-card border border-line p-4">
      <p className="text-sm font-bold">Material nuevo</p>
      <div className="grid gap-3 sm:grid-cols-2">
        <Field id="material-nuevo-nombre" label="Nombre">
          <input
            id="material-nuevo-nombre"
            value={nombre}
            onChange={(event) => setNombre(event.target.value)}
            maxLength={200}
            autoComplete="off"
            className={inputClass}
          />
        </Field>
        <Field id="material-nuevo-etapa" label="Tipo">
          <select
            id="material-nuevo-etapa"
            value={etapa}
            onChange={(event) => setEtapa(event.target.value)}
            className={inputClass}
          >
            {ETAPAS_NUEVAS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </Field>
      </div>
      {message ? (
        <p role="alert" className="text-sm text-bordeaux">
          {message}
        </p>
      ) : null}
      <div className="flex gap-3">
        <button
          type="button"
          disabled={pending}
          onClick={async () => {
            setPending(true);
            setMessage("");
            const result = await crearMaterialRapido(nombre, etapa);
            setPending(false);
            if (!result.ok) return setMessage(result.message);
            onCreated(result.option);
            setNombre("");
            setOpen(false);
          }}
          className="min-h-11 rounded-card bg-ink px-4 text-sm text-white disabled:opacity-60"
        >
          {pending ? "Creando…" : "Crear material"}
        </button>
        <button
          type="button"
          onClick={() => setOpen(false)}
          className="min-h-11 px-2 text-sm text-muted underline"
        >
          Cancelar
        </button>
      </div>
    </div>
  );
}
