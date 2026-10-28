"use client";

import { useEffect, useRef, useState } from "react";
import {
  Field,
  FormFeedback,
  inputClass,
  PrimaryButton,
} from "@/components/form";
import { Notice } from "@/components/ui";
import { formatPeriod } from "@/lib/format";
import type { VozPropuesta } from "@/lib/types";
import { useActionForm } from "@/lib/use-action-form";
import { fieldLabel, VOZ_ACTION_LABELS } from "@/lib/voz";
import { confirmarVoz } from "./actions";

const CURRENCIES = [
  { value: "ARS", label: "Pesos (ARS)" },
  { value: "USD", label: "Dólares (USD)" },
];
const DOLLAR_TYPES = [
  { value: "VENDEDOR", label: "Vendedor" },
  { value: "COMPRADOR", label: "Comprador" },
];
const PRICE_KINDS = [
  { value: "cotizado", label: "Cotizado (lo que pidió el taller)" },
  { value: "pagado", label: "Pagado (lo que se le pagó)" },
];

/**
 * The proposal as an editable confirmation card: "Entendí esto… ¿Lo cargo?". Resolved fields come filled in, ambiguous ones
 * are radio choices, missing ones are marked. Only the "Confirmar" button calls the write: the same server actions the
 * regular screens use, with this person's session.
 */
