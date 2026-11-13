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
  ORIGINS,
  sizeLabel,
} from "@/lib/modelos";
import type { ModeloLista } from "@/lib/types";
import { guardarConsumosLote } from "./actions";

export type ForroOption = { codigo: string; label: string };

const HEADERS: Record<string, string> = {
  cuero_m2_por_unidad: "Cuero m²",
  forro_m2_por_unidad: "Forro m²",
  flex_m2_por_unidad: "Flex m²",
  goma_eva_m2_por_unidad: "Goma EVA m²",
  herrajes_usd_por_unidad: "Herrajes USD",
  hilo_y_cemento: "Hilo y cemento",
  confeccion_estimada_ars: "Confección ARS",
  horas_de_confeccion: "Horas",
};

/**
 * The models sheet: one row per model, the consumptions editable in the cell. Empty = missing
 * data, 0 = "no lleva". Rows with missing data are highlighted. Nothing is computed here.
 */
export function ModelosGrid({
  modelos,
  forros,
}: {
  modelos: ModeloLista[];
  forros: ForroOption[];
}) {
  const columns = useMemo<GridColumn[]>(() => {
    const decimal = (name: string): GridColumn => ({
      key: name,
      header: HEADERS[name] ?? name,
      kind: "decimal",
      required: CONSUMPTION_FIELDS.find((field) => field.name === name)
        ?.required,
      width: "min-w-28",
    });
    const forro: GridColumn = {
      key: "forro",
      header: "Forro",
      kind: "select",
      emptyLabel: "Sin forro",
      options: forros.map((item) => ({
        value: item.codigo,
        label: item.label,
      })),
      width: "min-w-48",
    };
    const origen: GridColumn = {
      key: "origen_de_los_consumos",
      header: "Origen",
      kind: "select",
      emptyLabel: "Elegir…",
      required: true,
      options: ORIGINS.map((item) => ({
        value: item.value,
        label: item.label,
      })),
      width: "min-w-36",
    };
    return [
      decimal("cuero_m2_por_unidad"),
      forro,
      decimal("forro_m2_por_unidad"),
      decimal("flex_m2_por_unidad"),
      decimal("goma_eva_m2_por_unidad"),
      decimal("herrajes_usd_por_unidad"),
      decimal("hilo_y_cemento"),
      decimal("confeccion_estimada_ars"),
      decimal("horas_de_confeccion"),
      origen,
    ];
  }, [forros]);

  const byCode = useMemo(
    () => new Map(modelos.map((modelo) => [modelo.codigo, modelo])),
    [modelos],
  );

  const rows = useMemo<GridRow[]>(
    () =>
      modelos.map((modelo) => {
        const missing = hasMissingConsumptions(modelo);
        const cells: Record<string, string> = {
          forro: modelo.forro ?? "",
          origen_de_los_consumos: modelo.origen_de_los_consumos ?? "",
        };
        for (const field of CONSUMPTION_FIELDS) {
          cells[field.name] = decimalInputText(modelo[field.name]);
        }
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
      save.changes.map((change) => ({
        codigo: change.id,
        nombre: byCode.get(change.id)?.nombre_del_modelo ?? change.id,
        cells: change.cells,
      })),
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
      onSave={onSave}
    />
  );
}
