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
import { formatArs, formatDate, formatQuantity, todayIso } from "@/lib/format";
import { diasDelLote } from "@/lib/lote-estados";
import { nombreDeLote } from "@/lib/lotes";
import type { OrdenResumen } from "@/lib/types";

// A grid with no editable column: a lot is opened to change anything in it.
const NO_COLUMNS: GridColumn[] = [];

async function readOnly(): Promise<FormState> {
  return error("Los lotes se editan desde la página de cada lote.");
}

/**
 * The lots sheet, in the same grid as the models: one lot per row (named "code · date"), a click on the row
 * opens the lot. Read only. The admin sees creation and delivery dates, the days it has taken, units, costs and
 * warnings (the taller has its own cards, with no money). Every amount comes calculated by the API.
 */
export function LotesGrid({ ordenes }: { ordenes: OrdenResumen[] }) {
  const rows = useMemo<GridRow[]>(() => {
    const hoy = todayIso();
    return ordenes.map((orden) => {
      const nombre = nombreDeLote(orden.codigo, orden.fecha_de_envio);
      const href = `/fabricacion/${encodeURIComponent(orden.codigo)}`;
      const link = (text: string, className: string) => (
        <Link
          href={href}
          className={`block font-medium underline decoration-gold underline-offset-4 ${className}`}
        >
          {text}
        </Link>
      );
      const unidades = (suffix: string) => (
        <span key="unidades" className="block text-right tabular-nums">
          {formatQuantity(orden.unidades)}
          {suffix}
        </span>
      );
      return {
        id: orden.codigo,
        name: nombre,
        href,
        label: <div className="min-w-44">{link(nombre, "")}</div>,
        cells: {},
        extrasBefore: [
          whereText(orden),
          formatDate(orden.fecha_de_envio),
          formatDate(orden.fecha_de_entrega),
          <span key="dias" className="block text-right tabular-nums">
            {diasDelLote(orden, hoy)}
          </span>,
          <LotStateBadge key="estado" estado={orden.estado} />,
          <span key="productos" className="block text-right tabular-nums">
            {orden.productos}
          </span>,
          unidades(""),
          <span key="costo" className="block text-right tabular-nums">
            {formatArs(orden.costo_total)}
          </span>,
          <span key="unitario" className="block text-right tabular-nums">
            {formatArs(orden.costo_promedio_por_unidad)}
          </span>,
          <Avisos key="avisos" avisos={orden.avisos} />,
        ],
      };
    });
  }, [ordenes]);

  return (
    <EditableGrid
      label="Lotes"
      rowHeader="Lote"
      columns={NO_COLUMNS}
      extraHeadersBefore={[
        "Fabricación",
        "Creado",
        "Entrega",
        "Días",
        "Estado",
        "Productos",
        "Unidades",
        "Costo del lote",
        "Costo por unidad",
        "Avisos",
      ]}
      rows={rows}
      noun={{ one: "lote", many: "lotes" }}
      compact
      fitContent
      fitFrame
      onSave={readOnly}
    />
  );
}
