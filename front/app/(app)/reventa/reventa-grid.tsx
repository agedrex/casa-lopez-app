"use client";

import Link from "next/link";
import { useMemo } from "react";
import {
  EditableGrid,
  type GridColumn,
  type GridRow,
  type GridSave,
} from "@/components/editable-grid";
import { Badge } from "@/components/ui";
import { error } from "@/lib/action-state";
import {
  decimalInputText,
  formatArs,
  formatDate,
  parseDecimalInput,
} from "@/lib/format";
import type { ProductoReventa } from "@/lib/types";
import { guardarReventaLote } from "./actions";
import { formatMargenPct } from "./margen";

const NOUN = { one: "producto", many: "productos" };

function amountColumn(key: string, header: string): GridColumn {
  return {
    key,
    header,
    kind: "decimal",
    width: "min-w-40",
    placeholder: "Pendiente",
    validate: (value, { original, isNew }) => {
      if (!isNew && original !== "" && value === "") {
        return "Un valor cargado no se puede vaciar.";
      }
      return value !== "" && !/[1-9]/.test(parseDecimalInput(value) ?? "")
        ? "Tiene que ser mayor que cero."
        : null;
    },
  };
}

const MISSING_COST =
  "cargue el costo de compra para poder guardar el precio de venta o las unidades.";

/**
 * The merchandise as a sheet. Name, category, supplier, cost and sale price are edited in place;
 * a changed cost or price becomes a price update in the history. Margins are the API's.
 */
export function ReventaGrid({
  productos,
  categorias,
}: {
  productos: ProductoReventa[];
  categorias: string[];
}) {
  const columns = useMemo<GridColumn[]>(
    () => [
      {
        key: "nombre",
        header: "Producto",
        kind: "text",
        required: true,
        width: "min-w-64",
        placeholder: "Billetera de cuero",
      },
      {
        key: "categoria",
        header: "Categoría",
        kind: "select",
        emptyLabel: "Sin categoría",
        width: "min-w-40",
        options: categorias.map((categoria) => ({
          value: categoria,
          label: categoria,
        })),
      },
      {
        key: "proveedor",
        header: "Proveedor",
        kind: "text",
        width: "min-w-44",
      },
      amountColumn("costo", "Costo (ARS)"),
      amountColumn("precio_venta", "Precio de venta (ARS)"),
      {
        key: "unidades",
        header: "Unidades compradas",
        kind: "decimal",
        newOnly: true,
        width: "min-w-36",
        placeholder: "Opcional",
      },
    ],
    [categorias],
  );

  const rows = useMemo<GridRow[]>(
    () =>
      productos
        .filter((producto) => producto.activo)
        .map((producto) => {
          const sinCosto = producto.costo_unitario_ars === null;
          return {
            id: producto.codigo,
            name: producto.nombre,
            warn: sinCosto,
            label: (
              <span className="flex flex-wrap items-center gap-1.5">
                <Link
                  href={`/reventa/${encodeURIComponent(producto.codigo)}`}
                  className="text-sm underline decoration-gold underline-offset-4"
                >
                  {producto.codigo}
                </Link>
                {sinCosto ? <Badge tone="warn">Sin costo</Badge> : null}
              </span>
            ),
            cells: {
              nombre: producto.nombre,
              categoria: producto.categoria ?? "",
              proveedor: producto.proveedor ?? "",
              costo: decimalInputText(producto.costo_unitario_ars),
              precio_venta: decimalInputText(
                producto.precio_venta_unitario_ars,
              ),
            },
            extras: [
              <span key="margen">
                {formatArs(producto.margen_unitario_ars)}
                <span className="block text-xs text-muted">
                  {formatMargenPct(producto.margen_pct)}
                </span>
              </span>,
              formatDate(producto.ultima_compra),
            ],
          };
        }),
    [productos],
  );

  function onSave(save: GridSave) {
    for (const change of save.changes) {
      const name = rows.find((row) => row.id === change.id)?.name ?? change.id;
      if (change.changed.includes("precio_venta") && !change.cells.costo) {
        return Promise.resolve(
          error(`${name}: cargue primero el costo de compra.`),
        );
      }
    }
    for (const [index, fila] of save.added.entries()) {
      if (
        !fila.costo?.trim() &&
        (fila.precio_venta?.trim() || fila.unidades?.trim())
      ) {
        return Promise.resolve(
          error(`Producto nuevo ${index + 1}: ${MISSING_COST}`),
        );
      }
    }
    return guardarReventaLote(
      save.changes.map((change) => ({
        codigo: change.id,
        valores: Object.fromEntries(
          change.changed.map((key) => [key, change.cells[key] ?? ""]),
        ),
      })),
      save.added,
    );
  }

  return (
    <EditableGrid
      label="Productos de mercadería"
      rowHeader="Código"
      columns={columns}
      extraHeaders={["Margen", "Última compra"]}
      rows={rows}
      noun={NOUN}
      allowNew
      newRowLabel="Producto nuevo"
      onSave={onSave}
    />
  );
}
