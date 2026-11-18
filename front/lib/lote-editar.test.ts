import assert from "node:assert/strict";
import { test } from "node:test";
import { plainQuantity, readCantidad } from "./lote-editar";

function form(cantidad?: string): FormData {
  const data = new FormData();
  if (cantidad !== undefined) data.append("cantidad", cantidad);
  return data;
}

test("readCantidad acepta enteros y decimales con coma o punto", () => {
  assert.equal(readCantidad(form("12")), "12");
  assert.equal(readCantidad(form(" 2,5 ")), "2.5");
  assert.equal(readCantidad(form("0.25")), "0.25");
});

test("readCantidad rechaza cero, vacío, negativos y texto", () => {
  for (const raw of ["0", "0,00", "", "-3", "abc", "1,2,3"]) {
    assert.deepEqual(
      readCantidad(form(raw)),
      {
        status: "error",
        message:
          "Ingresá una cantidad mayor que cero. Para sacar el producto del lote usá «Quitar».",
        avisos: [],
      },
      raw,
    );
  }
  assert.equal(readCantidad(form()).constructor, Object);
});

test("plainQuantity saca los ceros sobrantes de la cantidad de la API", () => {
  assert.equal(plainQuantity("10.000000"), "10");
  assert.equal(plainQuantity("6.500000"), "6.5");
  assert.equal(plainQuantity("0.250000"), "0.25");
  assert.equal(plainQuantity("100"), "100");
});
