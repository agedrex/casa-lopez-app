import assert from "node:assert/strict";
import { test } from "node:test";
import {
  filasParaGuardar,
  leerProductoDeProveedor,
  UNIDADES,
} from "./proveedores";

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

test("a changed saved row gets back the name and the note the grid does not send", () => {
  const filas = filasParaGuardar(
    {
      changes: [
        {
          id: "PPR-0001",
          cells: {
            unidad: "m2",
            cantidad: "1,4",
            precio_referencial: "16000",
            moneda: "ARS",
            iva: "no",
            material: "",
          },
          changed: ["precio_referencial"],
        },
      ],
      added: [],
    },
    [
      { codigo: "PPR-0001", nombre: "Flex 1 × 1,40", nota: null },
      { codigo: "PPR-0002", nombre: "Goma EVA", nota: "Rollo" },
    ],
  );
  assert.equal(filas.length, 1);
  const result = leerProductoDeProveedor(filas[0], 1);
  assert.equal(result.ok, true);
  if (result.ok) {
    assert.equal(result.body.nombre, "Flex 1 × 1,40");
    assert.equal(result.body.precio_referencial, "16000");
    assert.equal(result.body.nota, null);
  }
});

test("the note of the saved product travels with the changed row", () => {
  const [fila] = filasParaGuardar(
    {
      changes: [
        {
          id: "PPR-0002",
          cells: { unidad: "m2", precio_referencial: "9000", moneda: "ARS" },
          changed: ["precio_referencial"],
        },
      ],
      added: [],
    },
    [{ codigo: "PPR-0002", nombre: "Goma EVA", nota: "Rollo" }],
  );
  assert.equal(fila.nombre, "Goma EVA");
  assert.equal(fila.nota, "Rollo");
});

test("a new row keeps its own name and goes after the changed ones", () => {
  const nueva = { ...fila, nombre: "Tela forro" };
  const filas = filasParaGuardar(
    {
      changes: [
        {
          id: "PPR-0001",
          cells: { unidad: "m2", precio_referencial: "16000", moneda: "ARS" },
          changed: ["precio_referencial"],
        },
      ],
      added: [nueva],
    },
    [{ codigo: "PPR-0001", nombre: "Flex 1 × 1,40", nota: null }],
  );
  assert.equal(filas.length, 2);
  assert.equal(filas[0].nombre, "Flex 1 × 1,40");
  assert.deepEqual(filas[1], nueva);
  const result = leerProductoDeProveedor(filas[1], 2);
  assert.equal(result.ok, true);
  if (result.ok) assert.equal(result.body.nombre, "Tela forro");
});
