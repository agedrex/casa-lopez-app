import assert from "node:assert/strict";
import { test } from "node:test";
import { costoVariableDelLote } from "./lote-costo-variable";

const base = {
  cuenta_en_costo_variable: false,
  cuenta_desde_estado: "LISTA",
  periodo: "2026-11",
  unidades: "13",
  costo_total: "250000",
};

test("un lote sin terminar avisa que cuenta cuando llegue a Lista", () => {
  const r = costoVariableDelLote(base);
  assert.equal(r.cuenta, false);
  assert.equal(r.titulo, "Todavía no suma al costo variable de 11/2026");
  assert.match(
    r.texto,
    /Va a sumar .*250\.000.* y 13 unidades cuando llegue a Lista/,
  );
});

test("un lote terminado ya suma su costo y sus unidades al mes", () => {
  const r = costoVariableDelLote({ ...base, cuenta_en_costo_variable: true });
  assert.equal(r.cuenta, true);
  assert.equal(r.titulo, "Ya suma al costo variable de 11/2026");
  assert.match(r.texto, /aporta .*250\.000.* y 13 unidades/);
});

test("sin costo calculado no inventa un monto", () => {
  const r = costoVariableDelLote({ ...base, costo_total: null, unidades: "1" });
  assert.match(r.texto, /1 unidad \(todavía no se pudo calcular su costo\)/);
});

test("sin fecha no cuenta en ningún mes", () => {
  const r = costoVariableDelLote({ ...base, periodo: null });
  assert.equal(r.cuenta, false);
  assert.equal(r.titulo, "No suma a ningún mes");
});
