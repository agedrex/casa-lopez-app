"use client";

import { useRef, useState, useTransition } from "react";
import {
  completarHoja,
  enviarHojaAlTaller,
  guardarHoja,
} from "@/app/(app)/taller/modelos/actions";
import { type FormState, IDLE } from "@/lib/action-state";
import {
  type AccionHoja,
  agregarFila,
  type FilaHoja,
  filasDeHoja,
  type ModoHoja,
  quitarFila,
  renombrarFila,
  SECCIONES,
} from "@/lib/formularios";
import type { FormularioLinea } from "@/lib/types";
import {
  FormFeedback,
  inputClass,
  PrimaryButton,
  SecondaryButton,
} from "./form";

/** Big title of a section; the border color and the help line tell "Consumos" and "Herrajes" apart. Each row shows its own unit. */
function TituloSeccion({ seccion }: { seccion: (typeof SECCIONES)[number] }) {
  return (
    <div className={`mb-3 border-l-4 ${seccion.accent} pl-4`}>
      <h3 className="text-2xl">{seccion.title}</h3>
      <p className="mt-0.5 text-sm text-muted">{seccion.help}</p>
    </div>
  );
}

/**
 * The consumption sheet of a model: the CONSUMOS and HERRAJES tables of the paper sheet, which the preloaded rows only start. It
 * calculates nothing.
 * - `editar` and `revisar` (whoever may edit: the admin until it is validated, the taller while ENVIADO): every row can be
 *   renamed, removed, and rows can be added; quantity and comment of each. Empty added rows are ignored. `acciones` are the
 *   buttons: Guardar, "Enviar al taller" (admin, draft) and "Completar y enviar a revisión" (taller). In `revisar` the admin
 *   buttons Validar / Devolver come from the page and work on what was last saved.
 * - `leer`: the filled rows as text.
 * The page passes `key={estado}` so a state change (completed, returned) starts from the fresh rows.
 */
