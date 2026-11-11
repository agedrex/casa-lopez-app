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
import { guardarGastosLote } from "./actions";

export type Bloque = "personal" | "servicios" | "otros";

const CATEGORIAS_PERSONAL = ["SUELDOS", "CARGAS_SOCIALES"];

const TITULOS: Record<Bloque, string> = {
  personal: "Mano de obra",
  servicios: "Servicios básicos",
  otros: "Gastos",
};
const NOUN = {
  personal: { one: "pago", many: "pagos" },
  servicios: { one: "servicio", many: "servicios" },
  otros: { one: "gasto", many: "gastos" },
};
const NUEVO: Record<Bloque, string> = {
  personal: "Persona nueva",
  servicios: "Servicio nuevo",
  otros: "Gasto nuevo",
};

const AREAS = [
  { value: "FABRICA", label: "Fábrica" },
  { value: "TIENDA", label: "Tienda" },
];

/**
 * The month's expenses as a sheet. Every cell of a saved row is edited in place and a row can be
 * marked for deletion. The totals shown are the ones the API sent.
 */
export function CostosGrid({
  periodo,
  gastos,
  personas,
  area,
  bloque = "otros",
}: {
  periodo: string;
  gastos: Gasto[];
  personas: Persona[];
  /** Area filter in the page ("FABRICA", "TIENDA" or ""): new rows start in that area. */
  area: string;
  /**
   * `personal` (sueldos y cargas) y `servicios` son grillas cortas para cargar el mes rápido;
   * `otros` es la grilla completa.
   */
  bloque?: Bloque;
}) {
  const columns = useMemo<GridColumn[]>(() => {
    const concepto: GridColumn = {
      key: "concepto",
      header: bloque === "personal" ? "Persona o puesto" : "Concepto",
      kind: "text",
      required: true,
      width: "min-w-64",
      placeholder:
        bloque === "personal"
          ? "Sueldo de Alderete"
          : bloque === "servicios"
            ? "Luz de la fábrica"
            : "Alquiler de la fábrica",
    };
    const lado: GridColumn = {
      key: "fabrica_o_tienda",
      header: "Es de",
      kind: "select",
      required: true,
      width: "min-w-32",
      options: AREAS,
    };
    const monto: GridColumn = {
      key: "monto",
      header: "Monto del mes (ARS)",
      kind: "decimal",
      width: "min-w-40",
      placeholder: "Pendiente",
      validate: (value, { original, isNew }) =>
        !isNew && original !== "" && value === ""
          ? "Un monto cargado no se puede vaciar."
          : null,
    };
    if (bloque === "servicios") {
      return [{ ...concepto, header: "Servicio" }, lado, monto];
    }
    const categoria: GridColumn = {
      key: "categoria",
      header: bloque === "personal" ? "Tipo" : "Categoría",
      kind: "select",
      required: true,
      width: "min-w-44",
      options: (bloque === "personal"
        ? CATEGORIAS_PERSONAL
        : EXPENSE_CATEGORIES.filter(
            (code) =>
              !CATEGORIAS_PERSONAL.includes(code) && code !== "SERVICIOS",
          )
      ).map((code) => ({ value: code, label: expenseCategoryLabel(code) })),
    };
    if (bloque === "personal") return [concepto, categoria, lado, monto];
    return [
      concepto,
      lado,
      categoria,
      monto,
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
    ];
  }, [personas, bloque]);

  const defaults = useMemo(
    () => ({
      fabrica_o_tienda: area,
      categoria:
        bloque === "personal"
          ? "SUELDOS"
          : bloque === "servicios"
            ? "SERVICIOS"
            : "",
    }),
    [area, bloque],
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
        extras:
          bloque !== "otros"
            ? undefined
            : [
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
    [gastos, bloque],
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
      bloque === "servicios"
        ? save.added.map((fila) => ({ ...fila, categoria: "SERVICIOS" }))
        : save.added,
      save.deleted,
    );
  }

  return (
    <EditableGrid
      label={`${TITULOS[bloque]} de ${formatPeriod(periodo)}`}
      rowHeader="Código"
      columns={columns}
      extraHeaders={bloque === "otros" ? ["Estado"] : []}
      rows={rows}
      noun={NOUN[bloque]}
      allowNew={bloque !== "otros"}
      newRowDefaults={defaults}
      newRowLabel={NUEVO[bloque]}
      allowDelete
      autoSave
      compact={bloque !== "otros"}
      onSave={onSave}
    />
  );
}
