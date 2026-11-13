import assert from "node:assert/strict";
import { test } from "node:test";
import { leerProductoDeProveedor, UNIDADES } from "./proveedores";

const fila = {
  nombre: " Flex 1 × 1,40 ",
  unidad: "m2",
  cantidad: "1,4",
  precio_referencial: "14000",
  moneda: "ARS",
};

test("a valid row becomes the API body, amounts as text", () => {
  const result = leerProductoDeProveedor(fila, 1);
  assert.deepEqual(result, {
    ok: true,
    body: {
      nombre: "Flex 1 × 1,40",
      unidad: "m2",
      cantidad: "1.4",
      precio_referencial: "14000",
      moneda: "ARS",
      iva_incluido: false,
      material: null,
      nota: null,
    },
  });
});

test("the quantity is optional, and so are the material, the note and the VAT flag", () => {
  const result = leerProductoDeProveedor(
    { ...fila, cantidad: "", iva: "si", material: "MAT-FO02", nota: "Rollo" },
    1,
  );
  assert.equal(result.ok, true);
  if (result.ok) {
    assert.equal(result.body.cantidad, null);
    assert.equal(result.body.iva_incluido, true);
    assert.equal(result.body.material, "MAT-FO02");
    assert.equal(result.body.nota, "Rollo");
  }
});

test("each missing or wrong field is refused with the name of the product", () => {
  const cases: [Record<string, string>, RegExp][] = [
    [{ nombre: "" }, /^Producto 3: indique el nombre/],
    [{ unidad: "" }, /^Flex 1 × 1,40: elija la unidad/],
    [{ unidad: "kg" }, /elija la unidad/],
    [{ moneda: "" }, /elija la moneda/],
    [{ moneda: "EUR" }, /elija la moneda/],
    [{ precio_referencial: "" }, /precio referencial/],
    [{ precio_referencial: "0" }, /precio referencial/],
    [{ precio_referencial: "1.000,50" }, /precio referencial/],
    [{ cantidad: "0" }, /cantidad/],
    [{ cantidad: "abc" }, /cantidad/],
  ];
  for (const [change, expected] of cases) {
    const result = leerProductoDeProveedor({ ...fila, ...change }, 3);
    assert.equal(result.ok, false, JSON.stringify(change));
    if (!result.ok) assert.match(result.message, expected);
  }
});

test("the unit list is the closed list of the backend", () => {
  assert.deepEqual(
    UNIDADES.map((unidad) => unidad.value).sort(),
    ["USD", "cm", "juego", "m", "m2", "unidad"].sort(),
  );
});
