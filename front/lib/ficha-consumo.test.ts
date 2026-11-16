import assert from "node:assert/strict";
import { test } from "node:test";
import { consumoRows, fichaSubtitle } from "./ficha-consumo";
import type { Ficha, ModeloDetalle } from "./types";

const ficha = {
  codigo: "PRD-0001",
  nombre: "Portafolio",
  modelo: "MOD-0001",
  modelo_nombre: "Portafolio Simple Ch.",
  cuero: "MAT-CU01",
  cuero_nombre: "Estándar",
  color: null,
  horas_de_confeccion: "2.5",
  receta: [
    {
      etapa: "CUERO",
      material: "MAT-CU01",
      material_nombre: "Estándar",
      color: null,
      consumo: "0.25",
    },
    {
      etapa: "FORRO",
      material: "MAT-FO02",
      material_nombre: "Tela forrería",
      color: null,
      consumo: "0.2",
    },
    {
      etapa: "HILO_CEMENTO",
      material: "MAT-HC01",
      material_nombre: "Hilo y cemento",
      color: null,
      consumo: "1",
    },
  ],
  costo_hoy: { dolar: "1570", etapas: { HILO_CEMENTO: "3140" } },
} as unknown as Ficha;

const modelo = {
  cuero_m2_por_unidad: "0.25",
  forro_m2_por_unidad: "0.2",
  flex_m2_por_unidad: null,
  goma_eva_m2_por_unidad: "0",
  herrajes_usd_por_unidad: "4",
  hilo_y_cemento: "1",
  insumos: [],
} as unknown as ModeloDetalle;

const row = (rows: ReturnType<typeof consumoRows>, insumo: string) => {
  const found = rows.find((r) => r.insumo === insumo);
  assert.ok(found, insumo);
  return found;
};

test("S1: the Material column shows names, never material codes", () => {
  const rows = consumoRows(ficha, modelo);
  assert.equal(row(rows, "Cuero").material, "Estándar");
  assert.equal(row(rows, "Forro").material, "Tela forrería");
  assert.ok(rows.every((r) => !/MAT-/.test(r.material)));
});

test("S1: a supply shows the material name without its code", () => {
  const withInsumo = {
    ...modelo,
    insumos: [{ etapa: "HERRAJES", nombre: "Herraje X", material: "MAT-IN01" }],
  } as unknown as ModeloDetalle;
  assert.equal(
    row(consumoRows(ficha, withInsumo), "Herrajes").material,
    "Herraje X",
  );
});

test("S1: without a name from the API the code is the fallback, not an empty cell", () => {
  const old = {
    ...ficha,
    receta: [{ ...ficha.receta[0], material_nombre: undefined }],
  } as Ficha;
  assert.equal(row(consumoRows(old, modelo), "Cuero").material, "MAT-CU01");
});

test("S1: the header uses model and leather names, and the color when there is one", () => {
  assert.equal(fichaSubtitle(ficha), "Portafolio Simple Ch. · Estándar");
  assert.equal(
    fichaSubtitle({ ...ficha, color: "Negro" }),
    "Portafolio Simple Ch. · Estándar · Negro",
  );
});

test("S2: the hours come last and say they are outside the cost", () => {
  const rows = consumoRows(ficha, modelo);
  const last = rows[rows.length - 1];
  assert.equal(last.insumo, "Horas de confección");
  assert.equal(last.porUnidad, "2,5 h");
  assert.match(last.material, /no entra en el costo/);
  const sinModelo = consumoRows(ficha, null);
  assert.equal(sinModelo[sinModelo.length - 1].insumo, "Horas de confección");
});

test("S2: a model without hours says the data is missing", () => {
  const rows = consumoRows({ ...ficha, horas_de_confeccion: null }, modelo);
  assert.equal(rows[rows.length - 1].porUnidad, "Falta el dato");
});

test("S3: hilo y cemento shows only the reference price in pesos", () => {
  const hilo = row(consumoRows(ficha, modelo), "Hilo y cemento");
  assert.match(hilo.porUnidad, /^\$\s?1\.570,00$/);
  assert.ok(!/USD|dólar|Fijo/.test(`${hilo.porUnidad} ${hilo.material}`));
  assert.equal(hilo.material, "Hilo y cemento");
});

test("S3: without a quote of today there is no amount, even if the model has no hilo datum", () => {
  const sinCosto = row(
    consumoRows({ ...ficha, costo_hoy: null }, modelo),
    "Hilo y cemento",
  );
  assert.equal(sinCosto.porUnidad, "—");
});

test("the other rows keep their quantities", () => {
  const rows = consumoRows(ficha, modelo);
  assert.equal(row(rows, "Cuero").porUnidad, "0,25 m²");
  assert.equal(row(rows, "Flex").porUnidad, "Falta el dato");
  assert.equal(row(rows, "Goma EVA").porUnidad, "0 m²");
  assert.equal(row(rows, "Herrajes").porUnidad, "4 USD");
});
