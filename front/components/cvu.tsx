import type { VeredictoCvu } from "@/lib/types";
import { Badge } from "./ui";

// Copy for the codes the API sends. Mapping a code to a sentence is text, not calculation.
// SUPUESTO: validar con Gerardo/Alejandro; MC_BAJO depends on a threshold that is still disabled.
const SHORT: Record<VeredictoCvu, string> = {
  NO_CUBRE_VARIABLE: "No cubre el costo",
  MC_BAJO: "Margen bajo",
  SALUDABLE: "Saludable",
};

const TONE = {
  NO_CUBRE_VARIABLE: "alert",
  MC_BAJO: "warn",
  SALUDABLE: "good",
} as const;

export const VERDICT_SENTENCE: Record<VeredictoCvu, string> = {
  NO_CUBRE_VARIABLE:
    "Con este precio perdés plata en cada unidad: no alcanza ni para cubrir lo que cuesta fabricarla.",
  MC_BAJO:
    "Con este precio cubrís lo que cuesta fabricarla, pero te queda muy poco de cada unidad para pagar los costos fijos.",
  SALUDABLE:
    "Con este precio cubrís lo que cuesta fabricarla y te queda margen de cada unidad para pagar los costos fijos.",
};

export function VeredictoBadge({ veredicto }: { veredicto: VeredictoCvu }) {
  return <Badge tone={TONE[veredicto]}>{SHORT[veredicto]}</Badge>;
}

/** Plain-language definition used wherever "margen de contribución" appears. */
export const MC_EXPLICACION =
  "El margen de contribución es lo que te queda de cada unidad para pagar los costos fijos.";
