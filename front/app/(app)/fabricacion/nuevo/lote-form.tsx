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
import { NUEVO_CATALOGO } from "../../productos/catalogo-nuevo";
import { cargarUltimoLote, createOrden } from "../actions";
import { CueroPanel } from "./cuero-panel";
import { BuscadorDeProductos } from "./lote-buscador";
import { type Fila, FilasDeProductos } from "./lote-product-rows";
import { type PanelState, UltimoLotePanel } from "./ultimo-lote-panel";

export type Option = { codigo: string; label: string };

export function LoteForm({
  talleres,
  nombresCuero,
}: {
  talleres: Option[];
  /** Material code -> name, to label the alternative leathers of the availability panel. */
  nombresCuero: Record<string, string>;
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
    if (taller === "" || taller === NUEVO_CATALOGO || donde !== "EXTERNA") {
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
      <div className="max-w-md">
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
            <option value={NUEVO_CATALOGO}>+ Crear taller nuevo…</option>
          </select>
          {taller === NUEVO_CATALOGO ? (
            <div className="mt-3">
              <label htmlFor="lote-taller-nuevo" className="sr-only">
                Nombre del taller nuevo
              </label>
              <input
                id="lote-taller-nuevo"
                name="taller_nuevo"
                required
                maxLength={200}
                autoComplete="off"
                placeholder="Nombre del taller nuevo"
                className={inputClass}
              />
              <p className="mt-1 text-sm text-muted sm:text-xs">
                Después podés completar teléfono y CUIT en Talleres.
              </p>
            </div>
          ) : null}
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
      <CueroPanel filas={filas} nombres={nombresCuero} />
      <FormFeedback state={state} />
      <PrimaryButton pending={pending}>
        {pending ? "Guardando…" : "Crear lote"}
      </PrimaryButton>
    </form>
  );
}
