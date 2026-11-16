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
 * The models of the taller (their consumption sheets), in the same grid as the models of the admin: one per row,
 * a click on the row opens the sheet. Read only.
 */
export function HojasGrid({
  hojas,
  userId,
}: {
  hojas: FormularioResumen[];
  userId: string;
}) {
  const rows = useMemo<GridRow[]>(
    () =>
      hojas.map((hoja) => {
        const href = `/taller/modelos/${encodeURIComponent(hoja.codigo)}`;
        return {
          id: hoja.codigo,
          name: hoja.articulo,
          href,
          label: (
            <div className="min-w-56 max-w-80">
              <Link
                href={href}
                className="block font-medium underline decoration-gold underline-offset-4"
              >
                {hoja.articulo}
              </Link>
              {hoja.creado_por === userId ? (
                <span className="mt-1 block">
                  <Badge>Creado por vos</Badge>
                </span>
              ) : null}
            </div>
          ),
          cells: {},
          extrasBefore: [
            hoja.modelo ?? <span className="text-muted">—</span>,
            <span key="hoja" className="tabular-nums">
              {hoja.codigo}
            </span>,
            <Badge key="estado" tone={ESTADO_TONE[hoja.estado]}>
              {estadoLabel(hoja.estado)}
            </Badge>,
            formatDate(hoja.created_at),
          ],
        };
      }),
    [hojas, userId],
  );

  return (
    <EditableGrid
      label="Modelos del taller"
      rowHeader="Modelo"
      columns={NO_COLUMNS}
      extraHeadersBefore={["ID del modelo", "Hoja", "Estado", "Creada"]}
      rows={rows}
      noun={{ one: "modelo", many: "modelos" }}
      compact
      fitContent
      onSave={readOnly}
    />
  );
}
