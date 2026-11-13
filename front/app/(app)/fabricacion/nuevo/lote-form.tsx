"use client";

import { useEffect, useRef, useState } from "react";
import {
  Field,
  FormFeedback,
  inputClass,
  PrimaryButton,
} from "@/components/form";
import {
  agregarProducto,
  FABRICA,
  quitarProducto,
  responsableDelLote,
} from "@/lib/lote-buscador";
import { useActionForm } from "@/lib/use-action-form";
import { cargarUltimoLote, createOrden } from "../actions";
import { BuscadorDeProductos } from "./lote-buscador";
import {
  type Fila,
  FilasDeProductos,
  PreciosPorFila,
} from "./lote-product-rows";
import { type PanelState, UltimoLotePanel } from "./ultimo-lote-panel";

export type Option = { codigo: string; label: string };

export function LoteForm({
  talleres,
  personas,
  today,
}: {
  talleres: Option[];
  personas: Option[];
  today: string;
}) {
  const { state, pending, onSubmit } = useActionForm(createOrden);
  // One choice: the factory (a lot made at home) or one workshop. The API takes it as place + workshop.
  const [responsable, setResponsable] = useState("");
  const { donde, taller } = responsableDelLote(responsable);
  const [filas, setFilas] = useState<Fila[]>([]);
  const nextId = useRef(0);
  const [panel, setPanel] = useState<PanelState>({ status: "idle" });

  // Last lot of the chosen workshop. The history is admin only: when it is refused the panel stays hidden.
  useEffect(() => {
    if (taller === "" || donde !== "EXTERNA") {
      setPanel({ status: "idle" });
      return;
    }
    let current = true;
    setPanel({ status: "loading" });
    cargarUltimoLote(taller)
      .then((result) => {
        if (!current) return;
        setPanel(
          result.status === "ok"
            ? { status: "ok", ultimo: result.ultimo }
            : { status: "idle" },
        );
      })
      .catch(() => {
        if (current) setPanel({ status: "idle" });
      });
    return () => {
      current = false;
    };
  }, [taller, donde]);

  function changeCantidad(id: number, cantidad: string) {
    setFilas((actuales) =>
      actuales.map((fila) => (fila.id === id ? { ...fila, cantidad } : fila)),
    );
  }

  // No form key: on success the action redirects to the new lot.
  return (
    <form onSubmit={onSubmit} className="space-y-6">
      {/* The place and the workshop travel as hidden fields derived from the single choice below. */}
      <input type="hidden" name="donde_se_hace" value={donde} />
      <input type="hidden" name="taller" value={taller} />
      <div className="grid gap-5 sm:grid-cols-2">
        <Field
          id="lote-responsable"
          label="Quién lo hace"
          hint={
            responsable === FABRICA
              ? "El lote se hace en la fábrica."
              : undefined
          }
        >
          <select
            id="lote-responsable"
            value={responsable}
            onChange={(event) => setResponsable(event.target.value)}
            className={inputClass}
          >
            <option value="">Elegir…</option>
            <option value={FABRICA}>Fábrica (en casa)</option>
            {talleres.length > 0 ? (
              <optgroup label="Talleres">
                {talleres.map((option) => (
                  <option key={option.codigo} value={option.codigo}>
                    {option.label}
                  </option>
                ))}
              </optgroup>
            ) : null}
          </select>
        </Field>
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
      <UltimoLotePanel state={panel} filas={filas} />
      <fieldset className="space-y-4">
        <legend className="mb-2 text-xs uppercase tracking-caps-sm text-muted">
          Productos del lote
        </legend>
        <BuscadorDeProductos
          filas={filas}
          onAdd={(resultado) => {
            setFilas((actuales) => {
              const nuevas = agregarProducto(
                actuales,
                resultado,
                nextId.current,
              );
              if (nuevas !== actuales) nextId.current += 1;
              return nuevas;
            });
          }}
        />
        <FilasDeProductos
          filas={filas}
          onChange={changeCantidad}
          onRemove={(id) =>
            setFilas((actuales) => quitarProducto(actuales, id))
          }
        />
      </fieldset>
      {/* Closed fields still travel with the form: without opening it the lot goes as chosen above, with no person. */}
      <details className="rounded-card border border-line px-4">
        <summary className="min-h-11 cursor-pointer py-3 text-base text-muted">
          Más opciones
        </summary>
        <div className="space-y-6 pb-4">
          <div className="grid gap-5 sm:grid-cols-2">
            {donde === "INTERNA" ? (
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
            ) : null}
          </div>
          <div className="space-y-2">
            <p className="text-xs uppercase tracking-caps-sm text-muted">
              Precios por producto (opcional)
            </p>
            <p className="text-sm text-muted">
              El taller pone el precio recién al retirar la mercadería: si
              todavía no lo tenés, dejá el precio pagado vacío y cargalo después
              desde el lote.
            </p>
            <PreciosPorFila filas={filas} />
          </div>
          <Field id="lote-nota" label="Nota (opcional)">
            <input
              id="lote-nota"
              name="nota"
              autoComplete="off"
              className={inputClass}
            />
          </Field>
        </div>
      </details>
      <FormFeedback state={state} />
      <PrimaryButton pending={pending}>
        {pending ? "Creando…" : "Crear lote"}
      </PrimaryButton>
    </form>
  );
}
