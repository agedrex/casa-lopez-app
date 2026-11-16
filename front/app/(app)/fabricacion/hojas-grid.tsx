"use client";

import Link from "next/link";
import { useMemo } from "react";
import {
  EditableGrid,
  type GridColumn,
  type GridRow,
} from "@/components/editable-grid";
import { Badge } from "@/components/ui";
import { error, type FormState } from "@/lib/action-state";
import { formatDate } from "@/lib/format";
import { ESTADO_TONE, estadoLabel } from "@/lib/formularios";
import type { FormularioResumen } from "@/lib/types";

// A grid with no editable column: the sheet is completed in its own page.
const NO_COLUMNS: GridColumn[] = [];

async function readOnly(): Promise<FormState> {
  return error("La hoja se completa desde su página.");
}

/**
 * The models of the taller (their consumption sheets), in the same grid as the models of the admin: one per row
 * (ID, Modelo, Estado, Creada), a click on the row opens the sheet. Read only.
 */
export function HojasGrid({ hojas }: { hojas: FormularioResumen[] }) {
  const rows = useMemo<GridRow[]>(
    () =>
      hojas.map((hoja) => {
        const href = `/taller/modelos/${encodeURIComponent(hoja.codigo)}`;
        return {
          id: hoja.codigo,
          name: hoja.articulo,
          href,
          // The model's ID; a sheet whose model is not created yet falls back to the sheet's own code.
          label: (
            <Link
              href={href}
              className="block font-medium tabular-nums underline decoration-gold underline-offset-4"
            >
              {hoja.modelo ?? hoja.codigo}
            </Link>
          ),
          cells: {},
          extrasBefore: [
            <span key="modelo" className="block min-w-56 max-w-80">
              {hoja.articulo}
            </span>,
            <Badge key="estado" tone={ESTADO_TONE[hoja.estado]}>
              {estadoLabel(hoja.estado)}
            </Badge>,
            formatDate(hoja.created_at),
          ],
        };
      }),
    [hojas],
  );

  return (
    <EditableGrid
      label="Modelos del taller"
      rowHeader="ID"
      columns={NO_COLUMNS}
      extraHeadersBefore={["Modelo", "Estado", "Creada"]}
      rows={rows}
      noun={{ one: "modelo", many: "modelos" }}
      compact
      fitContent
      fitFrame
      onSave={readOnly}
    />
  );
}
