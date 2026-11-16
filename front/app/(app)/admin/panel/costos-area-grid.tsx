"use client";

import { useMemo } from "react";
import {
  EditableGrid,
  type GridColumn,
  type GridRow,
  type GridSave,
} from "@/components/editable-grid";
import { Badge } from "@/components/ui";
import {
  decimalInputText,
  EXPENSE_CATEGORIES,
  expenseCategoryLabel,
  formatPeriod,
} from "@/lib/format";
import type { Gasto, Persona } from "@/lib/types";
import { guardarGastosLote } from "../../costos-fijos/actions";

export type AreaDelNegocio = "FABRICA" | "TIENDA";

const AREA_TEXT: Record<AreaDelNegocio, string> = {
  FABRICA: "la fábrica",
  TIENDA: "la tienda",
};

/**
 * The costs of one area (the factory or the store) in one month, as a sheet where every cost of
 * that area is added. The area is not a column: the view decides it, so a row cannot end up in the
 * other area by mistake. A changed amount is a correction on the API side (a new row that replaces
 * the old one, which stays in the history); nothing is overwritten and the totals come from the API.
 */
export function CostosAreaGrid({
  periodo,
  area,
  gastos,
  personas,
}: {
  periodo: string;
  area: AreaDelNegocio;
  gastos: Gasto[];
  personas: Persona[];
}) {
  const columns = useMemo<GridColumn[]>(
    () => [
      {
        key: "concepto",
        header: "Concepto",
        kind: "text",
        required: true,
        width: "min-w-64",
        placeholder:
          area === "FABRICA" ? "Alquiler de la fábrica" : "Alquiler del local",
      },
      {
        key: "categoria",
        header: "Categoría",
        kind: "select",
        required: true,
        width: "min-w-44",
        options: EXPENSE_CATEGORIES.map((code) => ({
          value: code,
          label: expenseCategoryLabel(code),
        })),
      },
      {
        key: "monto",
        header: "Monto del mes (ARS)",
        kind: "decimal",
        width: "min-w-40",
        placeholder: "Pendiente",
        validate: (value, { original, isNew }) =>
          !isNew && original !== "" && value === ""
            ? "Un monto cargado no se puede vaciar."
            : null,
      },
      {
        key: "persona",
        header: "Persona",
        kind: "select",
        emptyLabel: "Sin indicar",
        width: "min-w-40",
        options: personas.map((persona) => ({
          value: persona.codigo,
          label: persona.activo
            ? persona.nombre
            : `${persona.nombre} (inactiva)`,
        })),
      },
      { key: "nota_fuente", header: "Nota", kind: "text", width: "min-w-56" },
    ],
    [personas, area],
  );

  const rows = useMemo<GridRow[]>(
    () =>
      gastos.map((gasto) => ({
        id: gasto.codigo,
        name: gasto.concepto,
        warn: gasto.monto_ars_del_mes === null,
        label: <span className="text-sm text-muted">{gasto.codigo}</span>,
        cells: {
          concepto: gasto.concepto,
          categoria: gasto.categoria,
          monto: decimalInputText(gasto.monto_ars_del_mes),
          persona: gasto.persona ?? "",
          nota_fuente: gasto.nota_fuente ?? "",
        },
        extras: [
          <span key="estado" className="flex flex-wrap gap-1.5">
            {gasto.monto_ars_del_mes === null ? (
              <Badge tone="warn">Pendiente de monto</Badge>
            ) : null}
            {gasto.ficticio ? <Badge tone="warn">Ficticio</Badge> : null}
            {gasto.reemplaza_a ? (
              <Badge title="Este monto reemplaza al anterior, que quedó en el historial.">
                Corrige a {gasto.reemplaza_a}
              </Badge>
            ) : null}
            {gasto.monto_ars_del_mes !== null &&
            !gasto.ficticio &&
            !gasto.reemplaza_a ? (
              <span className="text-muted">—</span>
            ) : null}
          </span>,
        ],
      })),
    [gastos],
  );

  function onSave(save: GridSave) {
    return guardarGastosLote(
      periodo,
      save.changes.map((change) => ({
        codigo: change.id,
        valores: Object.fromEntries(
          change.changed.map((key) => [key, change.cells[key] ?? ""]),
        ),
      })),
      save.added.map((fila) => ({ ...fila, fabrica_o_tienda: area })),
      save.deleted,
    );
  }

  return (
    <EditableGrid
      label={`Costos de ${AREA_TEXT[area]} de ${formatPeriod(periodo)}`}
      rowHeader="Código"
      columns={columns}
      extraHeaders={["Estado"]}
      rows={rows}
      noun={{ one: "costo", many: "costos" }}
      allowNew
      startWithDraft={false}
      addLabel="Agregar costo"
      newRowLabel="Costo nuevo"
      allowDelete
      onSave={onSave}
    />
  );
}
