"use client";

import {
  Field,
  FormFeedback,
  inputClass,
  PrimaryButton,
  SecondaryButton,
} from "@/components/form";
import { PERSON_LINKS, PERSON_ROLES } from "@/lib/people";
import { useActionForm } from "@/lib/use-action-form";
import { createPersona, setPersonaActiva } from "./actions";

export function PersonaForm() {
  const { state, pending, formKey, onSubmit } = useActionForm(createPersona);
  return (
    <form key={formKey} onSubmit={onSubmit} className="space-y-5">
      <div className="grid gap-5 sm:grid-cols-3">
        <Field id="persona-nombre" label="Nombre">
          <input
            id="persona-nombre"
            name="nombre"
            required
            maxLength={120}
            autoComplete="off"
            className={inputClass}
          />
        </Field>
        <Field id="persona-rol" label="Rol">
          <select
            id="persona-rol"
            name="rol"
            required
            defaultValue=""
            className={inputClass}
          >
            <option value="" disabled>
              Elegir…
            </option>
            {PERSON_ROLES.map((item) => (
              <option key={item.value} value={item.value}>
                {item.label}
              </option>
            ))}
          </select>
        </Field>
        <Field id="persona-vinculo" label="Vínculo">
          <select
            id="persona-vinculo"
            name="vinculo"
            required
            defaultValue=""
            className={inputClass}
          >
            <option value="" disabled>
              Elegir…
            </option>
            {PERSON_LINKS.map((item) => (
              <option key={item.value} value={item.value}>
                {item.label}
              </option>
            ))}
          </select>
        </Field>
      </div>
      <Field id="persona-nota" label="Nota (opcional)">
        <input
          id="persona-nota"
          name="nota"
          autoComplete="off"
          className={inputClass}
        />
      </Field>
      <FormFeedback state={state} />
      <PrimaryButton pending={pending}>
        {pending ? "Cargando…" : "Cargar persona"}
      </PrimaryButton>
    </form>
  );
}

export function PersonaActivaForm({
  codigo,
  nombre,
  activo,
}: {
  codigo: string;
  nombre: string;
  activo: boolean;
}) {
  const { state, pending, onSubmit } = useActionForm(
    setPersonaActiva.bind(null, codigo, !activo),
  );
  return (
    <form onSubmit={onSubmit} className="space-y-2">
      <FormFeedback state={state} />
      <SecondaryButton pending={pending}>
        {pending ? "Guardando…" : activo ? "Desactivar" : "Activar"}
        <span className="sr-only"> a {nombre}</span>
      </SecondaryButton>
    </form>
  );
}
