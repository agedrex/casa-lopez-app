// What the "Consumo" block of the product page shows. Display only: no arithmetic, no money is
// calculated here (the amount of hilo y cemento is the one the engine put in the quote of today).
import { formatArs, formatQuantity, stageLabel } from "./format";
import type { Ficha, LineaReceta, ModeloDetalle } from "./types";

export type ConsumoRow = {
  insumo: string;
  porUnidad: string;
  material: string;
};

const MISSING = "Falta el dato";

/** The material as a person reads it: its name; the code only when the API has no name for it. */
function materialName(line: LineaReceta): string {
  return line.material_nombre?.trim() || line.material;
}

function materialsOf(
  stage: string,
  ficha: Ficha,
  modelo: ModeloDetalle | null,
): string {
  const fromRecipe = ficha.receta
    .filter((line) => line.etapa === stage)
    .map(materialName);
  const fromInsumos = (modelo?.insumos ?? [])
    .filter((insumo) => insumo.etapa === stage)
    .map((insumo) => insumo.nombre?.trim() || insumo.material);
  const all = [...fromRecipe, ...fromInsumos];
  if (stage === "CUERO" && ficha.cuero && fromRecipe.length === 0) {
    all.unshift(ficha.cuero_nombre?.trim() || ficha.cuero);
  }
  return all.length > 0 ? Array.from(new Set(all)).join(", ") : "—";
}

/** The model hours are information about the product, not part of the cost. */
export function hoursRow(ficha: Ficha): ConsumoRow {
  const hours = ficha.horas_de_confeccion;
  return {
    insumo: "Horas de confección",
    porUnidad:
      hours === null || hours === undefined
        ? MISSING
        : `${formatQuantity(hours)} h`,
    material: "Informativo: no entra en el costo",
  };
}

export function consumoRows(
  ficha: Ficha,
  modelo: ModeloDetalle | null,
): ConsumoRow[] {
  // Without access to the model (taller role) only the recipe lines are known.
  if (modelo === null) {
    return [
      ...ficha.receta.map((line) => ({
        insumo: stageLabel(line.etapa),
        porUnidad: formatQuantity(line.consumo),
        material: materialName(line),
      })),
      hoursRow(ficha),
    ];
  }
  const qty = (value: string | null | undefined, unit: string) =>
    value === null || value === undefined
      ? MISSING
      : `${formatQuantity(value)} ${unit}`;
  // Hilo y cemento is fixed at 1 USD, so its price in pesos is the dollar of today (no arithmetic).
  const hiloArs = ficha.costo_hoy?.dolar;
  return [
    {
      insumo: "Cuero",
      porUnidad: qty(modelo.cuero_m2_por_unidad, "m²"),
      material: materialsOf("CUERO", ficha, modelo),
    },
    {
      insumo: "Forro",
      porUnidad: qty(modelo.forro_m2_por_unidad, "m²"),
      material: materialsOf("FORRO", ficha, modelo),
    },
    {
      insumo: "Flex",
      porUnidad: qty(modelo.flex_m2_por_unidad, "m²"),
      material: materialsOf("FLEX", ficha, modelo),
    },
    {
      insumo: "Goma EVA",
      porUnidad: qty(modelo.goma_eva_m2_por_unidad, "m²"),
      material: materialsOf("GOMA_EVA", ficha, modelo),
    },
    {
      insumo: "Herrajes",
      porUnidad: qty(modelo.herrajes_usd_por_unidad, "USD"),
      material: materialsOf("HERRAJES", ficha, modelo),
    },
    {
      insumo: "Hilo y cemento",
      porUnidad: hiloArs ? formatArs(hiloArs) : "—",
      material: materialsOf("HILO_CEMENTO", ficha, modelo),
    },
    hoursRow(ficha),
  ];
}

/** "Modelo · cuero · color" of the page header, with names instead of codes. */
export function fichaSubtitle(ficha: Ficha): string {
  return [
    ficha.modelo_nombre?.trim() || ficha.modelo,
    ficha.cuero_nombre?.trim() || ficha.cuero,
    ficha.color,
  ]
    .filter(Boolean)
    .join(" · ");
}