export function PropuestaCard({ propuesta }: { propuesta: VozPropuesta }) {
  const { state, pending, formKey, onSubmit } = useActionForm(confirmarVoz);
  const [discarded, setDiscarded] = useState(false);
  const heading = useRef<HTMLHeadingElement>(null);
  useEffect(() => heading.current?.focus(), []);

  const done = state.status === "ok";
  const title = VOZ_ACTION_LABELS[propuesta.accion];

  if (propuesta.accion === "desconocida") {
    return (
      <Notice title={title}>
        <h3 ref={heading} tabIndex={-1} className="sr-only">
          {title}
        </h3>
        {propuesta.avisos.join(" ")} Pruebe con otra frase (hay ejemplos más
        abajo) o cargue el dato desde su pantalla.
      </Notice>
    );
  }
  if (discarded) {
    return (
      <output className="block text-sm text-muted">
        Propuesta descartada. No se cargó nada.
      </output>
    );
  }

  const missing = (field: string) => propuesta.faltantes.includes(field);
  const fields = {
    cargar_precio: (
      <>
        <Choice
          propuesta={propuesta}
          campo="material"
          name="material"
          placeholder="MAT-CU01"
        />
        <Choice
          propuesta={propuesta}
          campo="color"
          name="color"
          placeholder="Opcional"
          optional
        />
        <TextInput
          id="voz-precio"
          name="precio"
          label="Precio"
          value={propuesta.campos_resueltos.precio?.valor}
          missing={missing("precio")}
          placeholder="26"
        />
        <Select
          id="voz-moneda"
          name="moneda"
          label="Moneda"
          options={CURRENCIES}
          value={propuesta.campos_resueltos.moneda?.valor}
          missing={missing("moneda")}
        />
        <TextInput
          id="voz-vigente"
          name="vigente_desde"
          label="Rige desde"
          type="date"
          value={propuesta.campos_resueltos.vigente_desde?.valor}
          missing={missing("vigente_desde")}
        />
        <Fixed
          label="Unidad del precio"
          value={propuesta.campos_resueltos.unidad_del_precio?.valor}
          note="La define el material (la misma unidad de consumo)."
        />
      </>
    ),
    cargar_dolar: (
      <>
        <TextInput
          id="voz-dolar"
          name="valor"
          label="Pesos por dólar"
          value={propuesta.campos_resueltos.ars_por_usd?.valor}
          missing={missing("ars_por_usd")}
          placeholder="1545"
        />
        <Select
          id="voz-tipo"
          name="tipo"
          label="Tipo"
          options={DOLLAR_TYPES}
          value={propuesta.campos_resueltos.tipo?.valor}
          missing={missing("tipo")}
        />
        <TextInput
          id="voz-fecha"
          name="fecha"
          label="Fecha"
          type="date"
          value={propuesta.campos_resueltos.fecha?.valor}
          missing={missing("fecha")}
        />
      </>
    ),
    agregar_extra: (
      <>
        <Choice
          propuesta={propuesta}
          campo="producto"
          name="producto"
          placeholder="PRD-0001"
        />
        <Choice
          propuesta={propuesta}
          campo="material"
          name="material"
          placeholder="MAT-FL01"
        />
        <Choice
          propuesta={propuesta}
          campo="color"
          name="color"
          placeholder="Opcional"
          optional
        />
        <TextInput
          id="voz-consumo"
          name="consumo"
          label="Consumo por unidad"
          value={propuesta.campos_resueltos.consumo_neto_por_unidad?.valor}
          missing={missing("consumo_neto_por_unidad")}
          placeholder="0,25"
        />
      </>
    ),
    registrar_precio_taller: (
      <>
        <Choice
          propuesta={propuesta}
          campo="lote"
          name="lote"
          placeholder="LOT-0003"
        />
        <Choice
          propuesta={propuesta}
          campo="item"
          name="item"
          placeholder="LIT-0001"
        />
        <Select
          id="voz-precio-de"
          name="precio_de"
          label="Qué precio es"
          options={PRICE_KINDS}
          value={propuesta.campos_resueltos.precio_de?.valor}
          missing={missing("precio_de")}
        />
        <TextInput
          id="voz-precio-taller"
          name="precio"
          label="Precio por unidad (pesos)"
          value={propuesta.campos_resueltos.precio?.valor}
          missing={missing("precio")}
          placeholder="14000"
        />
      </>
    ),
    cargar_monto_gasto: (
      <>
        <Choice
          propuesta={propuesta}
          campo="gasto"
          name="gasto"
          placeholder="GF-0010"
        />
        <Fixed
          label="Período"
          value={
            propuesta.campos_resueltos.periodo
              ? formatPeriod(propuesta.campos_resueltos.periodo.valor)
              : undefined
          }
          note="El monto se carga en el período indicado en la frase o en el vigente."
        />
        <TextInput
          id="voz-monto"
          name="monto"
          label="Monto en pesos"
          value={propuesta.campos_resueltos.monto_ars_del_mes?.valor}
          missing={missing("monto_ars_del_mes")}
          placeholder="180000"
        />
      </>
    ),
  }[propuesta.accion];

  return (
    <section
      aria-labelledby="voz-propuesta-titulo"
      className="rounded-card border border-gold bg-surface p-6 shadow-card"
    >
      <h3
        id="voz-propuesta-titulo"
        ref={heading}
        tabIndex={-1}
        className="text-xl outline-none"
      >
        {title}
      </h3>
      <p className="mt-2">{propuesta.resumen}</p>
      <p className="mt-1 font-bold">¿Lo cargo?</p>

      {propuesta.avisos.length > 0 ? (
        <ul className="mt-3 list-disc space-y-1 pl-5 text-sm text-muted">
          {propuesta.avisos.map((aviso) => (
            <li key={aviso}>{aviso}</li>
          ))}
        </ul>
      ) : null}
      {propuesta.faltantes.length > 0 ? (
        <p className="mt-3 rounded-card border border-bordeaux/30 bg-bordeaux/5 px-4 py-2 text-sm text-bordeaux">
          Faltan o hay que elegir:{" "}
          {propuesta.faltantes.map(fieldLabel).join(", ")}. Complételos para
          poder cargar.
        </p>
      ) : null}

      <form
        key={formKey}
        onSubmit={onSubmit}
        className="mt-5 space-y-5"
        aria-label="Confirmar la carga"
      >
        <input type="hidden" name="accion" value={propuesta.accion} />
        <div className="grid gap-5 sm:grid-cols-2">{fields}</div>
        <FormFeedback state={state} />
        {done ? (
          <p className="text-sm text-muted">
            Listo. Para otra carga, escriba o dicte un pedido nuevo.
          </p>
        ) : (
          <div className="flex flex-wrap gap-3">
            {state.needsConfirm ? (
              <PrimaryButton pending={pending} name="confirmar" value="1">
                {pending ? "Cargando…" : "Cargar igual"}
              </PrimaryButton>
            ) : (
              <PrimaryButton pending={pending}>
                {pending ? "Cargando…" : "Confirmar y cargar"}
              </PrimaryButton>
            )}
            <button
              type="button"
              onClick={() => setDiscarded(true)}
              disabled={pending}
              className="rounded-card border border-ink px-5 py-2.5 text-sm uppercase tracking-caps-sm hover:bg-ink hover:text-white disabled:opacity-60"
            >
              Descartar
            </button>
          </div>
        )}
      </form>
    </section>
  );
}

function missingClass(missing: boolean): string {
  return missing ? `${inputClass} border-bordeaux` : inputClass;
}

function MissingHint({ id, missing }: { id: string; missing: boolean }) {
  return missing ? (
    <p id={id} className="mt-1 text-xs font-bold text-bordeaux">
      Falta completar o elegir este dato.
    </p>
  ) : null;
}

