import assert from "node:assert/strict";
import { test } from "node:test";
import { insumoTexto, unidadTexto } from "./lote-consumo";

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
