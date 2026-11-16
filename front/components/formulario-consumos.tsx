"use client";

import { useState, useTransition } from "react";
import { completarHoja, guardarHoja } from "@/app/(app)/taller/modelos/actions";
import { type FormState, IDLE } from "@/lib/action-state";
import {
  type FilaHoja,
  filasDeHoja,
  type ModoHoja,
  SECCIONES,
} from "@/lib/formularios";
import type { FormularioLinea } from "@/lib/types";
import {
  FormFeedback,
  inputClass,
  PrimaryButton,
  SecondaryButton,
} from "./form";

/** Big title of a section; the border color and the help line tell "Consumos" (m²) and "Herrajes" (units) apart. */
function TituloSeccion({ seccion }: { seccion: (typeof SECCIONES)[number] }) {
  return (
    <div className={`mb-3 border-l-4 ${seccion.accent} pl-4`}>
      <h3 className="text-2xl">
        {seccion.title}{" "}
        <span className="text-base text-muted">({seccion.unit})</span>
      </h3>
      <p className="mt-0.5 text-sm text-muted">{seccion.help}</p>
    </div>
  );
}

/**
 * The consumption sheet of a model: the CONSUMOS (m²) and HERRAJES (units) tables of the paper sheet. It calculates nothing.
 * - `editar` (taller, sheet ENVIADO): quantity and comment of every preloaded row; "Guardar" and "Enviar". Empty rows are ignored.
 * - `revisar` and `leer`: the filled rows as text. In `revisar` the admin buttons come from the page (Validar / Devolver).
 * The page passes `key={estado}` so a state change (completed, returned) starts from the fresh rows.
 */
export function HojaConsumos({
  codigo,
  lineas,
  modo,
}: {
  codigo: string;
  lineas: FormularioLinea[];
  modo: ModoHoja;
}) {
  if (modo === "editar")
    return <HojaEditable codigo={codigo} lineas={lineas} />;
  return <HojaDeSoloLectura lineas={lineas} />;
}

function HojaDeSoloLectura({ lineas }: { lineas: FormularioLinea[] }) {
  const filas = filasDeHoja(lineas);
  const vacias = filas.filter((f) => !f.cantidad && !f.comentario).length;
  return (
    <div className="space-y-8">
      {SECCIONES.map((seccion) => {
        const llenas = filas.filter(
          (f) => f.seccion === seccion.value && (f.cantidad || f.comentario),
        );
        return (
          <section key={seccion.value} aria-label={seccion.title}>
            <TituloSeccion seccion={seccion} />
            {llenas.length === 0 ? (
              <p className="text-sm text-muted">Sin datos cargados.</p>
            ) : (
              <ul className="divide-y divide-line/70 rounded-card border border-line bg-surface">
                {llenas.map((fila) => (
                  <li
                    key={`${fila.seccion}-${fila.nombre}`}
                    className="grid gap-1 px-4 py-3 text-sm sm:grid-cols-[minmax(0,1.2fr)_8rem_minmax(0,1.5fr)] sm:gap-4"
                  >
                    <span>{fila.nombre}</span>
                    <span className="tabular-nums sm:text-right">
                      {fila.cantidad || "—"}
                    </span>
                    <span className="text-muted">{fila.comentario}</span>
                  </li>
                ))}
              </ul>
            )}
          </section>
        );
      })}
      {vacias > 0 ? (
        <p className="text-sm text-muted">
          {vacias === 1
            ? "Hay 1 fila sin cantidad ni comentario (no se muestra)."
            : `Hay ${vacias} filas sin cantidad ni comentario (no se muestran).`}
        </p>
      ) : null}
    </div>
  );
}

function HojaEditable({
  codigo,
  lineas,
}: {
  codigo: string;
  lineas: FormularioLinea[];
}) {
  const [filas, setFilas] = useState<FilaHoja[]>(() => filasDeHoja(lineas));
  const [state, setState] = useState<FormState>(IDLE);
  const [pending, startTransition] = useTransition();

  const cambiar = (indice: number, cambio: Partial<FilaHoja>) =>
    setFilas((actuales) =>
      actuales.map((fila, i) => (i === indice ? { ...fila, ...cambio } : fila)),
    );

  const enviar = (accion: typeof guardarHoja) => {
    startTransition(async () => {
      setState(await accion(codigo, filas));
    });
  };

  return (
    <form
      className="space-y-10"
      onSubmit={(event) => {
        event.preventDefault();
        const submitter = (event.nativeEvent as SubmitEvent).submitter;
        enviar(
          submitter instanceof HTMLButtonElement &&
            submitter.value === "completar"
            ? completarHoja
            : guardarHoja,
        );
      }}
    >
      {SECCIONES.map((seccion) => (
        <fieldset key={seccion.value} className="min-w-0">
          <legend className="w-full p-0">
            <TituloSeccion seccion={seccion} />
          </legend>
          <ul className="space-y-1.5">
            {filas.map((fila, indice) =>
              fila.seccion !== seccion.value ? null : (
                <li
                  key={`${fila.seccion}-${fila.nombre}`}
                  className="grid grid-cols-[minmax(0,1fr)_7.5rem] gap-2 rounded-card border border-line bg-surface p-2 sm:grid-cols-[minmax(0,1.2fr)_8rem_minmax(0,1.5fr)] sm:items-center sm:gap-3 sm:px-3"
                >
                  <span className="self-center text-sm">{fila.nombre}</span>
                  <input
                    aria-label={`${fila.nombre}: cantidad (${seccion.unit})`}
                    inputMode="decimal"
                    autoComplete="off"
                    placeholder="0,00"
                    value={fila.cantidad}
                    onChange={(e) =>
                      cambiar(indice, { cantidad: e.target.value })
                    }
                    className={`${inputClass} min-h-11 text-right tabular-nums sm:min-h-9`}
                  />
                  <input
                    aria-label={`${fila.nombre}: comentarios o modificaciones`}
                    placeholder="Comentarios / modificaciones"
                    maxLength={2000}
                    value={fila.comentario}
                    onChange={(e) =>
                      cambiar(indice, { comentario: e.target.value })
                    }
                    className={`${inputClass} col-span-2 min-h-11 sm:col-span-1 sm:min-h-9`}
                  />
                </li>
              ),
            )}
          </ul>
        </fieldset>
      ))}
      <FormFeedback state={state} />
      <div className="flex flex-col gap-2 sm:flex-row">
        <SecondaryButton pending={pending} value="guardar" name="accion">
          {pending ? "Guardando…" : "Guardar"}
        </SecondaryButton>
        <PrimaryButton pending={pending} value="completar" name="accion">
          {pending ? "Enviando…" : "Enviar"}
        </PrimaryButton>
      </div>
    </form>
  );
}