function TextInput({
  id,
  name,
  label,
  value,
  missing,
  type = "text",
  placeholder,
}: {
  id: string;
  name: string;
  label: string;
  value?: string;
  missing: boolean;
  type?: string;
  placeholder?: string;
}) {
  return (
    <div>
      <Field id={id} label={label}>
        <input
          id={id}
          name={name}
          type={type}
          defaultValue={value ?? ""}
          placeholder={placeholder}
          inputMode={type === "text" ? "decimal" : undefined}
          autoComplete="off"
          aria-invalid={missing || undefined}
          aria-describedby={missing ? `${id}-falta` : undefined}
          className={missingClass(missing)}
        />
      </Field>
      <MissingHint id={`${id}-falta`} missing={missing} />
    </div>
  );
}

function Select({
  id,
  name,
  label,
  options,
  value,
  missing,
}: {
  id: string;
  name: string;
  label: string;
  options: { value: string; label: string }[];
  value?: string;
  missing: boolean;
}) {
  return (
    <div>
      <Field id={id} label={label}>
        <select
          id={id}
          name={name}
          defaultValue={value ?? ""}
          aria-invalid={missing || undefined}
          aria-describedby={missing ? `${id}-falta` : undefined}
          className={missingClass(missing)}
        >
          <option value="">Elija una opción</option>
          {options.map((option) => (
            <option key={option.value} value={option.value}>
              {option.label}
            </option>
          ))}
        </select>
      </Field>
      <MissingHint id={`${id}-falta`} missing={missing} />
    </div>
  );
}

function Fixed({
  label,
  value,
  note,
}: {
  label: string;
  value?: string;
  note: string;
}) {
  return (
    <div>
      <p className="mb-1.5 text-xs uppercase tracking-caps-sm text-muted">
        {label}
      </p>
      <p className="rounded-card border border-line bg-paper-mid px-3 py-2 text-sm">
        {value ?? "—"}
      </p>
      <p className="mt-1 text-xs text-muted">{note}</p>
    </div>
  );
}

/**
 * A field that holds a code or a name. Ambiguous: the candidates as radio choices (the person picks one). Otherwise a text
 * input with what was understood (or empty, marked, when nothing matched).
 */
function Choice({
  propuesta,
  campo,
  name,
  placeholder,
  optional = false,
}: {
  propuesta: VozPropuesta;
  campo: string;
  name: string;
  placeholder: string;
  optional?: boolean;
}) {
  const candidates = propuesta.candidatos[campo] ?? [];
  const resolved = propuesta.campos_resueltos[campo];
  const missing = propuesta.faltantes.includes(campo);
  const label = fieldLabel(campo);

  if (candidates.length > 0) {
    return (
      <fieldset
        className="min-w-0 sm:col-span-2"
        aria-describedby={`voz-${name}-falta`}
      >
        <legend className="mb-1.5 text-xs uppercase tracking-caps-sm text-muted">
          {label}
          {optional ? " (opcional)" : ""}: elija una opción
        </legend>
        <ul className="space-y-1.5">
          {candidates.map((candidate) => (
            <li key={candidate.codigo}>
              <label className="flex items-start gap-2 rounded-card border border-line bg-paper-mid px-3 py-2 text-sm">
                <input
                  type="radio"
                  name={name}
                  value={candidate.codigo}
                  className="mt-1"
                />
                <span>
                  {candidate.nombre}
                  {candidate.nombre === candidate.codigo ? null : (
                    <span className="text-muted"> · {candidate.codigo}</span>
                  )}
                </span>
              </label>
            </li>
          ))}
        </ul>
        <MissingHint id={`voz-${name}-falta`} missing={missing} />
      </fieldset>
    );
  }

  const id = `voz-${name}`;
  return (
    <div>
      <Field
        id={id}
        label={`${label}${optional ? " (opcional)" : ""}`}
        hint={resolved?.texto ? `Entendí: ${resolved.texto}` : undefined}
      >
        <input
          id={id}
          name={name}
          defaultValue={resolved?.valor ?? ""}
          placeholder={placeholder}
          autoComplete="off"
          aria-invalid={missing || undefined}
          aria-describedby={
            [resolved?.texto ? `${id}-hint` : "", missing ? `${id}-falta` : ""]
              .filter(Boolean)
              .join(" ") || undefined
          }
          className={missingClass(missing)}
        />
      </Field>
      <MissingHint id={`${id}-falta`} missing={missing} />
    </div>
  );
}
