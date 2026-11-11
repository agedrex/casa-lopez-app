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
  formatArs,
  formatPeriod,
} from "@/lib/format";
import type { Gasto, Persona } from "@/lib/types";
import { guardarGastosLote } from "./actions";

/**
 * The month's expenses as a sheet. Concept, area, category and amount are edited in the cell;
 * person and note can only be set on new rows. The totals shown are the ones the API sent.
 */
export function CostosGrid({
  periodo,
  gastos,
  personas,
  area,
  totales,
}: {
  periodo: string;
  gastos: Gasto[];
  personas: Persona[];
  /** Area filter in the page ("FABRICA", "TIENDA" or ""): new rows start in that area. */
  area: string;
  totales: { fabrica: string; tienda: string; total: string };
}) {
  const columns = useMemo<GridColumn[]>(
    () => [
      {
        key: "concepto",
        header: "Concepto",
        kind: "text",
        required: true,
        width: "min-w-64",
        placeholder: "Alquiler de la fábrica",
      },
      {
        key: "fabrica_o_tienda",
        header: "Es de",
        kind: "select",
        required: true,
        width: "min-w-32",
        options: [
          { value: "FABRICA", label: "Fábrica" },
          { value: "TIENDA", label: "Tienda" },
        ],
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
        newOnly: true,
        emptyLabel: "Sin indicar",
        width: "min-w-40",
        options: personas.map((persona) => ({
          value: persona.codigo,
          label: persona.activo
            ? persona.nombre
            : `${persona.nombre} (inactiva)`,
        })),
      },
      {
        key: "nota_fuente",
        header: "Nota o fuente",
        kind: "text",
        newOnly: true,
        width: "min-w-56",
      },
    ],
    [personas],
  );

  const defaults = useMemo(
    () => ({ fabrica_o_tienda: area, categoria: "" }),
    [area],
  );

  const byCode = useMemo(
    () => new Map(gastos.map((gasto) => [gasto.codigo, gasto])),
    [gastos],
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
          fabrica_o_tienda: gasto.fabrica_o_tienda,
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
      save.added,
    );
  }

  function warning(save: GridSave): string | null {
    const corrections = save.changes.filter((change) => {
      const gasto = byCode.get(change.id);
      return (
        change.changed.includes("monto") &&
        gasto !== undefined &&
        gasto.monto_ars_del_mes !== null
      );
    }).length;
    if (corrections === 0) return null;
    return corrections === 1
      ? "1 monto cargado va a quedar como corrección: el anterior se conserva en el historial."
      : `${corrections} montos cargados van a quedar como correcciones: los anteriores se conservan en el historial.`;
  }

  return (
    <EditableGrid
      label={`Gastos de ${formatPeriod(periodo)}`}
      rowHeader="Código"
      columns={columns}
      extraHeaders={["Estado"]}
      rows={rows}
      noun={{ one: "gasto", many: "gastos" }}
      allowNew
      newRowDefaults={defaults}
      newRowLabel="Gasto nuevo"
      warning={warning}
      onSave={onSave}
      note={
        <p className="text-sm text-muted">
          Cambiar el monto de un gasto que ya lo tiene crea una corrección y
          conserva el historial: el monto anterior no se pisa ni se borra. Un
          gasto sin monto queda pendiente y no entra en los totales. Guarde
          antes de cambiar de período o de filtro.
        </p>
      }
      footer={
        <div className="space-y-1">
          <dl className="flex flex-wrap gap-x-8 gap-y-1 text-sm">
            <div className="flex gap-2">
              <dt className="text-muted">Total fábrica</dt>
              <dd className="font-bold tabular-nums">
                {formatArs(totales.fabrica)}
              </dd>
            </div>
            <div className="flex gap-2">
              <dt className="text-muted">Total tienda</dt>
              <dd className="font-bold tabular-nums">
                {formatArs(totales.tienda)}
              </dd>
            </div>
            <div className="flex gap-2">
              <dt className="text-muted">Total del mes</dt>
              <dd className="font-bold tabular-nums">
                {formatArs(totales.total)}
              </dd>
            </div>
          </dl>
          <p className="text-xs text-muted">
            Los totales los calcula la aplicación y se actualizan al guardar.
          </p>
        </div>
      }
    />
  );
}
