"use client";

import Link from "next/link";
import { type ReactNode, useMemo } from "react";
import { Avisos } from "@/components/avisos";
import {
  EditableGrid,
  type GridColumn,
  type GridRow,
  type GridSave,
} from "@/components/editable-grid";
import { error } from "@/lib/action-state";
import {
  decimalInputText,
  formatArs,
  formatUsd,
  lifecycleLabel,
  parseDecimalInput,
} from "@/lib/format";
import {
  costoFaltante,
  cotizacionCaption,
  modeloDe,
  SIN_COTIZACION,
  tieneCotizacion,
} from "@/lib/productos";
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

// Column order (demo-staging-taller-grilla S5/S6): Producto + ID | Modelo + ID | costs (quoted, then today) |
// category, state and warnings | Margen % (editable) | Precio neto | Precio final.
const HEADERS_BEFORE = [
  "Modelo",
  "Costo cotizado (ARS)",
  "Costo cotizado (USD)",
  "Costo hoy (ARS)",
  "Costo hoy (USD)",
  "Categoría",
  "Estado",
  "Avisos",
];
const HEADERS_AFTER = ["Precio neto (ARS)", "Precio final (ARS)"];

/**
 * The products as a sheet for the admin. The only editable cell is the margin over the sale price;
 * the net and final prices are the API's (cost of today / (1 - margin), plus the active taxes), so
 * they update after saving. `etiquetas` is the first column of every row, built by the page.
 * The quoted cost is the latest saved quote's total, with the dollar and date it was quoted at.
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
      productos.map((producto) => {
        const modelo = modeloDe(producto);
        const cotizado = tieneCotizacion(producto);
        const sinCosto = producto.costo_hoy_ars === null;
        // Without a cost the first warning is already shown in the cost cell: the rest goes in "Avisos".
        const avisos = sinCosto ? producto.avisos.slice(1) : producto.avisos;
        return {
          id: producto.codigo,
          name: producto.nombre,
          warn: sinCosto,
          label: etiquetas[producto.codigo],
          cells: { margen: decimalInputText(producto.margen_pct) },
          extrasBefore: [
            modelo.nombre || modelo.codigo ? (
              <span key="modelo" className="block max-w-48">
                {modelo.busqueda ? (
                  <Link
                    href={`/productos?q=${encodeURIComponent(modelo.busqueda)}`}
                    title="Ver los productos de este modelo"
                    className="underline decoration-gold underline-offset-4"
                  >
                    {modelo.nombre ?? modelo.codigo}
                  </Link>
                ) : (
                  modelo.nombre
                )}
                {modelo.codigo && modelo.nombre !== modelo.codigo ? (
                  <span className="block text-xs text-muted">
                    {modelo.codigo}
                  </span>
                ) : null}
              </span>
            ) : (
              <span key="modelo" className="text-muted">
                —
              </span>
            ),
            cotizado ? (
              <span key="cot-ars" className="block tabular-nums">
                {formatArs(producto.costo_cotizado_ars)}
                <span className="block text-xs text-muted">
                  {cotizacionCaption(
                    producto.cotizacion_dolar,
                    producto.cotizacion_fecha,
                  )}
                </span>
              </span>
            ) : (
              <span key="cot-ars" className="text-muted">
                {SIN_COTIZACION}
              </span>
            ),
            <span key="cot-usd" className="tabular-nums">
              {cotizado ? formatUsd(producto.costo_cotizado_usd) : "—"}
            </span>,
            sinCosto ? (
              <span key="hoy-ars" className="text-muted">
                {costoFaltante(producto.avisos)}
              </span>
            ) : (
              <span key="hoy-ars" className="tabular-nums">
                {formatArs(producto.costo_hoy_ars)}
              </span>
            ),
            <span key="hoy-usd" className="tabular-nums">
              {sinCosto ? "—" : formatUsd(producto.costo_hoy_usd)}
            </span>,
            <span key="categoria">{producto.categoria ?? "—"}</span>,
            <span key="estado">
              {lifecycleLabel(producto.estado_del_ciclo)}
            </span>,
            <Avisos key="avisos" avisos={avisos} wrap />,
          ],
          extras: [
            <span key="neto" className="tabular-nums">
              {formatArs(producto.precio_venta_ars)}
            </span>,
            <span key="final" className="tabular-nums">
              {formatArs(producto.precio_final_ars)}
            </span>,
          ],
        };
      }),
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
      extraHeadersBefore={HEADERS_BEFORE}
      extraHeaders={HEADERS_AFTER}
      rows={rows}
      noun={NOUN}
      onSave={onSave}
    />
  );
}
