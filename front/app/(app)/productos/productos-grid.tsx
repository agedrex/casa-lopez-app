"use client";

import { type ReactNode, useMemo } from "react";
import {
  EditableGrid,
  type GridColumn,
  type GridRow,
  type GridSave,
} from "@/components/editable-grid";
import { error } from "@/lib/action-state";
import { decimalInputText, formatArs, parseDecimalInput } from "@/lib/format";
import { costoFaltante } from "@/lib/productos";
import type { ProductoResumen } from "@/lib/types";
import { guardarMargenesLote } from "./actions";

const NOUN = { one: "producto", many: "productos" };

const MARGEN_AYUDA =
  "Tiene que ser un porcentaje de 0 a 99,9, con un decimal como máximo. Ejemplo: 30 o 32,5.";

const COLUMNS: GridColumn[] = [
  {
    key: "margen",
    header: "Margen %",
    kind: "decimal",
    width: "min-w-28",
    placeholder: "Sin precio",
    validate: (value, { original }) => {
      if (value === "") {
        return original !== "" ? "Un margen cargado no se puede vaciar." : null;
      }
      return /^\d{1,2}(\.\d0*)?$/.test(parseDecimalInput(value) ?? "")
        ? null
        : MARGEN_AYUDA;
    },
  },
];

/**
 * The products as a sheet for the admin. The only editable cell is the margin over the sale price;
 * the net and final prices are the API's (cost of today / (1 - margin), plus the active taxes), so
 * they update after saving. `etiquetas` is the first column of every row, built by the page.
 */
export function ProductosGrid({
  productos,
  etiquetas,
}: {
  productos: ProductoResumen[];
  etiquetas: Record<string, ReactNode>;
}) {
  const rows = useMemo<GridRow[]>(
    () =>
      productos.map((producto) => ({
        id: producto.codigo,
        name: producto.nombre,
        warn: producto.costo_hoy_ars === null,
        label: etiquetas[producto.codigo],
        cells: { margen: decimalInputText(producto.margen_pct) },
        extras: [
          producto.costo_hoy_ars === null ? (
            <span key="costo" className="text-muted">
              {costoFaltante(producto.avisos)}
            </span>
          ) : (
            <span key="costo" className="tabular-nums">
              {formatArs(producto.costo_hoy_ars)}
            </span>
          ),
          <span key="neto" className="tabular-nums">
            {formatArs(producto.precio_venta_ars)}
          </span>,
          <span key="final" className="tabular-nums">
            {formatArs(producto.precio_final_ars)}
          </span>,
        ],
      })),
    [productos, etiquetas],
  );

  function onSave(save: GridSave) {
    for (const change of save.changes) {
      const producto = productos.find(({ codigo }) => codigo === change.id);
      if (producto?.costo_hoy_ars === null) {
        return Promise.resolve(
          error(
            `${producto.nombre}: no tiene costo calculable hoy, así que todavía no se le puede fijar un margen.`,
          ),
        );
      }
    }
    return guardarMargenesLote(
      save.changes.map((change) => ({
        codigo: change.id,
        margen: change.cells.margen ?? "",
      })),
    );
  }

  return (
    <EditableGrid
      label="Productos"
      rowHeader="Producto"
      columns={COLUMNS}
      extraHeaders={[
        "Costo hoy (ARS)",
        "Precio neto (ARS)",
        "Precio final (ARS)",
      ]}
      rows={rows}
      noun={NOUN}
      onSave={onSave}
    />
  );
}
