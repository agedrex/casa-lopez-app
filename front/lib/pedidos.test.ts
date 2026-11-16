import assert from "node:assert/strict";
import { test } from "node:test";
import {
  leerLineaSimpleDePedido,
  llegoTexto,
  PRESENTACIONES,
  unitPricePreview,
} from "./pedidos";

test("divides price by content with exact decimals", () => {
  assert.equal(unitPricePreview("14000", "1.4"), "10000.0000");
  assert.equal(unitPricePreview("6080", "1.5"), "4053.3333");
  assert.equal(unitPricePreview("8200", "1.4"), "5857.1429");
});

test("accepts a comma as decimal separator", () => {
  assert.equal(unitPricePreview("1250,50", "10"), "125.0500");
  assert.equal(unitPricePreview("10", "0,5"), "20.0000");
});

test("keeps small and zero prices with four decimals", () => {
  assert.equal(unitPricePreview("1", "3000"), "0.0003");
  assert.equal(unitPricePreview("0", "10"), "0.0000");
  assert.equal(unitPricePreview("1", "20000"), "0.0001");
  assert.equal(unitPricePreview("1", "30000"), "0.0000");
});

test("rounds half up at the fourth decimal", () => {
  assert.equal(unitPricePreview("1", "16"), "0.0625");
  assert.equal(unitPricePreview("1", "32"), "0.0313");
});

test("does not lose precision with long values", () => {
  assert.equal(
    unitPricePreview("123456789012.3456", "0.000001"),
    "123456789012345600.0000",
  );
});

test("returns null when a value is missing, invalid, negative or the content is zero", () => {
  assert.equal(unitPricePreview("", "10"), null);
  assert.equal(unitPricePreview("10", ""), null);
  assert.equal(unitPricePreview("abc", "10"), null);
  assert.equal(unitPricePreview("10", "0"), null);
  assert.equal(unitPricePreview("10", "0,000"), null);
  assert.equal(unitPricePreview("-5", "10"), null);
  assert.equal(unitPricePreview("1.2.3", "10"), null);
});

test("suggests the usual presentations", () => {
  assert.deepEqual(
    [...PRESENTACIONES],
    ["CARRETE", "CAJA", "ROLLO", "BOLSA", "UNIDAD", "PLANCHA"],
  );
});

test("a simple line is stored as quantity x one unit of the material", () => {
  const result = leerLineaSimpleDePedido(
    {
      material: "MAT-0001",
      cantidad: "5,5",
      precio: "10000",
      moneda: "ARS",
      iva: false,
    },
    1,
  );
  assert.deepEqual(result, {
    ok: true,
    linea: {
      material: "MAT-0001",
      cantidad_presentaciones: "5.5",
      presentacion: "UNIDAD",
      contenido_por_presentacion: "1",
      precio_por_presentacion: "10000",
      moneda: "ARS",
      iva_incluido: false,
    },
  });
});

test("a simple line names the first thing that is wrong", () => {
  const base = {
    material: "MAT-0001",
    cantidad: "2",
    precio: "10",
    moneda: "USD",
    iva: true,
  };
  const fail = (patch: Partial<typeof base>) =>
    leerLineaSimpleDePedido({ ...base, ...patch }, 2);
  assert.deepEqual(fail({ material: "" }), {
    ok: false,
    message: "Línea 2: elija el material.",
  });
  assert.deepEqual(fail({ cantidad: "0" }), {
    ok: false,
    message: "Línea 2: la cantidad debe ser un número mayor que 0.",
  });
  assert.deepEqual(fail({ cantidad: "abc" }), {
    ok: false,
    message: "Línea 2: la cantidad debe ser un número mayor que 0.",
  });
  assert.deepEqual(fail({ precio: "" }), {
    ok: false,
    message:
      "Línea 2: ingrese el precio por unidad, por ejemplo 14000 o 5857,14.",
  });
  assert.deepEqual(fail({ moneda: "EUR" }), {
    ok: false,
    message: "Línea 2: elija la moneda.",
  });
  assert.equal((fail({}) as { ok: true }).ok, true);
});

test("what arrived reads as a plain quantity when there is no real presentation", () => {
  assert.equal(
    llegoTexto({
      cantidad_presentaciones: "5.500000",
      presentacion: "UNIDAD",
      contenido_por_presentacion: "1.000000",
      unidad_de_consumo: "m2",
    }),
    "5,5 m2",
  );
  assert.equal(
    llegoTexto({
      cantidad_presentaciones: "3.000000",
      presentacion: "ROLLO",
      contenido_por_presentacion: "1.400000",
      unidad_de_consumo: "m2",
    }),
    "3 × ROLLO",
  );
});
