import assert from "node:assert/strict";
import { test } from "node:test";
import {
  accionesDeHoja,
  agregarFila,
  armarLineas,
  type FilaHoja,
  filasDeHoja,
  modoDeHoja,
  quitarFila,
  renombrarFila,
  SECCIONES,
} from "./formularios";
import type { FormularioEstado, FormularioLinea } from "./types";

function linea(
  nombre: string,
  extra: Partial<FormularioLinea> = {},
): FormularioLinea {
  return {
    seccion: "CONSUMO",
    orden: 1,
    nombre,
    cantidad: null,
    comentario: null,
    unidad: "m²",
    ...extra,
  };
}

const ESTADOS: FormularioEstado[] = [
  "BORRADOR",
  "ENVIADO",
  "COMPLETADO",
  "VALIDADO",
];

test("the admin edits the whole sheet while it is a draft, sent or in review, and only reads it once validated", () => {
  assert.deepEqual(
    ESTADOS.map((estado) => modoDeHoja("admin", estado)),
    ["editar", "editar", "revisar", "leer"],
  );
});

test("the taller edits only while the sheet is waiting for it and reads in any other state", () => {
  assert.deepEqual(
    ESTADOS.map((estado) => modoDeHoja("taller", estado)),
    ["leer", "editar", "leer", "leer"],
  );
});

test("nobody else edits, and admin wins when a user holds both roles", () => {
  assert.equal(modoDeHoja("gerente", "ENVIADO"), "leer");
  assert.equal(modoDeHoja(null, "ENVIADO"), "leer");
  assert.equal(modoDeHoja("taller,admin", "BORRADOR"), "editar");
});

test("each role gets its own buttons: the admin sends a draft to the workshop, the taller completes", () => {
  assert.deepEqual(accionesDeHoja("admin", "BORRADOR"), ["guardar", "enviar"]);
  assert.deepEqual(accionesDeHoja("admin", "ENVIADO"), ["guardar"]);
  assert.deepEqual(accionesDeHoja("admin", "COMPLETADO"), ["guardar"]);
  assert.deepEqual(accionesDeHoja("admin", "VALIDADO"), []);
  assert.deepEqual(accionesDeHoja("taller", "ENVIADO"), [
    "guardar",
    "completar",
  ]);
  assert.deepEqual(accionesDeHoja("taller", "BORRADOR"), []);
  assert.deepEqual(accionesDeHoja("taller", "COMPLETADO"), []);
  assert.deepEqual(accionesDeHoja("gerente", "ENVIADO"), []);
});

test("the sections no longer promise m² for every row: the unit lives on each row", () => {
  assert.deepEqual(
    SECCIONES.map((s) => s.unit),
    ["m²", "unidades"],
  );
});

test("rows keep the unit the API gave them and get a stable id", () => {
  const filas = filasDeHoja([
    linea("CUERO", { cantidad: "0.400000" }),
    linea("HS. DE TRABAJO", { unidad: "horas", orden: 2 }),
  ]);
  assert.deepEqual(
    filas.map((f) => [f.nombre, f.cantidad, f.unidad]),
    [
      ["CUERO", "0,4", "m²"],
      ["HS. DE TRABAJO", "", "horas"],
    ],
  );
  assert.equal(new Set(filas.map((f) => f.id)).size, 2);
});

test("the retired DESPERDICIO 30% row is hidden only while it is empty: a typed quantity is never lost", () => {
  const vacia = filasDeHoja([
    linea("CUERO"),
    linea("DESPERDICIO 30%", { orden: 2 }),
  ]);
  assert.deepEqual(
    vacia.map((f) => f.nombre),
    ["CUERO"],
  );
  const conCantidad = filasDeHoja([
    linea("DESPERDICIO 30%", { cantidad: "0.13" }),
  ]);
  assert.deepEqual(
    conCantidad.map((f) => f.nombre),
    ["DESPERDICIO 30%"],
  );
  const conComentario = filasDeHoja([
    linea("  desperdicio  30% ", { comentario: "ver con el taller" }),
  ]);
  assert.equal(conComentario.length, 1);
});

function base(): FilaHoja[] {
  return filasDeHoja([
    linea("CUERO"),
    linea("FLEX", { orden: 2 }),
    linea("CIERRE N5", { seccion: "HERRAJE", unidad: "unidades" }),
  ]);
}

test("adding a row puts it at the end of its section, empty, with the default unit of the section", () => {
  const filas = agregarFila(base(), "CONSUMO", "nueva-1");
  assert.deepEqual(
    filas.map((f) => f.nombre),
    ["CUERO", "FLEX", "", "CIERRE N5"],
  );
  assert.deepEqual(filas[2], {
    id: "nueva-1",
    seccion: "CONSUMO",
    nombre: "",
    cantidad: "",
    comentario: "",
    unidad: "m²",
  });
  const herraje = agregarFila(base(), "HERRAJE", "nueva-2");
  assert.equal(herraje[herraje.length - 1].unidad, "unidades");
  assert.equal(herraje[herraje.length - 1].seccion, "HERRAJE");
});

test("removing a row drops only that row; renaming resets the unit to the section default", () => {
  const filas = base();
  assert.deepEqual(
    quitarFila(filas, filas[1].id).map((f) => f.nombre),
    ["CUERO", "CIERRE N5"],
  );
  const horas = filasDeHoja([linea("HS. DE TRABAJO", { unidad: "horas" })]);
  const renombrada = renombrarFila(horas, horas[0].id, "TIEMPO");
  assert.equal(renombrada[0].nombre, "TIEMPO");
  assert.equal(renombrada[0].unidad, "m²");
  assert.equal(horas[0].nombre, "HS. DE TRABAJO"); // the original list is untouched
});

test("armarLineas skips a row that is completely empty (the one just added and never used)", () => {
  const filas = agregarFila(base(), "CONSUMO", "nueva-1");
  const armadas = armarLineas(filas);
  assert.ok(armadas.ok);
  assert.deepEqual(
    armadas.lineas.map((l) => l.nombre),
    ["CUERO", "FLEX", "CIERRE N5"],
  );
});

test("armarLineas still asks for a name when the row has a quantity or a comment, and sends the names trimmed", () => {
  const sinNombre = base().concat({
    ...agregarFila([], "CONSUMO", "x")[0],
    cantidad: "2",
  });
  const rechazada = armarLineas(sinNombre);
  assert.equal(rechazada.ok, false);
  const conNombre = armarLineas([
    {
      ...agregarFila([], "HERRAJE", "y")[0],
      nombre: "  BROCHE   ESPECIAL ",
      cantidad: "3",
    },
  ]);
  assert.ok(conNombre.ok);
  assert.deepEqual(conNombre.lineas, [
    {
      seccion: "HERRAJE",
      nombre: "BROCHE ESPECIAL",
      cantidad: "3",
      comentario: null,
    },
  ]);
});

test("armarLineas keeps its old rules: comma decimals, empty quantity is null, a bad number names the row", () => {
  const filas = filasDeHoja([linea("CUERO"), linea("FLEX", { orden: 2 })]);
  filas[0].cantidad = "0,25";
  const ok = armarLineas(filas);
  assert.ok(ok.ok);
  assert.deepEqual(
    ok.lineas.map((l) => l.cantidad),
    ["0.25", null],
  );
  filas[1].cantidad = "abc";
  const mala = armarLineas(filas);
  assert.equal(mala.ok, false);
  assert.match(mala.ok ? "" : mala.message, /FLEX/);
});
