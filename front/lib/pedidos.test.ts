import assert from "node:assert/strict";
import { test } from "node:test";
import {
  leerLineaSimpleDePedido,
  leerPielesDePedido,
  leerTamanosDePieles,
  llegoTexto,
  PRESENTACIONES,
  resumenDePieles,
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

const sizes = (text: string) => {
  const result = leerTamanosDePieles(text);
  return result.ok ? result.tamanos : result.message;
};

test("sizes separated by commas or spaces give one entry per skin", () => {
  assert.deepEqual(sizes("1, 2, 2, 5"), ["1", "2", "2", "5"]);
  assert.deepEqual(sizes("1 2 2 5"), ["1", "2", "2", "5"]);
  assert.deepEqual(sizes(" 1,2 ,, 3 "), ["1", "2", "3"]);
});

test("the 3x2 shorthand repeats a size, with or without spaces", () => {
  assert.deepEqual(sizes("3x2, 1"), ["2", "2", "2", "1"]);
  assert.deepEqual(sizes("3 x 2, 1, 5"), ["2", "2", "2", "1", "5"]);
  assert.deepEqual(sizes("2X1.5"), ["1.5", "1.5"]);
});

test("a size with a decimal point is kept as typed", () => {
  assert.deepEqual(sizes("2.5"), ["2.5"]);
});

test("sizes name what is wrong: empty, zero, not a number, too many", () => {
  assert.equal(
    sizes(""),
    "cargá el tamaño de cada piel en m², por ejemplo 1, 2, 2, 5.",
  );
  assert.equal(sizes("  "), sizes(""));
  assert.equal(sizes("0"), 'los tamaños deben ser mayores que 0 (revisá "0").');
  assert.equal(
    sizes("1, 0.0"),
    'los tamaños deben ser mayores que 0 (revisá "0.0").',
  );
  assert.equal(
    sizes("abc"),
    '"abc" no es un tamaño válido: usá números, con punto para los decimales (2.5).',
  );
  assert.equal(
    sizes("-2"),
    '"-2" no es un tamaño válido: usá números, con punto para los decimales (2.5).',
  );
  assert.equal(
    sizes("0x2"),
    'la cantidad de pieles de "0x2" debe ser 1 o más.',
  );
});

test("500 skins are accepted and 501 are refused", () => {
  const ok = leerTamanosDePieles("500x1");
  assert.equal(ok.ok, true);
  assert.equal((ok as { tamanos: string[] }).tamanos.length, 500);
  const tooMany = "no puede haber más de 500 pieles por pedido.";
  assert.equal(sizes("501x1"), tooMany);
  assert.equal(sizes("500x1, 1"), tooMany);
  assert.equal(sizes("99999999999x1"), tooMany);
  assert.equal(
    sizes(Array.from({ length: 501 }, () => "1").join(", ")),
    tooMany,
  );
});

test("the live summary counts skins and sums m2 exactly", () => {
  assert.deepEqual(resumenDePieles("1, 2, 2, 5"), {
    ok: true,
    pieles: 4,
    m2: "10",
  });
  assert.deepEqual(resumenDePieles("3x2, 1, 5"), {
    ok: true,
    pieles: 5,
    m2: "12",
  });
  assert.deepEqual(resumenDePieles("2.5, 0.1, 0.2"), {
    ok: true,
    pieles: 3,
    m2: "2.8",
  });
  assert.deepEqual(resumenDePieles("0.05, 0.05"), {
    ok: true,
    pieles: 2,
    m2: "0.1",
  });
  assert.equal(resumenDePieles("abc").ok, false);
});

test("a leather row is stored under pieles with one price per m2", () => {
  const result = leerPielesDePedido(
    {
      material: "MAT-0002",
      tamanos: "3x2, 1",
      precioPorM2: "20000,50",
      color: "  Negro ",
      moneda: "ARS",
      iva: true,
    },
    1,
  );
  assert.deepEqual(result, {
    ok: true,
    pieles: {
      material: "MAT-0002",
      tamanos: ["2", "2", "2", "1"],
      precio_por_m2: "20000.50",
      moneda: "ARS",
      iva_incluido: true,
      color: "Negro",
    },
  });
});

test("a leather row without color sends no color", () => {
  const result = leerPielesDePedido(
    {
      material: "MAT-0002",
      tamanos: "2.5",
      precioPorM2: "0",
      color: " ",
      moneda: "USD",
      iva: false,
    },
    1,
  );
  assert.equal(result.ok, true);
  assert.equal("color" in (result as { pieles: object }).pieles, false);
});

test("a leather row names the first thing that is wrong", () => {
  const base = {
    material: "MAT-0002",
    tamanos: "1, 2",
    precioPorM2: "100",
    color: "",
    moneda: "ARS",
    iva: false,
  };
  const fail = (patch: Partial<typeof base>) =>
    leerPielesDePedido({ ...base, ...patch }, 2);
  assert.deepEqual(fail({ material: "" }), {
    ok: false,
    message: "Línea 2: elija el material.",
  });
  assert.deepEqual(fail({ tamanos: "" }), {
    ok: false,
    message:
      "Línea 2: cargá el tamaño de cada piel en m², por ejemplo 1, 2, 2, 5.",
  });
  assert.deepEqual(fail({ tamanos: "0" }), {
    ok: false,
    message: 'Línea 2: los tamaños deben ser mayores que 0 (revisá "0").',
  });
  assert.equal(fail({ tamanos: "abc" }).ok, false);
  assert.equal(fail({ tamanos: "501x1" }).ok, false);
  assert.deepEqual(fail({ precioPorM2: "" }), {
    ok: false,
    message: "Línea 2: ingrese el precio por m², por ejemplo 20000 o 18500,50.",
  });
  assert.deepEqual(fail({ moneda: "EUR" }), {
    ok: false,
    message: "Línea 2: elija la moneda.",
  });
  assert.equal(fail({}).ok, true);
});

test("what arrived reads as skins for a leather line", () => {
  const line = (cantidad: string) => ({
    cantidad_presentaciones: cantidad,
    presentacion: "PIEL",
    contenido_por_presentacion: "2.000000",
    unidad_de_consumo: "m2",
  });
  assert.equal(llegoTexto(line("3.000000")), "3 pieles × 2 m²");
  assert.equal(llegoTexto(line("1.000000")), "1 piel × 2 m²");
});
