"use client";

import { useMemo } from "react";
import {
  EditableGrid,
  type GridColumn,
  type GridRow,
  type GridSave,
} from "@/components/editable-grid";
import { Badge } from "@/components/ui";
import { error } from "@/lib/action-state";
import {
  decimalInputText,
  formatDate,
  parseDecimalInput,
  stageLabel,
} from "@/lib/format";
import type { GrupoDeMateriales } from "@/lib/materiales";
import { guardarMaterialesLote } from "./actions";

const NOUN = { one: "material", many: "materiales" };

// Labels of the closed list of consumption units (the API checks the value).
const UNIDADES = [
  { value: "m2", label: "m²" },
  { value: "cm", label: "cm" },
  { value: "m", label: "m" },
  { value: "unidad", label: "unidad" },
  { value: "juego", label: "juego" },
  { value: "USD", label: "USD" },
];

// Module level: the grid compares it by reference.
const NEW_ROW_DEFAULTS = { moneda: "ARS" };

const MONEDAS = [
  { value: "ARS", label: "ARS" },
  { value: "USD", label: "USD" },
];

/**
 * The materials as a sheet, grouped by stage. The price, currency and supplier are edited in place:
 * a change is a new dated price in the history (nothing is overwritten). A new row is a new material
 * (name, stage and consumption unit are chosen once, here); a blocked material is read only.
 */
export function MaterialesGrid({
  grupos,
  etapas,
}: {
  grupos: GrupoDeMateriales[];
  etapas: string[];
}) {
  const columns = useMemo<GridColumn[]>(
    () => [
      {
        key: "nombre",
        header: "Material",
        kind: "text",
        newOnly: true,
        required: true,
        width: "min-w-64",
        placeholder: "Cierre metálico 30 cm",
      },
      {
        key: "etapa",
        header: "Etapa",
        kind: "select",
        newOnly: true,
        required: true,
        width: "min-w-36",
        options: etapas.map((etapa) => ({
          value: etapa,
          label: stageLabel(etapa),
        })),
      },
      {
        key: "unidad_de_consumo",
        header: "Unidad de consumo",
        kind: "select",
        newOnly: true,
        required: true,
        width: "min-w-32",
        options: UNIDADES,
      },
      {
        key: "precio",
        header: "Precio",
        kind: "decimal",
        width: "min-w-36",
        placeholder: "Sin precio",
        validate: (value, { original, isNew }) => {
          if (!isNew && original !== "" && value === "") {
            return "Un precio cargado no se puede vaciar.";
          }
          return value !== "" && !/[1-9]/.test(parseDecimalInput(value) ?? "")
            ? "Tiene que ser mayor que cero."
            : null;
        },
      },
      {
        key: "moneda",
        header: "Moneda",
        kind: "select",
        emptyLabel: "—",
        width: "min-w-24",
        options: MONEDAS,
      },
      {
        key: "proveedor",
        header: "Proveedor",
        kind: "text",
        width: "min-w-44",
      },
    ],
    [etapas],
  );

  const rows = useMemo<GridRow[]>(
    () =>
      grupos.flatMap((grupo) =>
        grupo.filas.map(({ material, precio, preciosPorColor }) => {
          const sinPrecio = material.cotizable && !precio;
          return {
            id: material.codigo,
            name: material.nombre,
            group: stageLabel(grupo.etapa),
            readOnly: !material.cotizable,
            warn: sinPrecio,
            label: (
              <span className="flex flex-wrap items-center gap-1.5">
                <span className="text-sm">{material.codigo}</span>
                {!material.cotizable ? (
                  <Badge tone="alert">No cotizable</Badge>
                ) : sinPrecio ? (
                  <Badge tone="warn">Sin precio</Badge>
                ) : null}
              </span>
            ),
            cells: {
              nombre: material.nombre,
              etapa: material.etapa,
              unidad_de_consumo: material.unidad_de_consumo,
              precio: decimalInputText(precio?.precio),
              moneda: precio?.moneda ?? "",
              proveedor: precio?.proveedor ?? "",
            },
            extras: [
              precio ? formatDate(precio.vigente_desde) : "—",
              preciosPorColor > 0
                ? `${preciosPorColor} ${preciosPorColor === 1 ? "precio" : "precios"} por color`
                : "—",
            ],
          };
        }),
      ),
    [grupos],
  );

  function onSave(save: GridSave) {
    for (const change of save.changes) {
      const name = rows.find((row) => row.id === change.id)?.name ?? change.id;
      const current = rows.find((row) => row.id === change.id)?.cells;
      if (!change.cells.precio?.trim()) {
        return Promise.resolve(error(`${name}: cargue el precio.`));
      }
      if (!change.cells.moneda && current?.precio === "") {
        return Promise.resolve(
          error(`${name}: elija la moneda del primer precio.`),
        );
      }
    }
    return guardarMaterialesLote(
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
      label="Materiales y precios"
      rowHeader="Código"
      columns={columns}
      extraHeaders={["Precio desde", "Precios por color"]}
      rows={rows}
      noun={NOUN}
      allowNew
      startWithDraft={false}
      addLabel="Agregar material"
      newRowLabel="Material nuevo"
      draftGroup="Materiales nuevos"
      newRowDefaults={NEW_ROW_DEFAULTS}
      onSave={onSave}
    />
  );
}
