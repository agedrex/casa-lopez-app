"use client";

import Link from "next/link";
import { type ReactNode, useEffect, useMemo, useRef, useState } from "react";
import { Badge } from "@/components/ui";
import { decimalInputText } from "@/lib/format";
import { ESTADO_TONE, estadoLabel, isEstado } from "@/lib/formularios";
import {
  CONSUMPTION_FIELDS,
  hasMissingConsumptions,
  SIZES,
  sizeLabel,
} from "@/lib/modelos";
import {
  ariaSort,
  type Orden,
  ordenar,
  paginar,
  siguienteOrden,
  type Valor,
} from "@/lib/paginacion";
import type { ModeloLista } from "@/lib/types";

/** Read-only measure: right-aligned, "—" when the model has no value (NULL = missing data). */
function Measure({ value }: { value: string | null }) {
  return value === null ? (
    <span className="block text-right text-muted">—</span>
  ) : (
    <span className="block text-right tabular-nums">
      {decimalInputText(value)}
    </span>
  );
}

/** State of the newest consumption sheet of the model, linked to that sheet; "Sin hoja" when it has none. */
function HojaEstado({ modelo }: { modelo: ModeloLista }) {
  const { hoja_codigo: codigo, hoja_estado: estado } = modelo;
  if (!codigo || !estado) {
    return <span className="text-muted">Sin hoja</span>;
  }
  return (
    <Link
      href={`/taller/modelos/${encodeURIComponent(codigo)}`}
      title={`Hoja ${codigo}`}
      className="inline-block"
    >
      <Badge tone={isEstado(estado) ? ESTADO_TONE[estado] : "neutral"}>
        {estadoLabel(estado)}
      </Badge>
    </Link>
  );
}

// The same fields, in the same order and with the same units, as the consumption form of a model
// (`ConsumptionFields`). Hours are left out on purpose: they live in the page of each model.
const MEASURES = CONSUMPTION_FIELDS.filter(
  (field) => field.name !== "horas_de_confeccion",
);

type Columna = {
  clave: string;
  titulo: string;
  /** Numeric columns are right-aligned, like their cells. */
  numerica?: boolean;
  valor: (modelo: ModeloLista) => Valor;
  celda: (modelo: ModeloLista) => ReactNode;
};

const TAMANOS = SIZES.map((size) => size.value as string);

function numero(value: string | null): number | null {
  if (value === null) return null;
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : null;
}

const COLUMNAS: Columna[] = [
  {
    clave: "estado",
    titulo: "Estado",
    valor: (m) => (m.hoja_estado ? estadoLabel(m.hoja_estado) : null),
    celda: (m) => <HojaEstado modelo={m} />,
  },
  {
    clave: "categoria",
    titulo: "Categoría",
    valor: (m) => m.categoria,
    celda: (m) => m.categoria ?? <span className="text-muted">—</span>,
  },
  {
    clave: "tamano",
    titulo: "Tamaño",
    // Small, medium, large: not alphabetical.
    valor: (m) => {
      const rank = m.tamano ? TAMANOS.indexOf(m.tamano) : -1;
      return rank < 0 ? null : rank;
    },
    celda: (m) => sizeLabel(m.tamano),
  },
  ...MEASURES.map(
    (field): Columna => ({
      clave: field.name,
      titulo: `${field.label} ${field.unit}`,
      numerica: true,
      valor: (m) => numero(m[field.name]),
      celda: (m) => <Measure value={m[field.name]} />,
    }),
  ),
  {
    clave: "forro",
    titulo: "Forro (material)",
    valor: (m) => m.forro,
    celda: (m) => m.forro ?? <span className="text-muted">Sin forro</span>,
  },
];

const NOMBRE: Columna = {
  clave: "nombre",
  titulo: "Modelo",
  valor: (m) => m.nombre_del_modelo,
  celda: (m) => (
    <div className="min-w-56 max-w-80">
      <Link
        href={`/productos/modelos/${encodeURIComponent(m.codigo)}`}
        className="block font-medium underline decoration-gold underline-offset-4"
      >
        {m.nombre_del_modelo}
      </Link>
      <span className="block font-mono text-sm text-muted sm:text-xs">
        {m.codigo}
      </span>
    </div>
  ),
};

const th =
  "border-b border-line bg-paper-mid px-3 py-3 text-sm font-normal uppercase tracking-caps-sm text-muted sm:text-xs";

