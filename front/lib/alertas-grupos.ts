import type { GrupoCalidad, Hallazgo, Severidad } from "./types";

const ORDEN: Record<Severidad, number> = { alta: 0, media: 1, baja: 2 };

// Groups whose message is "<qué pasa>: <nombre humano>".
const CON_NOMBRE = new Set([
  "modelos_sin_validar",
  "modelos",
  "materiales",
  "gastos_fijos",
]);

export type AlertaItem = {
  codigo: string;
  nombre: string | null;
  detalle: string;
  severidad: Severidad;
  ruta: string;
};

export type AlertaGrupo = {
  clave: string;
  titulo: string;
  total: number;
  /** Most severe alert of the group, for its badge. */
  maxima: Severidad;
  items: AlertaItem[];
};

/**
 * Splits "Falta el consumo de cuero: Alhajero" into a human name and what is wrong.
 * Only for the groups whose backend message follows that shape; the rest keep the whole message.
 */
export function nombreDeAlerta(
  clave: string,
  hallazgo: Hallazgo,
): { nombre: string | null; detalle: string } {
  const { mensaje } = hallazgo;
  const corte = mensaje.indexOf(": ");
  if (!CON_NOMBRE.has(clave) || corte < 1) {
    return { nombre: null, detalle: mensaje };
  }
  const nombre = mensaje
    .slice(corte + 2)
    .split(";")[0]
    .trim();
  const detalle = mensaje.slice(0, corte).trim();
  if (!nombre) return { nombre: null, detalle: mensaje };
  return {
    nombre,
    detalle: clave === "modelos_sin_validar" ? "Sin validar" : detalle,
  };
}

/**
 * One group per alert type with its own counter, keeping the backend order. Filters by severity
 * and topic first, so the counters match what is listed; empty groups are dropped.
 */
export function agruparAlertas(
  grupos: GrupoCalidad[],
  severidad: string,
  tema: string,
): AlertaGrupo[] {
  const resultado: AlertaGrupo[] = [];
  for (const grupo of grupos) {
    if (tema && grupo.clave !== tema) continue;
    const items = grupo.hallazgos
      .map((hallazgo, indice) => ({ hallazgo, indice }))
      .filter(({ hallazgo }) => !severidad || hallazgo.severidad === severidad)
      .sort(
        (a, b) =>
          ORDEN[a.hallazgo.severidad] - ORDEN[b.hallazgo.severidad] ||
          a.indice - b.indice,
      )
      .map(({ hallazgo }): AlertaItem => {
        const { nombre, detalle } = nombreDeAlerta(grupo.clave, hallazgo);
        return {
          codigo: hallazgo.entidad,
          nombre,
          detalle,
          severidad: hallazgo.severidad,
          ruta: hallazgo.ruta,
        };
      });
    if (items.length === 0) continue;
    resultado.push({
      clave: grupo.clave,
      titulo: grupo.titulo,
      total: items.length,
      maxima: items[0].severidad,
      items,
    });
  }
  return resultado;
}