export function HojaConsumos({
  codigo,
  lineas,
  modo,
  acciones,
}: {
  codigo: string;
  lineas: FormularioLinea[];
  modo: ModoHoja;
  acciones: AccionHoja[];
}) {
  if (modo === "leer") return <HojaDeSoloLectura lineas={lineas} />;
  return (
    <HojaEditable
      codigo={codigo}
      lineas={lineas}
      acciones={acciones}
      enRevision={modo === "revisar"}
    />
  );
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
                    key={fila.id}
                    className="grid gap-1 px-4 py-3 text-sm sm:grid-cols-[minmax(0,1.2fr)_8rem_minmax(0,1.5fr)] sm:gap-4"
                  >
                    <span>{fila.nombre}</span>
                    <span className="tabular-nums sm:text-right">
                      {fila.cantidad ? `${fila.cantidad} ${fila.unidad}` : "—"}
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
  acciones,
  enRevision,
}: {
  codigo: string;
  lineas: FormularioLinea[];
  acciones: AccionHoja[];
  enRevision: boolean;
}) {
  const [filas, setFilas] = useState<FilaHoja[]>(() => filasDeHoja(lineas));
  const [state, setState] = useState<FormState>(IDLE);
  const [pending, startTransition] = useTransition();
  const contador = useRef(0);
  // The row just added, so its name field takes the focus.
  const [enfocar, setEnfocar] = useState<string | null>(null);

  const cambiar = (id: string, cambio: Partial<FilaHoja>) =>
    setFilas((actuales) =>
      actuales.map((fila) => (fila.id === id ? { ...fila, ...cambio } : fila)),
    );

  const agregar = (seccion: FilaHoja["seccion"]) => {
    contador.current += 1;
    const id = `nueva-${contador.current}`;
    setFilas((actuales) => agregarFila(actuales, seccion, id));
    setEnfocar(id);
  };

  const accionDe = (valor: string): typeof guardarHoja =>
    valor === "completar"
      ? completarHoja
      : valor === "enviar"
        ? enviarHojaAlTaller
        : guardarHoja;

  return (
    <form
      className="space-y-10"
      onSubmit={(event) => {
        event.preventDefault();
        const submitter = (event.nativeEvent as SubmitEvent).submitter;
        const accion = accionDe(
          submitter instanceof HTMLButtonElement ? submitter.value : "",
        );
        startTransition(async () => {
          setState(await accion(codigo, filas));
        });
      }}
    >
      {SECCIONES.map((seccion) => (
        <fieldset key={seccion.value} className="min-w-0">
          <legend className="w-full p-0">
            <TituloSeccion seccion={seccion} />
          </legend>
          <ul className="space-y-1.5">
            {filas.map((fila) =>
              fila.seccion !== seccion.value ? null : (
                <li
                  key={fila.id}
                  className="grid grid-cols-[minmax(0,1fr)_2.75rem] gap-2 rounded-card border border-line bg-surface p-2 sm:grid-cols-[minmax(0,1.2fr)_9rem_minmax(0,1.5fr)_2.5rem] sm:items-center sm:gap-3 sm:px-3"
                >
                  <input
                    aria-label="Nombre de la fila"
                    placeholder="Nombre de la fila"
                    maxLength={200}
                    autoComplete="off"
                    // biome-ignore lint/a11y/noAutofocus: the row the person just added gets the focus
                    autoFocus={enfocar === fila.id}
                    value={fila.nombre}
                    onChange={(e) =>
                      setFilas((actuales) =>
                        renombrarFila(actuales, fila.id, e.target.value),
                      )
                    }
                    className={`${inputClass} min-h-11 text-sm sm:min-h-9`}
                  />
                  <button
                    type="button"
                    aria-label={`Quitar la fila ${fila.nombre || "sin nombre"}`}
                    title="Quitar la fila"
                    onClick={() =>
                      setFilas((actuales) => quitarFila(actuales, fila.id))
                    }
                    className="min-h-11 rounded-card border border-line text-lg leading-none text-muted hover:border-bordeaux hover:text-bordeaux sm:order-4 sm:min-h-9"
                  >
                    ×
                  </button>
                  <label className="col-span-2 flex items-center gap-2 sm:col-span-1">
                    <input
                      aria-label={`${fila.nombre || "Fila nueva"}: cantidad (${fila.unidad})`}
                      inputMode="decimal"
                      autoComplete="off"
                      placeholder="0,00"
                      value={fila.cantidad}
                      onChange={(e) =>
                        cambiar(fila.id, { cantidad: e.target.value })
                      }
                      className={`${inputClass} min-h-11 text-right tabular-nums sm:min-h-9`}
                    />
                    <span className="w-16 shrink-0 text-xs text-muted">
                      {fila.unidad}
                    </span>
                  </label>
                  <input
                    aria-label={`${fila.nombre || "Fila nueva"}: comentarios o modificaciones`}
                    placeholder="Comentarios / modificaciones"
                    maxLength={2000}
                    value={fila.comentario}
                    onChange={(e) =>
                      cambiar(fila.id, { comentario: e.target.value })
                    }
                    className={`${inputClass} col-span-2 min-h-11 sm:col-span-1 sm:min-h-9`}
                  />
                </li>
              ),
            )}
          </ul>
          <button
            type="button"
            onClick={() => agregar(seccion.value)}
            className="mt-2 min-h-11 text-sm underline decoration-gold underline-offset-4 sm:min-h-0"
          >
            + Agregar fila a {seccion.title.toLowerCase()}
          </button>
        </fieldset>
      ))}
      {enRevision ? (
        <p className="text-sm text-muted">
          Si cambiás algo, tocá Guardar antes de validar o devolver la hoja:
          esas acciones usan lo último que se guardó.
        </p>
      ) : null}
      <FormFeedback state={state} />
      <div className="flex flex-col gap-2 sm:flex-row">
        {acciones.includes("guardar") ? (
          <SecondaryButton
            pending={pending}
            value="guardar"
            name="accion"
            pendingLabel="Guardando…"
          >
            Guardar
          </SecondaryButton>
        ) : null}
        {acciones.includes("enviar") ? (
          <PrimaryButton
            pending={pending}
            value="enviar"
            name="accion"
            pendingLabel="Enviando…"
          >
            Enviar al taller
          </PrimaryButton>
        ) : null}
        {acciones.includes("completar") ? (
          <PrimaryButton
            pending={pending}
            value="completar"
            name="accion"
            pendingLabel="Enviando…"
          >
            Enviar
          </PrimaryButton>
        ) : null}
      </div>
    </form>
  );
}
