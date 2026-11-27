import assert from "node:assert/strict";
import { test } from "node:test";
import {
  environmentProblem,
  isEntorno,
  parseArgs,
} from "./set-password-guards";

test("lee las tres opciones", () => {
  const options = parseArgs([
    "--email",
    "alguien@ejemplo.com",
    "--entorno",
    "production",
    "--confirmar",
  ]);
  assert.deepEqual(options, {
    email: "alguien@ejemplo.com",
    entorno: "production",
    confirmar: true,
  });
});

test("sin argumentos queda en dry-run y sin email", () => {
  assert.deepEqual(parseArgs([]), {
    email: null,
    entorno: null,
    confirmar: false,
  });
});

test("una bandera no se consume como valor de --email", () => {
  const options = parseArgs(["--email", "--confirmar"]);
  assert.equal(options.email, null);
  assert.equal(options.confirmar, true);
});

test("una bandera no se consume como valor de --entorno", () => {
  const options = parseArgs(["--entorno", "--confirmar"]);
  assert.equal(options.entorno, null);
  assert.equal(options.confirmar, true);
});

test("--entorno sin valor al final queda en null", () => {
  assert.equal(parseArgs(["--entorno"]).entorno, null);
});

test("con banderas repetidas gana la última", () => {
  const options = parseArgs([
    "--entorno",
    "staging",
    "--entorno",
    "production",
  ]);
  assert.equal(options.entorno, "production");
});

test("un typo en --confirmar no confirma nada", () => {
  const options = parseArgs(["--email", "a@b.com", "--confimar"]);
  assert.equal(options.confirmar, false);
});

test("el entorno es una lista cerrada y sensible a mayúsculas", () => {
  assert.equal(isEntorno("staging"), true);
  assert.equal(isEntorno("production"), true);
  assert.equal(isEntorno("Production"), false);
  assert.equal(isEntorno("entorno=production"), false);
  assert.equal(isEntorno(null), false);
});

test("sin entorno de Railway, production se rechaza y staging se permite", () => {
  assert.notEqual(environmentProblem("production", undefined), null);
  assert.equal(environmentProblem("staging", undefined), null);
});

test("un entorno de Railway vacío se trata como ausente", () => {
  assert.notEqual(environmentProblem("production", ""), null);
  assert.equal(environmentProblem("staging", ""), null);
});

test("un entorno de Railway que no coincide se rechaza", () => {
  assert.notEqual(environmentProblem("production", "staging"), null);
  assert.notEqual(environmentProblem("staging", "production"), null);
});

test("un entorno de Railway que coincide se permite", () => {
  assert.equal(environmentProblem("production", "production"), null);
  assert.equal(environmentProblem("staging", "staging"), null);
});

test("el mensaje nunca repite el valor del entorno de Railway", () => {
  const problem = environmentProblem("production", "secreto-interno");
  assert.ok(problem);
  assert.ok(!problem.includes("secreto-interno"));
});
