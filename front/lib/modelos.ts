// Fields and closed lists of the Modelos tab. The API validates every value; this only
// decides what the forms offer and how a code is worded.
export const SIZES = [
  { value: "CHICO", label: "Chico" },
  { value: "MEDIANO", label: "Mediano" },
  { value: "GRANDE", label: "Grande" },
] as const;

export const ORIGINS = [
  { value: "EXCEL", label: "Excel viejo" },
  { value: "MOLDE", label: "Moldes" },
  { value: "ESTIMADO", label: "Estimado" },
  { value: "MEDIDO", label: "Medido" },
] as const;

export function sizeLabel(code: string | null): string {
  return SIZES.find((item) => item.value === code)?.label ?? "—";
}

export function originLabel(code: string | null): string {
  return ORIGINS.find((item) => item.value === code)?.label ?? "—";
}

export type ConsumptionField = {
  name:
    | "cuero_m2_por_unidad"
    | "forro_m2_por_unidad"
    | "flex_m2_por_unidad"
    | "goma_eva_m2_por_unidad"
    | "herrajes_usd_por_unidad"
    | "hilo_y_cemento"
    | "confeccion_estimada_ars"
    | "horas_de_confeccion";
  label: string;
  unit: string;
  required?: boolean;
};

export const CONSUMPTION_FIELDS: ConsumptionField[] = [
  { name: "cuero_m2_por_unidad", label: "Cuero", unit: "m²", required: true },
  { name: "forro_m2_por_unidad", label: "Forro", unit: "m²" },
  { name: "flex_m2_por_unidad", label: "Flex", unit: "m²" },
  { name: "goma_eva_m2_por_unidad", label: "Goma EVA", unit: "m²" },
  { name: "herrajes_usd_por_unidad", label: "Herrajes", unit: "USD" },
  { name: "hilo_y_cemento", label: "Hilo y cemento", unit: "juegos" },
  {
    name: "confeccion_estimada_ars",
    label: "Confección estimada",
    unit: "ARS",
  },
  { name: "horas_de_confeccion", label: "Horas de confección", unit: "horas" },
];
