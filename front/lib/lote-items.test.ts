import assert from "node:assert/strict";
import { test } from "node:test";
import { readItems } from "./lote-items";

function form(filas: Record<string, string>[]): FormData {
  const data = new FormData();
  for (const fila of filas) {
    for (const campo of ["producto", "cantidad", "pagado", "cotizado"]) {
      data.append(campo, fila[campo] ?? "");
    }
  }
  return data;
}

test("readItems lee las filas paralelas y deja los precios vacíos en null", () => {
  const items = readItems(
    form([
      { producto: "PRD-1", cantidad: "10" },
      { producto: "PRD-2", cantidad: "2,5", pagado: "1500", cotizado: "1.600" },
    ]),
  );
  assert.deepEqual(items, [
    {
      producto: "PRD-1",
      cantidad: "10",
      taller_precio_pagado_por_unidad_ars: null,
      taller_precio_cotizado_por_unidad_ars: null,
    },
    {
      producto: "PRD-2",
      cantidad: "2.5",
      taller_precio_pagado_por_unidad_ars: "1500",
      taller_precio_cotizado_por_unidad_ars: "1.600",
    },
  ]);
});

test("readItems pide al menos un producto", () => {
  assert.deepEqual(readItems(form([])), {
    status: "error",
    message: "Agregue al menos un producto al lote.",
    avisos: [],
  });
  assert.equal(
    (readItems(form([{}, {}])) as { message: string }).message,
    "Agregue al menos un producto al lote.",
  );
});

test("readItems rechaza una cantidad en cero o sin número, con el número de fila", () => {
  const cero = readItems(form([{ producto: "PRD-1", cantidad: "0" }]));
  assert.equal(
    (cero as { message: string }).message,
    "Producto 1: ingrese una cantidad mayor que cero.",
  );
  const vacia = readItems(
    form([
      { producto: "PRD-1", cantidad: "1" },
      { producto: "PRD-2", cantidad: "" },
    ]),
  );
  assert.equal(
    (vacia as { message: string }).message,
    "Producto 2: ingrese una cantidad mayor que cero.",
  );
});

test("readItems rechaza precios mal escritos y cantidad sin producto", () => {
  assert.equal(
    (
      readItems(
        form([{ producto: "PRD-1", cantidad: "1", pagado: "mucho" }]),
      ) as { message: string }
    ).message,
    "Producto 1: el precio pagado no es un número válido.",
  );
  assert.equal(
    (readItems(form([{ cantidad: "4" }])) as { message: string }).message,
    "Producto 1: indique el código del producto.",
  );
});
