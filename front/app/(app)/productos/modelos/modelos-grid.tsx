"use client";

import Link from "next/link";
import { useMemo } from "react";
import {
  EditableGrid,
  type GridColumn,
  type GridRow,
  type GridSave,
} from "@/components/editable-grid";
import { Badge, Notice } from "@/components/ui";
import { decimalInputText } from "@/lib/format";
import {
  CONSUMPTION_FIELDS,
  hasMissingConsumptions,
  sizeLabel,
} from "@/lib/modelos";
import type { ModeloLista } from "@/lib/types";
import { guardarConsumosLote } from "./actions";

/**
 * The models sheet, kept simple: model, validation and hours. The other consumptions are edited
 * in each model's page. Rows with missing consumptions are highlighted. Nothing is computed here.
 */
export function ModelosGrid({ modelos }: { modelos: ModeloLista[] }) {
  const columns = useMemo<GridColumn[]>(
    () => [
      {
        key: "horas_de_confeccion",
        header: "Horas",
        kind: "decimal",
        required: CONSUMPTION_FIELDS.find(
          (field) => field.name === "horas_de_confeccion",
        )?.required,
        width: "min-w-28",
      },
    ],
    [],
  );

  const byCode = useMemo(
    () => new Map(modelos.map((modelo) => [modelo.codigo, modelo])),
    [modelos],
  );

  const rows = useMemo<GridRow[]>(
    () =>
      modelos.map((modelo) => {
        const missing = hasMissingConsumptions(modelo);
        const cells: Record<string, string> = {
          horas_de_confeccion: decimalInputText(modelo.horas_de_confeccion),
        };
        return {
          id: modelo.codigo,
          name: modelo.nombre_del_modelo,
          warn: missing,
          label: (
            <div className="min-w-48 max-w-72">
              <Link
                href={`/productos/modelos/${encodeURIComponent(modelo.codigo)}`}
                className="underline decoration-gold underline-offset-4"
              >
                {modelo.nombre_del_modelo}
              </Link>
              <span className="block text-sm text-muted sm:text-xs">
                {modelo.codigo}
                {modelo.categoria ? ` · ${modelo.categoria}` : ""}
                {modelo.tamano ? ` · ${sizeLabel(modelo.tamano)}` : ""}
              </span>
              {missing ? (
                <Badge tone="warn" title="Algún consumo está vacío.">
                  Faltan datos
                </Badge>
              ) : null}
            </div>
          ),
          cells,
          extras: [
            <Badge key="validado" tone={modelo.validado ? "good" : "neutral"}>
              {modelo.validado ? "Validado" : "Sin validar"}
            </Badge>,
          ],
        };
      }),
    [modelos],
  );

  function onSave(save: GridSave) {
    return guardarConsumosLote(
      save.changes.map((change) => {
        const modelo = byCode.get(change.id);
        // The API takes every field of every row: the hidden ones go as they are today.
        const cells: Record<string, string> = {};
        if (modelo) {
          cells.forro = modelo.forro ?? "";
          cells.origen_de_los_consumos = modelo.origen_de_los_consumos ?? "";
          for (const field of CONSUMPTION_FIELDS) {
            cells[field.name] = decimalInputText(modelo[field.name]);
          }
        }
        return {
          codigo: change.id,
          nombre: modelo?.nombre_del_modelo ?? change.id,
          cells: { ...cells, ...change.cells },
        };
      }),
    );
  }

  function warning(save: GridSave): string | null {
    const validated = save.changes.filter(
      (change) => byCode.get(change.id)?.validado,
    ).length;
    if (validated === 0) return null;
    return validated === 1
      ? "1 de los modelos modificados está validado y va a quedar sin validar."
      : `${validated} de los modelos modificados están validados y van a quedar sin validar.`;
  }

  return (
    <EditableGrid
      label="Consumos por modelo"
      rowHeader="Modelo"
      columns={columns}
      extraHeaders={["Validación"]}
      rows={rows}
      noun={{ one: "modelo", many: "modelos" }}
      warning={warning}
      autoSave
      fitContent
      onSave={onSave}
    />
  );
}
