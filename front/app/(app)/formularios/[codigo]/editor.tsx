"use client";

import {
  FormFeedback,
  PrimaryButton,
  SecondaryButton,
} from "@/components/form";
import { FormularioConsumos } from "@/components/formulario-consumos";
import type { FormularioAcciones } from "@/lib/formulario";
import type { Formulario } from "@/lib/types";
import { useActionForm } from "@/lib/use-action-form";
import { trabajarFormulario } from "../actions";
import { PrintButton } from "./print-button";

/**
 * The sheet in edit mode with the buttons the current role may use in the current state. Every button submits the
 * same form with its `accion`; the server action saves the typed rows first when they changed. "Guardar" comes
 * first so that Enter inside a cell saves instead of moving the form on.
 */
export function FormularioEditor({
  formulario,
  acciones,
}: {
  formulario: Formulario;
  acciones: FormularioAcciones;
}) {
  const { state, pending, onSubmit } = useActionForm(
    trabajarFormulario.bind(null, formulario.codigo),
  );
  return (
    <form onSubmit={onSubmit} className="space-y-6">
      <FormularioConsumos
        formulario={formulario}
        mode="edit"
        articuloEditable={acciones.editarArticulo}
      />
      <FormFeedback state={state} />
      <div className="flex flex-col gap-3 sm:flex-row sm:flex-wrap print:hidden">
        <SecondaryButton pending={pending} name="accion" value="guardar">
          Guardar
        </SecondaryButton>
        {acciones.enviar ? (
          <PrimaryButton pending={pending} name="accion" value="enviar">
            {formulario.estado === "ENVIADO"
              ? "Reenviar al taller"
              : "Enviar al taller"}
          </PrimaryButton>
        ) : null}
        {acciones.completar ? (
          <PrimaryButton pending={pending} name="accion" value="completar">
            Completar
          </PrimaryButton>
        ) : null}
        {acciones.validar ? (
          <PrimaryButton pending={pending} name="accion" value="validar">
            Validar
          </PrimaryButton>
        ) : null}
        <PrintButton />
      </div>
      {acciones.devolver ? (
        <details className="rounded-card border border-line p-4 print:hidden">
          <summary className="cursor-pointer text-sm uppercase tracking-caps-sm text-muted">
            Devolver con comentario
          </summary>
          <div className="mt-4 space-y-4">
            <label
              htmlFor="formulario-comentario"
              className="block text-sm uppercase tracking-caps-sm text-muted sm:text-xs"
            >
              Qué tiene que corregir el taller
            </label>
            <textarea
              id="formulario-comentario"
              name="comentario"
              rows={3}
              maxLength={2000}
              className="w-full rounded-card border border-line bg-surface px-3 py-2 text-base outline-none focus:border-gold sm:text-sm"
            />
            <SecondaryButton pending={pending} name="accion" value="devolver">
              Devolver al taller
            </SecondaryButton>
          </div>
        </details>
      ) : null}
    </form>
  );
}
