"use client";

import Link from "next/link";
import { useMemo } from "react";
import { Avisos } from "@/components/avisos";
import {
  EditableGrid,
  type GridColumn,
  type GridRow,
} from "@/components/editable-grid";
import { LotStateBadge, whereText } from "@/components/orders-table";
import { error, type FormState } from "@/lib/action-state";
import { formatArs, formatDate, formatQuantity } from "@/lib/format";
import { nombreDeLote } from "@/lib/lotes";
import { collapseSpaces } from "@/lib/productos";
import type { OrdenResumen, Renglon } from "@/lib/types";

// A grid with no editable column: a lot is opened to change anything in it.
const NO_COLUMNS: GridColumn[] = [];

async function readOnly(): Promise<FormState> {
  return error("Los lotes se editan desde la página de cada lote.");
}

/** What to make in a lot (taller view): the product and how many, each linked to its sheet. */
function QueHacer({ renglones }: { renglones: Renglon[] | undefined }) {
  if (!renglones || renglones.length === 0) {
    return <span className="text-muted">—</span>;
  }
  return (
    <ul className="min-w-56 max-w-80 space-y-1">
      {renglones.map((item) => (
        <li
          key={item.codigo}
          className="flex items-baseline justify-between gap-3"
        >
          <Link
            href={`/productos/${encodeURIComponent(item.producto)}`}
            className="line-clamp-2 break-words underline decoration-gold underline-offset-4"
          >
            {collapseSpaces(item.producto_nombre)}
          </Link>
          <span className="shrink-0 tabular-nums">
            {formatQuantity(item.cantidad)} u.
          </span>
        </li>
      ))}
    </ul>
  );
}

/**
 * The lots sheet, in the same grid as the models: one lot per row (named "code · date"), a click on the row
 * opens the lot. Read only. The admin sees units, costs and warnings; the taller sees what to make and no
 * money of any kind. Every amount comes calculated by the API.
 */
export function LotesGrid({
  ordenes,
  renglones,
  taller = false,
}: {
  ordenes: OrdenResumen[];
  /** Taller view only: the products of each lot by lot code. */
  renglones?: Record<string, Renglon[]>;
  taller?: boolean;
}) {
  const rows = useMemo<GridRow[]>(
    () =>
      ordenes.map((orden) => {
        const nombre = nombreDeLote(orden.codigo, orden.fecha_de_envio);
        const href = `/fabricacion/${encodeURIComponent(orden.codigo)}`;
        return {
          id: orden.codigo,
          name: nombre,
          href,
          label: (
            <div className="min-w-44">
              <Link
                href={href}
                className="block font-medium underline decoration-gold underline-offset-4"
              >
                {nombre}
              </Link>
            </div>
          ),
          cells: {},
          extrasBefore: [
            whereText(orden),
            formatDate(orden.fecha_de_envio),
            formatDate(orden.fecha_de_entrega),
            <LotStateBadge key="estado" estado={orden.estado} />,
            ...(taller
              ? [<QueHacer key="que" renglones={renglones?.[orden.codigo]} />]
              : [
                  <span
                    key="productos"
                    className="block text-right tabular-nums"
                  >
                    {orden.productos}
                  </span>,
                  <span
                    key="unidades"
                    className="block text-right tabular-nums"
                  >
                    {formatQuantity(orden.unidades)}
                  </span>,
                  <span key="costo" className="block text-right tabular-nums">
                    {formatArs(orden.costo_total)}
                  </span>,
                  <span
                    key="unitario"
                    className="block text-right tabular-nums"
                  >
                    {formatArs(orden.costo_promedio_por_unidad)}
                  </span>,
                  <Avisos key="avisos" avisos={orden.avisos} />,
                ]),
          ],
        };
      }),
    [ordenes, renglones, taller],
  );

  return (
    <EditableGrid
      label="Lotes"
      rowHeader="Lote"
      columns={NO_COLUMNS}
      extraHeadersBefore={[
        "Dónde",
        "Envío",
        "Entrega",
        "Estado",
        ...(taller
          ? ["Qué hay que hacer"]
          : [
              "Productos",
              "Unidades",
              "Costo del lote",
              "Costo por unidad",
              "Avisos",
            ]),
      ]}
      rows={rows}
      noun={{ one: "lote", many: "lotes" }}
      compact
      fitContent
      onSave={readOnly}
    />
  );
}
