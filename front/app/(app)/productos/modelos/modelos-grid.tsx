"use client";

import Link from "next/link";
import { useMemo } from "react";
import {
  EditableGrid,
  type GridColumn,
  type GridRow,
} from "@/components/editable-grid";
import { Badge } from "@/components/ui";
import { error, type FormState } from "@/lib/action-state";
import { decimalInputText } from "@/lib/format";
import { ESTADO_TONE, estadoLabel, isEstado } from "@/lib/formularios";
import {
  CONSUMPTION_FIELDS,
  hasMissingConsumptions,
  originLabel,
  sizeLabel,
} from "@/lib/modelos";
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

// A grid with no editable column: the consumptions are edited in the page of each model.
const NO_COLUMNS: GridColumn[] = [];

async function readOnly(): Promise<FormState> {
  return error("Los consumos se editan desde la página de cada modelo.");
}

/**
 * The models sheet: one thing per column, in the order of the consumption form (name, category, size,
 * the consumptions with their units, lining material, origin) and the state of the sheet at the end.
 * Read only: rows with missing consumptions are highlighted. Nothing is computed here.
 */
export function ModelosGrid({ modelos }: { modelos: ModeloLista[] }) {
  const rows = useMemo<GridRow[]>(
    () =>
      modelos.map((modelo) => {
        const missing = hasMissingConsumptions(modelo);
        return {
          id: modelo.codigo,
          name: modelo.nombre_del_modelo,
          warn: missing,
          label: (
            <div className="min-w-56 max-w-80">
              <Link
                href={`/productos/modelos/${encodeURIComponent(modelo.codigo)}`}
                className="block font-medium underline decoration-gold underline-offset-4"
              >
                {modelo.nombre_del_modelo}
              </Link>
              <span className="block font-mono text-sm text-muted sm:text-xs">
                {modelo.codigo}
              </span>
            </div>
          ),
          cells: {},
          extrasBefore: [
            modelo.categoria ?? <span className="text-muted">—</span>,
            sizeLabel(modelo.tamano),
            ...MEASURES.map((field) => (
              <Measure key={field.name} value={modelo[field.name]} />
            )),
            modelo.forro ?? <span className="text-muted">Sin forro</span>,
            originLabel(modelo.origen_de_los_consumos),
            <div key="estado" className="flex flex-wrap gap-1.5">
              <HojaEstado modelo={modelo} />
              {missing ? (
                <Badge tone="warn" title="Algún consumo está vacío.">
                  Faltan datos
                </Badge>
              ) : null}
            </div>,
          ],
        };
      }),
    [modelos],
  );

  return (
    <EditableGrid
      label="Consumos por modelo"
      rowHeader="Modelo"
      columns={NO_COLUMNS}
      extraHeadersBefore={[
        "Categoría",
        "Tamaño",
        ...MEASURES.map((field) => `${field.label} ${field.unit}`),
        "Forro (material)",
        "Origen de los consumos",
        "Estado",
      ]}
      rows={rows}
      noun={{ one: "modelo", many: "modelos" }}
      compact
      fitContent
      fitFrame
      onSave={readOnly}
    />
  );
}
