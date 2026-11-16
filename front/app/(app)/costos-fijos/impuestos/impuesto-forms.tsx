"use client";

import { useMemo } from "react";
import {
  fractionToPercentInput,
  percentToFraction,
} from "@/app/(app)/admin/impuestos/percent";
import {
  EditableGrid,
  type GridColumn,
  type GridRow,
  type GridSave,
} from "@/components/editable-grid";
import type { Impuesto } from "@/lib/types";
import { guardarImpuestosLote } from "./actions";

const COLUMNS: GridColumn[] = [
  {
    key: "nombre",
    header: "Impuesto",
    kind: "text",
    newOnly: true,
    required: true,
    width: "min-w-64",
    placeholder: "IVA",
  },
  {
    key: "porcentaje",
    header: "Porcentaje (%)",
    kind: "decimal",
    required: true,
    width: "min-w-40",
    placeholder: "21",
    validate: (value) =>
      percentToFraction(value) === null
        ? "Entre 0 y 100, con hasta un decimal. Ejemplo: 21 o 3,5."
        : null,
  },
];

const NOUN = { one: "impuesto", many: "impuestos" };

/** The taxes as a sheet: the percentage is edited in place and new taxes are added at the end. */
export function ImpuestosGrid({ impuestos }: { impuestos: Impuesto[] }) {
  const rows = useMemo<GridRow[]>(
    () =>
      impuestos.map((impuesto) => ({
        id: impuesto.codigo,
        name: impuesto.nombre,
        label: <span className="text-sm text-muted">{impuesto.codigo}</span>,
        cells: {
          nombre: impuesto.nombre,
          porcentaje: fractionToPercentInput(impuesto.alicuota),
        },
      })),
    [impuestos],
  );

  function onSave(save: GridSave) {
    return guardarImpuestosLote(
      save.changes.map((change) => ({
        codigo: change.id,
        porcentaje: change.cells.porcentaje ?? "",
      })),
      save.added,
    );
  }

  return (
    <EditableGrid
      label="Impuestos"
      rowHeader="ID"
      columns={COLUMNS}
      rows={rows}
      noun={NOUN}
      allowNew
      startWithDraft={false}
      addLabel="Agregar impuesto"
      newRowLabel="Impuesto nuevo"
      autoSave
      compact
      fitContent
      onSave={onSave}
    />
  );
}
