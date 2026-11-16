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
import { filasParaGuardar, MONEDAS, UNIDADES } from "@/lib/proveedores";
import type { ProveedorProducto } from "@/lib/types";
import { guardarProductosDeProveedor } from "./productos-actions";

const NOUN = { one: "producto", many: "productos" };
const NEW_ROW_DEFAULTS = { moneda: "ARS" };

export type MaterialOpcion = { codigo: string; label: string };

/**
 * What else the supplier offers, as a sheet: product, material (optional), unit and price per unit.
 * A changed row is saved as a new dated version (the old price stays in the history); a new product
 * is added with the button at the end. It is a reference: it never creates a material price.
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
        placeholder: "Nombre del producto",
      },
      {
        key: "material",
        header: "Material",
        kind: "select",
        emptyLabel: "Otro producto (sin material)",
        width: "min-w-48",
        options: materiales.map((material) => ({
          value: material.codigo,
          label: material.label,
        })),
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
        key: "precio_referencial",
        header: "Precio por unidad",
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
          // Always the price of one unit (an old row with a quantity is shown divided; saving it keeps that unit price).
          precio_referencial: decimalInputText(producto.precio_por_unidad),
          moneda: producto.moneda,
          material: producto.material ?? "",
        },
        extras: [
          formatDate(producto.vigente_desde),
          producto.precio_anterior
            ? formatMoney(producto.precio_anterior, producto.moneda)
            : "—",
        ],
      })),
    [productos],
  );

  function onSave(save: GridSave) {
    return guardarProductosDeProveedor(
      codigo,
      filasParaGuardar(save, productos),
    );
  }

  return (
    <EditableGrid
      label="Productos que vende el proveedor"
      rowHeader="Código"
      columns={columns}
      extraHeaders={["Vigente desde", "Precio anterior"]}
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
