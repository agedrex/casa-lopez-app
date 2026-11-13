"use client";

import { useEffect, useRef, useState } from "react";
import {
  Field,
  FormFeedback,
  inputClass,
  PrimaryButton,
} from "@/components/form";
import { useActionForm } from "@/lib/use-action-form";
import { cargarUltimoLote, createOrden } from "../actions";
import {
  type Fila,
  FilasDeProductos,
  PreciosPorFila,
  type ProductoOption,
} from "./lote-product-rows";
import { type PanelState, UltimoLotePanel } from "./ultimo-lote-panel";

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
  const [taller, setTaller] = useState("");
  const [filas, setFilas] = useState<Fila[]>([
    { id: 0, producto: "", cantidad: "" },
  ]);
  const nextId = useRef(1);
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

  function changeFila(
    id: number,
    campo: "producto" | "cantidad",
    valor: string,
  ) {
    setFilas((actuales) =>
      actuales.map((fila) =>
        fila.id === id ? { ...fila, [campo]: valor } : fila,
      ),
    );
  }

  // No form key: on success the action redirects to the new lot.
  return (
    <form onSubmit={onSubmit} className="space-y-6">
      <div className="grid gap-5 sm:grid-cols-2">
        <Field
          id="lote-taller"
          label="Taller"
          hint={donde === "INTERNA" ? "El lote se hace en casa." : undefined}
        >
          <select
            id="lote-taller"
            name="taller"
            value={taller}
            onChange={(event) => setTaller(event.target.value)}
            disabled={donde === "INTERNA"}
            className={inputClass}
          >
            <option value="">Elegir…</option>
            {talleres.map((option) => (
              <option key={option.codigo} value={option.codigo}>
                {option.label}
              </option>
            ))}
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
      <UltimoLotePanel state={panel} filas={filas} productos={productos} />
      <FilasDeProductos
        productos={productos}
        filas={filas}
        onChange={changeFila}
        onAdd={() => {
          setFilas((actuales) => [
            ...actuales,
            { id: nextId.current, producto: "", cantidad: "" },
          ]);
          nextId.current += 1;
        }}
        onRemove={(id) =>
          setFilas((actuales) => actuales.filter((fila) => fila.id !== id))
        }
      />
      {/* Closed fields still travel with the form: without opening it the lot is EXTERNA at the chosen workshop. */}
      <details className="rounded-card border border-line px-4">
        <summary className="min-h-11 cursor-pointer py-3 text-base text-muted">
          Más opciones
        </summary>
        <div className="space-y-6 pb-4">
          <div className="grid gap-5 sm:grid-cols-2">
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
