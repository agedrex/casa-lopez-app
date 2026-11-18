import assert from "node:assert/strict";
import { test } from "node:test";
import { insumoTexto, resumenDeConsumo, unidadTexto } from "./lote-consumo";
import type { ConsumoLote } from "./types";

function consumo(cambios: Partial<ConsumoLote> = {}): ConsumoLote {
  return {
    lote: "LOT-0001",
    estado: "PLANIFICADA",
    productos: [
      {
        item: "LIT-0001",
        producto: "PRD-0001",
        producto_nombre: "Portafolio Simple Ch.",
        cantidad: "4.000000",
        insumos: [
          {
            material: "MAT-CU01",
            material_nombre: "Estándar",
            color: "Negro",
            unidad: "m2",
            por_unidad: "0.250000",
            total: "1.000000",
          },
          {
            material: "MAT-HC01",
            material_nombre: "Hilo y cemento",
            color: null,
            unidad: "juego",
            por_unidad: "1.000000",
            total: "4.000000",
          },
        ],
      },
      {
        item: "LIT-0002",
        producto: "PRD-0002",
        producto_nombre: "Cartera Bugatti",
        cantidad: "1.000000",
        insumos: [],
      },
    ],
    totales: [
      {
        material: "MAT-CU01",
        material_nombre: "Estándar",
        color: "Negro",
        unidad: "m2",
        total: "2.800000",
        productos: ["PRD-0001", "PRD-0003"],
      },
      {
        material: "MAT-HC01",
        material_nombre: "Hilo y cemento",
        color: null,
        unidad: "juego",
        total: "6.000000",
        productos: ["PRD-0001"],
      },
    ],
    sin_consumo: [{ producto: "PRD-0002", producto_nombre: "Cartera Bugatti" }],
    ...cambios,
  };
}

test("unidadTexto usa el símbolo de las unidades conocidas y deja las otras tal cual", () => {
  assert.equal(unidadTexto("m2"), "m²");
  assert.equal(unidadTexto("juego"), "juego");
  assert.equal(unidadTexto("cm"), "cm");
  assert.equal(unidadTexto("m"), "m");
});

test("insumoTexto junta nombre y color, sin color queda solo el nombre", () => {
  assert.equal(
    insumoTexto({ material_nombre: "Estándar", color: "Negro" }),
    "Estándar · Negro",
  );
  assert.equal(
    insumoTexto({ material_nombre: "Hilo y cemento", color: null }),
    "Hilo y cemento",
  );
});

test("resumenDeConsumo arma una tarjeta por producto con cada insumo y su cantidad con unidad", () => {
  const resumen = resumenDeConsumo(consumo());
  assert.equal(resumen.productos.length, 2);
  const primero = resumen.productos[0];
  assert.equal(primero.key, "LIT-0001");
  assert.equal(primero.titulo, "Portafolio Simple Ch.");
  assert.equal(primero.cantidad, "4");
  assert.deepEqual(
    primero.insumos.map((i) => [i.nombre, i.porUnidad, i.total]),
    [
      ["Estándar · Negro", "0,25 m²", "1 m²"],
      ["Hilo y cemento", "1 juego", "4 juegos"],
    ],
  );
});

test("un producto sin insumos queda marcado y no inventa filas", () => {
  const sin = resumenDeConsumo(consumo()).productos[1];
  assert.deepEqual(sin.insumos, []);
  assert.equal(sin.sinConsumo, true);
  assert.equal(resumenDeConsumo(consumo()).productos[0].sinConsumo, false);
});

test("los totales del lote muestran lo que dice la API, con cuántos productos lo usan", () => {
  const totales = resumenDeConsumo(consumo()).totales;
  assert.deepEqual(
    totales.map((t) => [t.nombre, t.total, t.productos]),
    [
      ["Estándar · Negro", "2,8 m²", 2],
      ["Hilo y cemento", "6 juegos", 1],
    ],
  );
});

test("el titular cuenta productos y unidades, y avisa cuando no hay consumo cargado", () => {
  assert.equal(
    resumenDeConsumo(consumo()).titular,
    "2 productos · 5 unidades · 2 insumos en total",
  );
  assert.equal(
    resumenDeConsumo(consumo({ productos: [], totales: [], sin_consumo: [] }))
      .titular,
    "Todavía no hay consumo para este lote.",
  );
});

test("sinConsumo lista los productos que no se pueden contar", () => {
  assert.deepEqual(resumenDeConsumo(consumo()).sinConsumo, [
    "Cartera Bugatti (PRD-0002)",
  ]);
});

test("nada del resumen lleva plata: solo cantidades", () => {
  const texto = JSON.stringify(resumenDeConsumo(consumo()));
  assert.equal(/\$|USD|ARS/.test(texto), false);
});
