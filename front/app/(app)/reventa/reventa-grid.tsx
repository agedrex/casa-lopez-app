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
import { decimalInputText, parseDecimalInput } from "@/lib/format";
import type { ProductoReventa } from "@/lib/types";
import { guardarReventaLote } from "./actions";

const NOUN = { one: "producto", many: "productos" };

function costColumn(): GridColumn {
  return {
    key: "costo",
    header: "Costo unitario",
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

/**
 * The merchandise as a sheet. Name, category, unit cost and supplier are edited in place and saved
 * on leaving the cell; a changed cost becomes a price update in the history (nothing is overwritten).
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
      costColumn(),
      {
        key: "proveedor",
        header: "Proveedor",
        kind: "text",
        width: "min-w-44",
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
            },
          };
        }),
    [productos],
  );

  function onSave(save: GridSave) {
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
      rowHeader="ID"
      columns={columns}
      rows={rows}
      noun={NOUN}
      allowNew
      startWithDraft={false}
      compact
      fitContent
      fitFrame
      addLabel="Agregar producto"
      newRowLabel="Producto nuevo"
      onSave={onSave}
    />
  );
}
