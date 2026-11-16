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

/**
 * The consumption sheet of a model: the CONSUMOS (m²) and HERRAJES (units) tables of the paper sheet. It calculates nothing.
 * - `editar` (taller, sheet ENVIADO): quantity and comment of every row, add / remove rows, "Guardar" and "Completar".
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
            <h3 className="mb-3 text-lg">
              {seccion.title}{" "}
              <span className="text-sm text-muted">({seccion.unit})</span>
            </h3>
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
      className="space-y-5"
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
          <legend className="mb-2 text-base">
            {seccion.title}{" "}
            <span className="text-sm text-muted">({seccion.unit})</span>
          </legend>
          <ul className="space-y-1.5">
            {filas.map((fila, indice) =>
              fila.seccion !== seccion.value ? null : (
                <li
                  // biome-ignore lint/suspicious/noArrayIndexKey: the rows are only ever added at the end or removed, and their position is their identity here.
                  key={indice}
                  className="grid grid-cols-[minmax(0,1fr)_7.5rem] gap-2 rounded-card border border-line bg-surface p-2 sm:grid-cols-[minmax(0,1.2fr)_8rem_minmax(0,1.5fr)_auto] sm:items-center sm:gap-3 sm:px-3"
                >
                  {fila.agregada ? (
                    <input
                      aria-label={`Nombre de la fila ${indice + 1} de ${seccion.title.toLowerCase()}`}
                      value={fila.nombre}
                      maxLength={200}
                      placeholder="Nombre"
                      onChange={(e) =>
                        cambiar(indice, { nombre: e.target.value })
                      }
                      className={`${inputClass} min-h-11 sm:min-h-9`}
                    />
                  ) : (
                    <span className="self-center text-sm">{fila.nombre}</span>
                  )}
                  <input
                    aria-label={`${fila.nombre || "Fila nueva"}: cantidad (${seccion.unit})`}
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
                    aria-label={`${fila.nombre || "Fila nueva"}: comentarios o modificaciones`}
                    placeholder="Comentarios / modificaciones"
                    maxLength={2000}
                    value={fila.comentario}
                    onChange={(e) =>
                      cambiar(indice, { comentario: e.target.value })
                    }
                    className={`${inputClass} col-span-2 min-h-11 sm:col-span-1 sm:min-h-9`}
                  />
                  <button
                    type="button"
                    aria-label={`Quitar la fila ${fila.nombre || "nueva"}`}
                    onClick={() =>
                      setFilas((actuales) =>
                        actuales.filter((_, i) => i !== indice),
                      )
                    }
                    className="col-span-2 min-h-11 rounded-card border border-line px-3 text-sm text-muted hover:border-bordeaux hover:text-bordeaux sm:col-span-1 sm:min-h-9 sm:py-1"
                  >
                    ×
                  </button>
                </li>
              ),
            )}
          </ul>
          <button
            type="button"
            onClick={() =>
              setFilas((actuales) => [
                ...actuales,
                {
                  seccion: seccion.value,
                  nombre: "",
                  cantidad: "",
                  comentario: "",
                  agregada: true,
                },
              ])
            }
            className="mt-1 min-h-11 text-sm underline decoration-gold underline-offset-4 sm:min-h-9"
          >
            + Agregar fila de {seccion.title.toLowerCase()}
          </button>
        </fieldset>
      ))}
      <FormFeedback state={state} />
      <div className="flex flex-col gap-2 sm:flex-row">
        <SecondaryButton pending={pending} value="guardar" name="accion">
          {pending ? "Guardando…" : "Guardar"}
        </SecondaryButton>
        <PrimaryButton pending={pending} value="completar" name="accion">
          Completar y enviar a revisión
        </PrimaryButton>
      </div>
      <p className="text-xs text-muted">
        Al completar, la hoja pasa al administrador y ya no la podés editar,
        salvo que te la devuelva con comentarios. Las filas vacías no hace falta
        borrarlas.
      </p>
    </form>
  );
}
