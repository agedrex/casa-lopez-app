import assert from "node:assert/strict";
import { test } from "node:test";
import { agruparMateriales } from "./materiales";
import type { Material, Precio } from "./types";

function material(codigo: string, etapa: string, nombre: string): Material {
  return {
    codigo,
    nombre,
    nombre_corto: null,
    etapa,
    unidad_de_consumo: "m2",
    cotizable: true,
    controla_inventario: false,
    desperdicio_manual: null,
  };
}

function precio(
  codigo: string,
  materialCodigo: string,
  overrides: Partial<Precio> = {},
): Precio {
  return {
    codigo,
    material: materialCodigo,
    color: null,
    proveedor: null,
    precio: "10",
    moneda: "ARS",
    unidad_del_precio: "m2",
    iva_incluido: false,
    vigente_desde: "2026-09-01",
    nota_fuente: null,
    vigente: true,
    variacion_pct: null,
    salto_grande: false,
    ...overrides,
  };
}

test("groups follow the stage order of the quote and materials are sorted by name inside", () => {
  const grupos = agruparMateriales(
    [
      material("M3", "HERRAJES", "Cierre"),
      material("M2", "CUERO", "Vaca"),
      material("M1", "CUERO", "Carpincho"),
      material("M4", "FORRO", "Tela"),
    ],
    [],
  );
  assert.deepEqual(
    grupos.map((g) => [g.etapa, g.filas.map((f) => f.material.codigo)]),
    [
      ["CUERO", ["M1", "M2"]],
      ["FORRO", ["M4"]],
      ["HERRAJES", ["M3"]],
    ],
  );
});

test("an unknown stage goes last, and empty stages are not listed", () => {
  const grupos = agruparMateriales(
    [material("M1", "OTRA", "X"), material("M2", "CUERO", "Y")],
    [],
  );
  assert.deepEqual(
    grupos.map((g) => g.etapa),
    ["CUERO", "OTRA"],
  );
});

test("the price shown is the one in force for all colors; color prices are only counted", () => {
  const [grupo] = agruparMateriales(
    [material("M1", "CUERO", "Vaca")],
    [
      precio("P3", "M1", { precio: "30", color: "Negro" }),
      precio("P2", "M1", { precio: "26", vigente_desde: "2026-10-01" }),
      precio("P1", "M1", { precio: "24", vigente: false }),
    ],
  );
  const [fila] = grupo.filas;
  assert.equal(fila.precio?.codigo, "P2");
  assert.equal(fila.preciosPorColor, 1);
});

test("without a price in force, the newest one for all colors is shown", () => {
  const [grupo] = agruparMateriales(
    [material("M1", "CUERO", "Vaca")],
    [
      precio("P1", "M1", { vigente: false, vigente_desde: "2026-12-01" }),
      precio("P0", "M1", { vigente: false, vigente_desde: "2026-08-01" }),
    ],
  );
  assert.equal(grupo.filas[0].precio?.codigo, "P1");
});

test("a material with only color prices has no price for the grid", () => {
  const [grupo] = agruparMateriales(
    [material("M1", "CUERO", "Vaca")],
    [precio("P1", "M1", { color: "Negro" })],
  );
  assert.equal(grupo.filas[0].precio, null);
  assert.equal(grupo.filas[0].preciosPorColor, 1);
});
