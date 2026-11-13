"use client";

import { useEffect, useId, useState } from "react";
import { inputClass } from "@/components/form";
import {
  consultaDeBusqueda,
  type FilaDeLote,
  MIN_QUERY,
  type ResultadoDeBusqueda,
} from "@/lib/lote-buscador";
import { buscarProductos } from "../actions";

const DEBOUNCE_MS = 300;

type Busqueda =
  | { status: "idle" }
  | { status: "loading" }
  | { status: "error"; message: string }
  | { status: "ok"; resultados: ResultadoDeBusqueda[]; hayMas: boolean };

/**
 * Finder over the whole catalog: it asks the API while the person types and lists the matches with an
 * "Agregar" button, so several products can be picked one after the other. Enter never submits the form.
 */
export function BuscadorDeProductos({
  filas,
  onAdd,
}: {
  filas: FilaDeLote[];
  onAdd: (resultado: ResultadoDeBusqueda) => void;
}) {
  const inputId = useId();
  const [texto, setTexto] = useState("");
  const [busqueda, setBusqueda] = useState<Busqueda>({ status: "idle" });

  useEffect(() => {
    const consulta = consultaDeBusqueda(texto);
    if (consulta === null) {
      setBusqueda({ status: "idle" });
      return;
    }
    let vigente = true;
    setBusqueda({ status: "loading" });
    const espera = setTimeout(() => {
      buscarProductos(consulta)
        .then((respuesta) => {
          if (vigente) setBusqueda(respuesta);
        })
        .catch(() => {
          if (vigente) {
            setBusqueda({
              status: "error",
              message: "No se pudo buscar. Intente de nuevo.",
            });
          }
        });
    }, DEBOUNCE_MS);
    return () => {
      vigente = false;
      clearTimeout(espera);
    };
  }, [texto]);

  const agregados = new Set(filas.map((fila) => fila.producto));

  return (
    <div className="space-y-3">
      <label
        htmlFor={inputId}
        className="block text-sm uppercase tracking-caps-sm text-muted sm:text-xs"
      >
        Buscar productos
      </label>
      <input
        id={inputId}
        type="search"
        autoComplete="off"
        placeholder="Código, nombre, modelo, cuero o color"
        value={texto}
        onChange={(event) => setTexto(event.target.value)}
        onKeyDown={(event) => {
          if (event.code === "Enter" || event.code === "NumpadEnter") {
            event.preventDefault();
          }
        }}
        className={inputClass}
      />
      <div aria-live="polite" className="text-sm">
        {busqueda.status === "idle" ? (
          <p className="text-muted">
            Escriba al menos {MIN_QUERY} letras: se busca en todos los
            productos.
          </p>
        ) : null}
        {busqueda.status === "loading" ? (
          <p className="text-muted">Buscando…</p>
        ) : null}
        {busqueda.status === "error" ? (
          <p role="alert" className="text-red-700">
            {busqueda.message}
          </p>
        ) : null}
        {busqueda.status === "ok" && busqueda.resultados.length === 0 ? (
          <p className="text-muted">No hay productos que coincidan.</p>
        ) : null}
      </div>
      {busqueda.status === "ok" && busqueda.resultados.length > 0 ? (
        <>
          <ul className="max-h-80 divide-y divide-line overflow-y-auto rounded-card border border-line">
            {busqueda.resultados.map((resultado) => {
              const agregado = agregados.has(resultado.codigo);
              return (
                <li
                  key={resultado.codigo}
                  className="flex items-center justify-between gap-4 px-3 py-2"
                >
                  <span className="min-w-0 text-sm">
                    {resultado.nombre}
                    <span className="block text-xs text-muted">
                      {[resultado.codigo, resultado.modelo, resultado.categoria]
                        .filter(Boolean)
                        .join(" · ")}
                    </span>
                  </span>
                  <button
                    type="button"
                    onClick={() => onAdd(resultado)}
                    disabled={agregado}
                    aria-label={
                      agregado
                        ? `${resultado.nombre} ya está en el lote`
                        : `Agregar ${resultado.nombre} al lote`
                    }
                    className="inline-flex min-h-11 shrink-0 items-center rounded-card border border-ink px-3 py-2 text-sm uppercase tracking-caps-sm hover:bg-ink hover:text-white disabled:border-line disabled:text-muted disabled:hover:bg-transparent disabled:hover:text-muted sm:min-h-0"
                  >
                    {agregado ? "Agregado" : "Agregar"}
                  </button>
                </li>
              );
            })}
          </ul>
          {busqueda.hayMas ? (
            <p className="text-sm text-muted">
              Hay más productos que coinciden: escriba algo más para acotar la
              búsqueda.
            </p>
          ) : null}
        </>
      ) : null}
    </div>
  );
}
