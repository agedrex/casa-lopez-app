import assert from "node:assert/strict";
import { test } from "node:test";
import { consumoRowsDelTaller } from "../app/(app)/productos/[codigo]/consumo-taller";
import { consumoRows } from "./ficha-consumo";
import type { Ficha, ModeloDetalle } from "./types";

const ficha = {
  codigo: "PRD-0001",
  nombre: "Portafolio",
  modelo: "MOD-0001",
  cuero: "MAT-CU01",
  cuero_nombre: "Estándar",
  color: null,
  horas_de_confeccion: "2.5",
  receta: [],
  costo_hoy: { dolar: "1575", etapas: {} },
} as unknown as Ficha;

const modelo = {
  cuero_m2_por_unidad: "0.25",
  forro_m2_por_unidad: "0.2",
  flex_m2_por_unidad: null,
  goma_eva_m2_por_unidad: "0",
  herrajes_usd_por_unidad: "4",
  hilo_y_cemento: "0.2662",
  insumos: [],
} as unknown as ModeloDetalle;

const row = (rows: ReturnType<typeof consumoRows>, insumo: string) => {
  const found = rows.find((r) => r.insumo === insumo);
  assert.ok(found, insumo);
  return found;
};

test("S5: the taller sees hilo y cemento in juegos, two decimals at most", () => {
  const rows = consumoRowsDelTaller(ficha, modelo);
  assert.equal(row(rows, "Hilo y cemento").porUnidad, "0,27 juegos");
  assert.equal(
    row(
      consumoRowsDelTaller(ficha, { ...modelo, hilo_y_cemento: "1" }),
      "Hilo y cemento",
    ).porUnidad,
    "1 juego",
  );
});

test("S5: the taller sees no money amount on the ficha", () => {
  const rows = consumoRowsDelTaller(ficha, modelo);
  for (const r of rows) assert.ok(!/\$|USD/.test(r.porUnidad), r.insumo);
  assert.equal(row(rows, "Herrajes").porUnidad, "—");
});

test("S5: a model without hilo data says it is missing", () => {
  const rows = consumoRowsDelTaller(ficha, { ...modelo, hilo_y_cemento: null });
  assert.equal(row(rows, "Hilo y cemento").porUnidad, "Falta el dato");
});

test("PRESERVE: quantities in m², the hours and the materials are untouched", () => {
  const rows = consumoRowsDelTaller(ficha, modelo);
  const base = consumoRows(ficha, modelo);
  assert.equal(row(rows, "Cuero").porUnidad, "0,25 m²");
  assert.equal(row(rows, "Flex").porUnidad, "Falta el dato");
  assert.equal(row(rows, "Horas de confección").porUnidad, "2,5 h");
  assert.deepEqual(
    rows.map((r) => r.material),
    base.map((r) => r.material),
  );
});

test("S5: without the model (recipe lines only) nothing changes", () => {
  assert.deepEqual(consumoRowsDelTaller(ficha, null), consumoRows(ficha, null));
});
