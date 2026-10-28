"use client";

import { useState } from "react";
import {
  Field,
  FormFeedback,
  inputClass,
  PrimaryButton,
} from "@/components/form";
import { useActionForm } from "@/lib/use-action-form";
import { createOrden } from "../actions";
import { type ProductoOption, ProductRows } from "../product-rows";

export type Option = { codigo: string; label: string };

export function LoteForm({
  talleres,
  personas,
  productos,
  today,
}: {
  talleres: Option[];
  personas: Option[];
  productos: ProductoOption[];
  today: string;
}) {
  const { state, pending, onSubmit } = useActionForm(createOrden);
  const [donde, setDonde] = useState("EXTERNA");
  // No form key: on success the action redirects to the new lot.
  return (
    <form onSubmit={onSubmit} className="space-y-6">
      <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
        <Field id="lote-donde" label="Dónde se hace">
          <select
            id="lote-donde"
            name="donde_se_hace"
            value={donde}
            onChange={(event) => setDonde(event.target.value)}
            className={inputClass}
          >
            <option value="EXTERNA">En taller</option>
            <option value="INTERNA">En casa</option>
          </select>
        </Field>
        {donde === "EXTERNA" ? (
          <Field
            id="lote-taller"
            label="Taller"
            hint="Sin taller, el lote queda marcado en Calidad de datos."
          >
            <select
              id="lote-taller"
              name="taller"
              defaultValue=""
              aria-describedby="lote-taller-hint"
              className={inputClass}
            >
              <option value="">Elegir…</option>
              {talleres.map((taller) => (
                <option key={taller.codigo} value={taller.codigo}>
                  {taller.label}
                </option>
              ))}
            </select>
          </Field>
        ) : (
          <Field id="lote-persona" label="Persona (opcional)">
            <select
              id="lote-persona"
              name="persona"
              defaultValue=""
              className={inputClass}
            >
              <option value="">Sin indicar</option>
              {personas.map((persona) => (
                <option key={persona.codigo} value={persona.codigo}>
                  {persona.label}
                </option>
              ))}
            </select>
          </Field>
        )}
        <Field id="lote-envio" label="Fecha de envío">
          <input
            id="lote-envio"
            name="fecha_de_envio"
            type="date"
            defaultValue={today}
            className={inputClass}
          />
        </Field>
      </div>
      <ProductRows productos={productos} idPrefix="lote" />
      <Field id="lote-nota" label="Nota (opcional)">
        <input
          id="lote-nota"
          name="nota"
          autoComplete="off"
          className={inputClass}
        />
      </Field>
      <p className="text-sm text-muted">
        El precio cotizado es lo que pidió el taller por unidad. El precio
        pagado se carga después, desde el lote, cuando el taller cobra.
      </p>
      <FormFeedback state={state} />
      <PrimaryButton pending={pending}>
        {pending ? "Creando…" : "Crear lote"}
      </PrimaryButton>
    </form>
  );
}
