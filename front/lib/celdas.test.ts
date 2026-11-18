import assert from "node:assert/strict";
import { test } from "node:test";
import { cellError, mostrarErrorDeCelda } from "./celdas";

const requerida = { kind: "text", required: true } as const;
const monto = { kind: "decimal" } as const;

test("una celda requerida vacía falla con 'Falta completar.' y no es inmediata", () => {
  assert.deepEqual(cellError(requerida, "  ", "Luz", false), {
    message: "Falta completar.",
    immediate: false,
  });
});

test("una celda requerida con texto no falla", () => {
  assert.equal(cellError(requerida, "Luz", "", true), null);
});

test("un número inválido falla y es inmediato; uno válido no", () => {
  assert.deepEqual(cellError(monto, "abc", "", false), {
    message: "No es un número válido. Ejemplo: 0,25.",
    immediate: true,
  });
  assert.equal(cellError(monto, "1545,5", "", false), null);
  assert.equal(cellError(monto, "", "", false), null);
});

test("la validación propia de la columna se informa sin ser inmediata", () => {
  const vaciable = {
    kind: "decimal",
    validate: (value: string, ctx: { original: string; isNew: boolean }) =>
      !ctx.isNew && ctx.original !== "" && value === "" ? "No se vacía." : null,
  } as const;
  assert.deepEqual(cellError(vaciable, "", "100", false), {
    message: "No se vacía.",
    immediate: false,
  });
});

test("el error se muestra al salir de la celda, no antes", () => {
  const falta = { message: "Falta completar.", immediate: false };
  assert.equal(
    mostrarErrorDeCelda(falta, { visited: false, attempted: false }),
    false,
  );
  assert.equal(
    mostrarErrorDeCelda(falta, { visited: true, attempted: false }),
    true,
  );
});

test("el error se muestra al intentar guardar aunque no se haya salido de la celda", () => {
  const falta = { message: "Falta completar.", immediate: false };
  assert.equal(
    mostrarErrorDeCelda(falta, { visited: false, attempted: true }),
    true,
  );
});

test("un error inmediato se muestra siempre y sin error no se muestra nada", () => {
  const numero = { message: "No es un número válido.", immediate: true };
  assert.equal(
    mostrarErrorDeCelda(numero, { visited: false, attempted: false }),
    true,
  );
  assert.equal(
    mostrarErrorDeCelda(null, { visited: true, attempted: true }),
    false,
  );
  assert.equal(
    mostrarErrorDeCelda(undefined, { visited: true, attempted: true }),
    false,
  );
});
