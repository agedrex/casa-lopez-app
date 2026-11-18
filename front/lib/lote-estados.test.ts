import assert from "node:assert/strict";
import { test } from "node:test";
import {
  agruparLotesPorEstado,
  diasDelLote,
  diasEntre,
  lineaDeTiempo,
  siguienteEstadoDelTaller,
  textoDeDias,
} from "./lote-estados";
import type { EstadoDeOrden, OrdenResumen } from "./types";

function orden(
  codigo: string,
  estado: string,
  envio: string | null,
): OrdenResumen {
  return {
    codigo,
    donde_se_hace: "EXTERNA",
    taller: null,
    taller_nombre: null,
    persona: null,
    persona_nombre: null,
    fecha_de_envio: envio,
    fecha_de_entrega: null,
    periodo: null,
    estado,
    nota: null,
    productos: 1,
    unidades: "10",
    total_cotizado: "0",
    total_cobrado: "0",
    costo_total: null,
    costo_promedio_por_unidad: null,
    avisos: [],
  };
}

function paso(
  estado: string,
  fecha: string,
  cambiado_por: string | null = null,
): EstadoDeOrden {
  return {
    estado,
    fecha,
    quien: null,
    quien_nombre: null,
    cambiado_por,
    registrado_en: `${fecha}T10:00:00-03:00`,
  };
}

test("the taller only has the next state, and none after LISTA (closing is the admin's)", () => {
  assert.equal(siguienteEstadoDelTaller("PLANIFICADA"), "EN_CORTE");
  assert.equal(siguienteEstadoDelTaller("EN_CORTE"), "CORTADA");
  assert.equal(siguienteEstadoDelTaller("CORTADA"), "EN_CONFECCION");
  assert.equal(siguienteEstadoDelTaller("EN_CONFECCION"), "LISTA");
  assert.equal(siguienteEstadoDelTaller("LISTA"), null);
  assert.equal(siguienteEstadoDelTaller("CERRADA"), null);
  assert.equal(siguienteEstadoDelTaller("INVENTADO"), null);
});

test("lots are grouped by state in the order of the cycle, oldest first, closed ones last, empty groups left out", () => {
  const grupos = agruparLotesPorEstado([
    orden("LOT-0005", "CERRADA", "2026-11-01"),
    orden("LOT-0004", "EN_CORTE", "2026-11-10"),
    orden("LOT-0003", "PLANIFICADA", "2026-11-12"),
    orden("LOT-0002", "EN_CORTE", "2026-11-05"),
    orden("LOT-0001", "EN_CORTE", null),
    orden("LOT-0006", "LISTA", "2026-11-02"),
  ]);
  assert.deepEqual(
    grupos.map((g) => [g.estado, g.lotes.map((l) => l.codigo)]),
    [
      ["PLANIFICADA", ["LOT-0003"]],
      ["EN_CORTE", ["LOT-0002", "LOT-0004", "LOT-0001"]],
      ["LISTA", ["LOT-0006"]],
      ["CERRADA", ["LOT-0005"]],
    ],
  );
  assert.deepEqual(agruparLotesPorEstado([]), []);
});

test("whole days between two dates, never negative, null when one is missing", () => {
  assert.equal(diasEntre("2026-11-16", "2026-11-16"), 0);
  assert.equal(diasEntre("2026-11-16", "2026-11-21"), 5);
  assert.equal(diasEntre("2026-10-30", "2026-11-02"), 3);
  assert.equal(diasEntre("2026-11-20", "2026-11-16"), 0);
  assert.equal(diasEntre(null, "2026-11-16"), null);
  assert.equal(textoDeDias(0), "menos de un día");
  assert.equal(textoDeDias(1), "1 día");
  assert.equal(textoDeDias(7), "7 días");
});

test("the timeline counts the days in each state and from the creation, and the open state runs until today", () => {
  const linea = lineaDeTiempo(
    [
      paso("PLANIFICADA", "2026-11-10"),
      paso("EN_CORTE", "2026-11-12", "Ana"),
      paso("CORTADA", "2026-11-12", "Ana"),
    ],
    "2026-11-17",
  );
  assert.deepEqual(
    linea.pasos.map((p) => [p.estado, p.diasEnElEstado, p.diasDesdeElInicio]),
    [
      ["PLANIFICADA", 2, 0],
      ["EN_CORTE", 0, 2],
      ["CORTADA", 5, 2],
    ],
  );
  assert.deepEqual(
    linea.pasos.map((p) => [p.actual, p.quien]),
    [
      [false, null],
      [false, "Ana"],
      [true, "Ana"],
    ],
  );
  assert.equal(linea.terminado, false);
  assert.equal(linea.diasTotales, 7);
});

test("a closed lot ends its timeline on the closing day: no open state keeps counting", () => {
  const linea = lineaDeTiempo(
    [
      paso("PLANIFICADA", "2026-11-10"),
      paso("LISTA", "2026-11-14"),
      paso("CERRADA", "2026-11-16"),
    ],
    "2026-11-30",
  );
  assert.equal(linea.terminado, true);
  assert.equal(linea.diasTotales, 6);
  assert.equal(linea.pasos[2].diasEnElEstado, null);
  assert.equal(lineaDeTiempo([], "2026-11-30").diasTotales, null);
});

test("who changed a state: the logged-in user first, else the person the admin picked", () => {
  const linea = lineaDeTiempo(
    [
      {
        estado: "EN_CORTE",
        fecha: "2026-11-12",
        quien: "PER-0002",
        quien_nombre: "Marta",
        cambiado_por: null,
        registrado_en: null,
      },
    ],
    "2026-11-12",
  );
  assert.equal(linea.pasos[0].quien, "Marta");
});

test("days a lot has taken: to the delivery date, else to today while open, else a dash", () => {
  const base = orden("LOT-0001", "EN_CORTE", "2026-11-10");
  assert.equal(diasDelLote(base, "2026-11-17"), "7");
  assert.equal(
    diasDelLote(
      { ...base, estado: "CERRADA", fecha_de_entrega: "2026-11-14" },
      "2026-11-17",
    ),
    "4",
  );
  assert.equal(diasDelLote({ ...base, estado: "CERRADA" }, "2026-11-17"), "—");
  assert.equal(
    diasDelLote({ ...base, fecha_de_envio: null }, "2026-11-17"),
    "—",
  );
});
