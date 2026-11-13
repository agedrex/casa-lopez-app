"use client";

import { useMemo } from "react";
import {
  EditableGrid,
  type GridColumn,
  type GridRow,
  type GridSave,
} from "@/components/editable-grid";
import { Badge } from "@/components/ui";
import { decimalInputText, formatDate, formatMoney } from "@/lib/format";
import { MONEDAS, UNIDADES } from "@/lib/proveedores";
import type { ProveedorProducto } from "@/lib/types";
import { guardarProductosDeProveedor } from "./productos-actions";

const NOUN = { one: "producto", many: "productos" };
const NEW_ROW_DEFAULTS = { moneda: "ARS", iva: "no" };

export type MaterialOpcion = { codigo: string; label: string };

/**
 * What the supplier sells, as a sheet: product, unit, quantity of one presentation and reference
 * price. A changed row is saved as a new dated version (the old price stays in the history);
 * a new product is added with the button at the end. The price per unit is the API's.
 */
export function ProductosQueVende({
  codigo,
  productos,
  materiales,
}: {
  codigo: string;
  productos: ProveedorProducto[];
  materiales: MaterialOpcion[];
}) {
  const columns = useMemo<GridColumn[]>(
    () => [
      {
        key: "nombre",
        header: "Producto",
        kind: "text",
        required: true,
        newOnly: true,
        width: "min-w-64",
        placeholder: "Flex 1 × 1,40",
      },
      {
        key: "unidad",
        header: "Unidad",
        kind: "select",
        required: true,
        width: "min-w-40",
        options: UNIDADES.map((unidad) => ({ ...unidad })),
      },
      {
        key: "cantidad",
        header: "Cantidad",
        kind: "decimal",
        width: "min-w-28",
        placeholder: "Opcional",
        validate: (value) =>
          value !== "" && !/[1-9]/.test(value)
            ? "Tiene que ser mayor que cero."
            : null,
      },
      {
        key: "precio_referencial",
        header: "Precio referencial",
        kind: "decimal",
        required: true,
        width: "min-w-36",
        validate: (value) =>
          !/[1-9]/.test(value) ? "Tiene que ser mayor que cero." : null,
      },
      {
        key: "moneda",
        header: "Moneda",
        kind: "select",
        required: true,
        width: "min-w-24",
        options: MONEDAS.map((moneda) => ({ value: moneda, label: moneda })),
      },
      {
        key: "iva",
        header: "IVA",
        kind: "select",
        width: "min-w-32",
        options: [
          { value: "no", label: "Sin IVA" },
          { value: "si", label: "Con IVA" },
        ],
      },
      {
        key: "material",
        header: "Material",
        kind: "select",
        emptyLabel: "Sin vincular",
        width: "min-w-48",
        options: materiales.map((material) => ({
          value: material.codigo,
          label: material.label,
        })),
      },
    ],
    [materiales],
  );

  const rows = useMemo<GridRow[]>(
    () =>
      productos.map((producto) => ({
        id: producto.codigo,
        name: producto.nombre,
        label: (
          <span className="flex flex-wrap items-center gap-1.5">
            <span className="text-sm">{producto.codigo}</span>
            {producto.cargas > 1 ? (
              <Badge tone="neutral">{producto.cargas} precios cargados</Badge>
            ) : null}
          </span>
        ),
        cells: {
          nombre: producto.nombre,
          unidad: producto.unidad,
          cantidad: decimalInputText(producto.cantidad),
          precio_referencial: decimalInputText(producto.precio_referencial),
          moneda: producto.moneda,
          iva: producto.iva_incluido ? "si" : "no",
          material: producto.material ?? "",
        },
        extras: [
          formatMoney(producto.precio_por_unidad, producto.moneda),
          formatDate(producto.vigente_desde),
        ],
      })),
    [productos],
  );

  function onSave(save: GridSave) {
    // A changed saved row goes complete (the API stores a new version); what the grid does not show is carried over.
    const changed = save.changes.map((change) => ({
      ...change.cells,
      nota: productos.find((p) => p.codigo === change.id)?.nota ?? "",
    }));
    return guardarProductosDeProveedor(codigo, [...changed, ...save.added]);
  }

  return (
    <EditableGrid
      label="Productos que vende el proveedor"
      rowHeader="Código"
      columns={columns}
      extraHeaders={["Precio por unidad", "Vigente desde"]}
      rows={rows}
      noun={NOUN}
      allowNew
      startWithDraft={false}
      addLabel="Agregar producto"
      newRowLabel="Producto nuevo"
      newRowDefaults={NEW_ROW_DEFAULTS}
      onSave={onSave}
    />
  );
}
