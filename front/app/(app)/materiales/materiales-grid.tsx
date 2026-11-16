"use client";

import Link from "next/link";
import { useMemo } from "react";
import {
  EditableGrid,
  type GridColumn,
  type GridRow,
  type GridSave,
} from "@/components/editable-grid";
import { Badge } from "@/components/ui";
import {
  formatDate,
  formatMoney,
  formatQuantity,
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

/**
 * The materials as a sheet, grouped by stage. Prices are NOT edited here: they arrive with each supplier
 * order (Proveedores). A new row is a new material (name, stage and consumption unit are chosen once).
 * The code of each row opens the sheet of the material: its orders, prices and what was received.
 */
export function MaterialesGrid({
  grupos,
  etapas,
  recibido,
}: {
  grupos: GrupoDeMateriales[];
  etapas: string[];
  recibido: Record<string, string>;
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
                <Link
                  href={`/materiales/${encodeURIComponent(material.codigo)}`}
                  className="text-sm underline decoration-gold underline-offset-4"
                >
                  {material.codigo}
                </Link>
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
            },
            extras: [
              precio ? formatMoney(precio.precio, precio.moneda) : "—",
              precio ? formatDate(precio.vigente_desde) : "—",
              recibido[material.codigo]
                ? `${formatQuantity(recibido[material.codigo])} ${material.unidad_de_consumo}`
                : "—",
              preciosPorColor > 0
                ? `${preciosPorColor} ${preciosPorColor === 1 ? "precio" : "precios"} por color`
                : "—",
            ],
          };
        }),
      ),
    [grupos, recibido],
  );

  function onSave(save: GridSave) {
    return guardarMaterialesLote([], save.added);
  }

  return (
    <EditableGrid
      label="Materiales"
      rowHeader="Código"
      columns={columns}
      extraHeaders={["Último precio", "Desde", "Recibido", "Precios por color"]}
      rows={rows}
      noun={NOUN}
      allowNew
      startWithDraft={false}
      addLabel="Agregar material"
      newRowLabel="Material nuevo"
      draftGroup="Materiales nuevos"
      onSave={onSave}
    />
  );
}
