"use client";

import {
  Field,
  FormFeedback,
  inputClass,
  PrimaryButton,
} from "@/components/form";
import { stageLabel } from "@/lib/format";
import { useActionForm } from "@/lib/use-action-form";
import { crearMaterialRapido } from "./material-nuevo-actions";

const UNIDADES = [
  { value: "m2", label: "m² (superficie)" },
  { value: "m", label: "metros" },
  { value: "cm", label: "cm" },
  { value: "unidad", label: "unidades" },
  { value: "juego", label: "juegos" },
];

/** The materials are a starting base: a new one is added here, with no price (the order brings it). */
export function MaterialNuevoForm({ etapas }: { etapas: string[] }) {
  const { state, pending, formKey, onSubmit } =
    useActionForm(crearMaterialRapido);
  return (
    <details className="rounded-card border border-line p-4">
      <summary className="cursor-pointer text-sm font-bold">
        ¿No está el material? Agregar uno nuevo
      </summary>
      <form key={formKey} onSubmit={onSubmit} className="mt-4 space-y-4">
        <div className="grid gap-4 sm:grid-cols-3">
          <Field id="mn-nombre" label="Material">
            <input
              id="mn-nombre"
              name="nombre"
              required
              autoComplete="off"
              placeholder="Cierre metálico 30 cm"
              className={inputClass}
            />
          </Field>
          <Field id="mn-etapa" label="Parte del producto">
            <select id="mn-etapa" name="etapa" required className={inputClass}>
              <option value="">Elegir…</option>
              {etapas.map((etapa) => (
                <option key={etapa} value={etapa}>
                  {stageLabel(etapa)}
                </option>
              ))}
            </select>
          </Field>
          <Field id="mn-unidad" label="Se mide en">
            <select
              id="mn-unidad"
              name="unidad_de_consumo"
              required
              className={inputClass}
            >
              <option value="">Elegir…</option>
              {UNIDADES.map((u) => (
                <option key={u.value} value={u.value}>
                  {u.label}
                </option>
              ))}
            </select>
          </Field>
        </div>
        <FormFeedback state={state} />
        <PrimaryButton pending={pending}>
          {pending ? "Agregando…" : "Agregar material"}
        </PrimaryButton>
      </form>
    </details>
  );
}
