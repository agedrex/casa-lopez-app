import assert from "node:assert/strict";
import { test } from "node:test";
import { cubiertoPorInsumos } from "./formulario-insumos";
import type { InsumoModelo } from "./types";

function insumo(etapa: string): InsumoModelo {
  return {
    codigo: "MIN-0001",
    material: "MAT-X",
    nombre: "Cierre N5",
    etapa,
    unidad_de_consumo: "unidad",
    cantidad_por_unidad: "1",
    precio_unitario: null,
    moneda: null,
  };
}

test("herrajes and hilo y cemento are covered by supplies of their own stage", () => {
  assert.equal(
    cubiertoPorInsumos("herrajes_usd_por_unidad", [insumo("HERRAJES")]),
    true,
  );
  assert.equal(
    cubiertoPorInsumos("hilo_y_cemento", [insumo("HILO_CEMENTO")]),
    true,
  );
});

test("a supply of another stage, no supplies, or a field with no supply stage cover nothing", () => {
  assert.equal(
    cubiertoPorInsumos("herrajes_usd_por_unidad", [insumo("FLEX")]),
    false,
  );
  assert.equal(cubiertoPorInsumos("herrajes_usd_por_unidad", []), false);
  assert.equal(
    cubiertoPorInsumos("cuero_m2_por_unidad", [insumo("HERRAJES")]),
    false,
  );
});
