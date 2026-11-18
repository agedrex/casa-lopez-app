// What the "Consumo" block of the product page shows. Display only: no arithmetic, no money is
// calculated here (the amount of hilo y cemento is the one the engine put in the quote of today).
import { formatArs, formatQuantity, stageLabel } from "./format";
import { cubiertoPorInsumos } from "./formulario-insumos";
import type { Ficha, LineaReceta, ModeloDetalle } from "./types";

export type ConsumoRow = {
  insumo: string;
  porUnidad: string;
  material: string;
};

const MISSING = "Falta el dato";
const BY_INSUMOS = "Según los insumos";

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
  // Validating a sheet saves herrajes / hilo y cemento as supplies (the Material column lists them) and those replace the
  // single amount in the cost, so an empty amount is not missing data when the model has supplies of that stage.
  const insumos = modelo.insumos ?? [];
  const qty = (
    value: string | null | undefined,
    unit: string,
    field?: string,
  ) =>
    value === null || value === undefined
      ? field && cubiertoPorInsumos(field, insumos)
        ? BY_INSUMOS
        : MISSING
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
      porUnidad: qty(
        modelo.herrajes_usd_por_unidad,
        "USD",
        "herrajes_usd_por_unidad",
      ),
      material: materialsOf("HERRAJES", ficha, modelo),
    },
    {
      insumo: "Hilo y cemento",
      porUnidad:
        modelo.hilo_y_cemento == null &&
        cubiertoPorInsumos("hilo_y_cemento", insumos)
          ? BY_INSUMOS
          : hiloArs
            ? formatArs(hiloArs)
            : "—",
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

/**
 * The margin typed in the price block of the product sheet (a percentage over the price, one decimal at most, below 100):
 * `30`, `30,5` or `30.5` give `"30"` / `"30.5"` for the API; anything else is null. Text only, no arithmetic.
 */
export function parseMargenParam(
  raw: string | null | undefined,
): string | null {
  const match = /^(\d{1,2})(?:[.,](\d))?$/.exec((raw ?? "").trim());
  if (!match) return null;
  return match[2] === undefined ? match[1] : `${match[1]}.${match[2]}`;
}
