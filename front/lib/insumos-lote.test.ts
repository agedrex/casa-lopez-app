import assert from "node:assert/strict";
import { test } from "node:test";
import {
  cantidadDeInsumo,
  tablaDeInsumos,
} from "../app/(app)/fabricacion/[codigo]/insumos-lote";
import type { ConsumoLote, LoteCuero } from "./types";

test("S5: a quantity in juegos shows two decimals at most", () => {
  assert.equal(cantidadDeInsumo("0.2662", "juego"), "0,27 juegos");
  assert.equal(cantidadDeInsumo("1", "juego"), "1 juego");
  assert.equal(cantidadDeInsumo("1.5", "juego"), "1,5 juegos");
});

test("PRESERVE: other units keep their precision", () => {
  assert.equal(cantidadDeInsumo("0.2662", "m2"), "0,2662 m²");
  assert.equal(cantidadDeInsumo("3", "unidad"), "3 unidades");
});

const consumo = {
  lote: "LOT-0001",
  estado: "PLANIFICADA",
  productos: [
    {
      item: "LIT-0001",
      producto: "PRD-0001",
      producto_nombre: "Portafolio",
      cantidad: "5",
      insumos: [
        {
          material: "MAT-CU01",
          material_nombre: "Estándar",
          color: "Negro",
          unidad: "m2",
          por_unidad: "0.25",
          total: "1.25",
        },
        {
          material: "MAT-HC01",
          material_nombre: "Hilo y cemento",
          color: null,
          unidad: "juego",
          por_unidad: "0.2662",
          total: "1.331",
        },
      ],
    },
  ],
  totales: [
    {
      material: "MAT-CU01",
      material_nombre: "Estándar",
      color: "Negro",
      unidad: "m2",
      total: "1.25",
      productos: ["PRD-0001"],
    },
    {
      material: "MAT-HC01",
      material_nombre: "Hilo y cemento",
      color: null,
      unidad: "juego",
      total: "1.331",
      productos: ["PRD-0001"],
    },
  ],
  sin_consumo: [],
} as ConsumoLote;

const cuero = {
  lote: "LOT-0001",
  estado: "PLANIFICADA",
  cueros: [
    {
      material: "MAT-CU01",
      material_nombre: "Estándar",
      color: "Negro",
      necesario: "1.25",
      ya_cortado: "0",
      por_cortar: "1.25",
      disponible: "1",
      alcanza: false,
      faltante: "0.25",
      sobrante: "0",
      productos: ["PRD-0001"],
    },
  ],
  sin_consumo: [],
} as LoteCuero;

test("S6: one table with the total per supply and the leather stock in the leather row", () => {
  const tabla = tablaDeInsumos(consumo, cuero);
  assert.deepEqual(
    tabla.filas.map((f) => [f.nombre, f.total, f.cuero]),
    [
      ["Estándar · Negro", "1,25 m²", "Falta 0,25 m²"],
      ["Hilo y cemento", "1,33 juegos", null],
    ],
  );
  assert.equal(tabla.faltan, 1);
});

test("S6: per product, juegos also show two decimals", () => {
  const [producto] = tablaDeInsumos(consumo, cuero).productos;
  assert.equal(producto.insumos[1].porUnidad, "0,27 juegos");
  assert.equal(producto.insumos[1].total, "1,33 juegos");
});

test("S6: without the leather answer (closed lot) there is no stock column data", () => {
  const tabla = tablaDeInsumos(consumo, null);
  assert.ok(tabla.filas.every((f) => f.cuero === null));
  assert.equal(tabla.hayCuero, false);
  assert.equal(tabla.faltan, 0);
});

test("S6: products without supplies are listed apart, not counted", () => {
  const tabla = tablaDeInsumos(
    {
      ...consumo,
      sin_consumo: [{ producto: "PRD-0009", producto_nombre: "Llavero" }],
    },
    null,
  );
  assert.deepEqual(tabla.sinConsumo, ["Llavero (PRD-0009)"]);
});
