import assert from "node:assert/strict";
import { test } from "node:test";
import {
  agregarProducto,
  consultaDeBusqueda,
  type FilaDeLote,
  quitarProducto,
  RESULT_LIMIT,
  responsableDelLote,
  resultadosDeBusqueda,
  rutaDeBusqueda,
} from "./lote-buscador";
import type { ProductoResumen } from "./types";

function resumen(codigo: string, nombre = `Producto ${codigo}`) {
  return {
    codigo,
    nombre,
    categoria: "Carteras",
    modelo: "MOD-0001",
    estado_del_ciclo: "COTIZADO",
    es_kit: false,
    costo_hoy_ars: "1000.00",
    costo_hoy_usd: "1.00",
    avisos: [],
    revisar: false,
    motivos_revisar: [],
    precio_venta_ars: null,
    margen_pct: null,
    precio_final_ars: null,
  } satisfies ProductoResumen;
}

test("consultaDeBusqueda colapsa espacios y exige 2 caracteres", () => {
  assert.equal(consultaDeBusqueda("  cartera   negra "), "cartera negra");
  assert.equal(consultaDeBusqueda(" a "), null);
  assert.equal(consultaDeBusqueda("   "), null);
  assert.equal(consultaDeBusqueda("PRD"), "PRD");
});

test("consultaDeBusqueda corta lo que la API rechazaría (más de 100 caracteres)", () => {
  assert.equal(consultaDeBusqueda("a".repeat(150))?.length, 100);
});

test("rutaDeBusqueda pide un resultado más que el límite y escapa el texto", () => {
  const ruta = rutaDeBusqueda("bolso & co");
  assert.equal(ruta, `/productos?limit=${RESULT_LIMIT + 1}&q=bolso%20%26%20co`);
});

test("resultadosDeBusqueda no deja pasar plata y marca si hay más", () => {
  const filas = Array.from({ length: RESULT_LIMIT + 1 }, (_, i) =>
    resumen(`PRD-${i}`),
  );
  const { resultados, hayMas } = resultadosDeBusqueda(filas);
  assert.equal(resultados.length, RESULT_LIMIT);
  assert.equal(hayMas, true);
  assert.deepEqual(resultados[0], {
    codigo: "PRD-0",
    nombre: "Producto PRD-0",
    modelo: "MOD-0001",
    categoria: "Carteras",
  });
  assert.equal(resultadosDeBusqueda(filas.slice(0, 3)).hayMas, false);
});

test("resultadosDeBusqueda acomoda los espacios del nombre", () => {
  const { resultados } = resultadosDeBusqueda([
    resumen("PRD-1", "Cartera   Fucsia "),
  ]);
  assert.equal(resultados[0].nombre, "Cartera Fucsia");
});

const resultado = (codigo: string) => ({
  codigo,
  nombre: codigo,
  modelo: null,
  categoria: null,
});

test("agregarProducto suma varios productos y no repite el mismo", () => {
  let filas: FilaDeLote[] = [];
  filas = agregarProducto(filas, resultado("PRD-1"), 0);
  filas = agregarProducto(filas, resultado("PRD-2"), 1);
  filas = agregarProducto(filas, resultado("PRD-1"), 2);
  assert.deepEqual(
    filas.map((f) => [f.id, f.producto, f.cantidad]),
    [
      [0, "PRD-1", ""],
      [1, "PRD-2", ""],
    ],
  );
});

test("quitarProducto saca solo esa fila, hasta dejar el lote vacío", () => {
  const filas: FilaDeLote[] = [
    { id: 0, producto: "PRD-1", nombre: "Uno", cantidad: "3" },
    { id: 1, producto: "PRD-2", nombre: "Dos", cantidad: "" },
  ];
  assert.deepEqual(
    quitarProducto(filas, 0).map((f) => f.producto),
    ["PRD-2"],
  );
  assert.deepEqual(quitarProducto(quitarProducto(filas, 0), 1), []);
});

test("responsableDelLote: fábrica es INTERNA sin taller, un taller es EXTERNA", () => {
  assert.deepEqual(responsableDelLote("FABRICA"), {
    donde: "INTERNA",
    taller: "",
  });
  assert.deepEqual(responsableDelLote("TAL-0001"), {
    donde: "EXTERNA",
    taller: "TAL-0001",
  });
  assert.deepEqual(responsableDelLote(""), { donde: "EXTERNA", taller: "" });
});
