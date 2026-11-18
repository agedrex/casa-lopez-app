// Pure helpers for the state of a lot: what the taller sees (lots grouped by state, the next state) and the
// follow-up timeline of the admin (days in each state, who changed it). Dates travel as "AAAA-MM-DD"; there is
// no money here.
import type { EstadoDeOrden, OrdenResumen } from "./types";

/** The cycle, in order. The taller works from PLANIFICADA to LISTA; CERRADA (final quote) is the admin's. */
const CICLO = [
  "PLANIFICADA",
  "EN_CORTE",
  "CORTADA",
  "EN_CONFECCION",
  "LISTA",
  "CERRADA",
] as const;

/** The state a taller moves a lot to from `estado`; null after LISTA (closing is not the taller's) or for an unknown one. */
export function siguienteEstadoDelTaller(estado: string): string | null {
  const posicion = (CICLO as readonly string[]).indexOf(estado);
  const siguiente = posicion === -1 ? undefined : CICLO[posicion + 1];
  return siguiente && siguiente !== "CERRADA" ? siguiente : null;
}

export type GrupoDeLotes = { estado: string; lotes: OrdenResumen[] };

/**
 * Lots grouped by state, in the order of the cycle (closed ones last); the oldest first inside a group, the
 * undated ones after the dated, then by code. Groups with no lots are left out.
 */
export function agruparLotesPorEstado(ordenes: OrdenResumen[]): GrupoDeLotes[] {
  return CICLO.map((estado) => ({
    estado: estado as string,
    lotes: ordenes
      .filter((orden) => orden.estado === estado)
      .sort((a, b) => {
        if (a.fecha_de_envio !== b.fecha_de_envio) {
          if (a.fecha_de_envio === null) return 1;
          if (b.fecha_de_envio === null) return -1;
          return a.fecha_de_envio < b.fecha_de_envio ? -1 : 1;
        }
        return a.codigo < b.codigo ? -1 : a.codigo > b.codigo ? 1 : 0;
      }),
  })).filter((grupo) => grupo.lotes.length > 0);
}

const DIA = /^(\d{4})-(\d{2})-(\d{2})/;

function utc(fecha: string): number | null {
  const m = DIA.exec(fecha);
  return m ? Date.UTC(Number(m[1]), Number(m[2]) - 1, Number(m[3])) : null;
}

/** Whole days from `desde` to `hasta` (never negative); null when a date is missing or unreadable. */
export function diasEntre(
  desde: string | null | undefined,
  hasta: string | null | undefined,
): number | null {
  const a = desde ? utc(desde) : null;
  const b = hasta ? utc(hasta) : null;
  if (a === null || b === null) return null;
  return Math.max(0, Math.round((b - a) / 86_400_000));
}

export function textoDeDias(dias: number): string {
  if (dias <= 0) return "menos de un día";
  return dias === 1 ? "1 día" : `${dias} días`;
}

export type PasoDeLinea = {
  estado: string;
  fecha: string;
  // Who changed it: the logged-in user, else the person the admin picked; null when nobody was recorded.
  quien: string | null;
  // When it was saved (date and time as the API sent them).
  registradoEn: string | null;
  // Days the lot stayed in this state; null for CERRADA (nothing follows).
  diasEnElEstado: number | null;
  diasDesdeElInicio: number | null;
  actual: boolean;
};

export type LineaDeTiempo = {
  pasos: PasoDeLinea[];
  terminado: boolean;
  // From the first state to CERRADA, or to today while the lot is open; null with no history.
  diasTotales: number | null;
};

export function lineaDeTiempo(
  estados: EstadoDeOrden[],
  hoy: string,
): LineaDeTiempo {
  const inicio = estados[0]?.fecha ?? null;
  const pasos = estados.map((e, i): PasoDeLinea => {
    const siguiente = estados[i + 1];
    const ultimo = siguiente === undefined;
    return {
      estado: e.estado,
      fecha: e.fecha,
      quien: e.cambiado_por || e.quien_nombre || null,
      registradoEn: e.registrado_en ?? null,
      diasEnElEstado:
        e.estado === "CERRADA"
          ? null
          : diasEntre(e.fecha, ultimo ? hoy : siguiente.fecha),
      diasDesdeElInicio: diasEntre(inicio, e.fecha),
      actual: ultimo,
    };
  });
  const cierre = estados.find((e) => e.estado === "CERRADA");
  return {
    pasos,
    terminado: cierre !== undefined,
    diasTotales: diasEntre(inicio, cierre ? cierre.fecha : hoy),
  };
}

/**
 * Days a lot has taken: from its creation date to its delivery date, else (while it is not closed) to today.
 * "—" when it has no creation date or is closed without a delivery date.
 */
export function diasDelLote(
  orden: Pick<OrdenResumen, "fecha_de_envio" | "fecha_de_entrega" | "estado">,
  hoy: string,
): string {
  const fin =
    orden.fecha_de_entrega ?? (orden.estado === "CERRADA" ? null : hoy);
  const dias = diasEntre(orden.fecha_de_envio, fin);
  return dias === null ? "—" : String(dias);
}