function Encabezado({
  columna,
  orden,
  onOrdenar,
  className,
}: {
  columna: Columna;
  orden: Orden | null;
  onOrdenar: (clave: string) => void;
  className: string;
}) {
  const sentido = ariaSort(orden, columna.clave);
  return (
    <th
      scope="col"
      aria-sort={sentido}
      className={`${className} ${columna.numerica ? "text-right" : "text-left"}`}
    >
      <button
        type="button"
        onClick={() => onOrdenar(columna.clave)}
        title={`Ordenar por ${columna.titulo}`}
        className="inline-flex min-h-11 items-center gap-1 uppercase tracking-caps-sm hover:text-ink sm:min-h-0"
      >
        {columna.titulo}
        <span aria-hidden="true" className="w-3 text-ink">
          {sentido === "ascending" ? "▲" : sentido === "descending" ? "▼" : ""}
        </span>
      </button>
    </th>
  );
}

/**
 * The models sheet: one thing per column, in the order of the consumption form (name, the state of the sheet, category,
 * size, the consumptions with their units, lining material). 25 rows per page, and each header sorts the whole list.
 * Read only: rows with missing consumptions are highlighted. Nothing is computed here.
 */
export function ModelosGrid({ modelos }: { modelos: ModeloLista[] }) {
  const [orden, setOrden] = useState<Orden | null>(null);
  const [pagina, setPagina] = useState(1);
  const marco = useRef<HTMLDivElement>(null);

  const ordenados = useMemo(() => {
    const columna = [NOMBRE, ...COLUMNAS].find(
      (item) => item.clave === orden?.clave,
    );
    return orden && columna
      ? ordenar(modelos, columna.valor, orden.dir)
      : modelos;
  }, [modelos, orden]);
  const vista = paginar(ordenados, pagina);

  // A new page or a new order starts at the top of the table, not where the previous one was scrolled.
  // biome-ignore lint/correctness/useExhaustiveDependencies: the page and the order are the triggers.
  useEffect(() => {
    marco.current?.scrollTo({ top: 0 });
  }, [vista.pagina, orden]);

  function ordenarPor(clave: string) {
    setOrden((actual) => siguienteOrden(actual, clave));
    setPagina(1);
  }

  return (
    <div className="space-y-4">
      <div
        ref={marco}
        className="max-h-[75vh] w-fit max-w-full overflow-auto overscroll-x-contain rounded-card border border-line bg-surface"
      >
        <table
          aria-label="Consumos por modelo"
          className="w-auto min-w-max border-collapse text-left text-sm"
        >
          <thead>
            <tr>
              <Encabezado
                columna={NOMBRE}
                orden={orden}
                onOrdenar={ordenarPor}
                className={`${th} sticky left-0 top-0 z-30 sm:px-4`}
              />
              {COLUMNAS.map((columna) => (
                <Encabezado
                  key={columna.clave}
                  columna={columna}
                  orden={orden}
                  onOrdenar={ordenarPor}
                  className={`${th} sticky top-0 z-20`}
                />
              ))}
            </tr>
          </thead>
          <tbody>
            {vista.items.map((modelo) => {
              const falta = hasMissingConsumptions(modelo);
              return (
                <tr key={modelo.codigo} className={falta ? "bg-blush/25" : ""}>
                  <th
                    scope="row"
                    className={`sticky left-0 z-10 border-b border-line/70 bg-surface px-3 py-2 text-left align-top font-normal sm:px-4 ${falta ? "border-l-4 border-l-blush-deep" : "border-l-4 border-l-transparent"}`}
                  >
                    {NOMBRE.celda(modelo)}
                  </th>
                  {COLUMNAS.map((columna) => (
                    <td
                      key={columna.clave}
                      className="border-b border-line/70 px-3 py-2 align-top text-sm"
                    >
                      {columna.celda(modelo)}
                    </td>
                  ))}
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      {vista.paginas > 1 ? (
        <nav
          aria-label="Paginación"
          className="flex flex-wrap items-center justify-between gap-3 text-sm"
        >
          <button
            type="button"
            onClick={() => setPagina(vista.pagina - 1)}
            disabled={vista.pagina <= 1}
            className="min-h-11 rounded-card border border-ink px-4 py-2 text-sm uppercase tracking-caps-sm hover:bg-ink hover:text-white disabled:opacity-40 disabled:hover:bg-transparent disabled:hover:text-inherit sm:min-h-0"
          >
            ← Anterior
          </button>
          <span className="text-muted" aria-live="polite">
            {vista.desde}–{vista.hasta} de {vista.total} · Página {vista.pagina}{" "}
            de {vista.paginas}
          </span>
          <button
            type="button"
            onClick={() => setPagina(vista.pagina + 1)}
            disabled={vista.pagina >= vista.paginas}
            className="min-h-11 rounded-card border border-ink px-4 py-2 text-sm uppercase tracking-caps-sm hover:bg-ink hover:text-white disabled:opacity-40 disabled:hover:bg-transparent disabled:hover:text-inherit sm:min-h-0"
          >
            Siguiente →
          </button>
        </nav>
      ) : null}
    </div>
  );
}
