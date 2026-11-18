import assert from "node:assert/strict";
import { test } from "node:test";
import {
  describeValidationErrors,
  FIELD_LABELS,
  readErrorBody,
} from "./errores-campos";

const issue = (
  loc: (string | number)[],
  type: string,
  ctx?: object,
  msg = "",
) => ({
  loc: ["body", ...loc],
  type,
  msg,
  ...(ctx ? { ctx } : {}),
});

test("a negative consumption says the human name of the field and the limit, never the internal name", () => {
  const text = describeValidationErrors([
    issue(["cuero_m2_por_unidad"], "greater_than_equal", { ge: 0 }),
  ]);
  assert.equal(
    text,
    "El consumo de cuero por unidad debe ser mayor o igual a 0.",
  );
  assert.ok(!text.includes("cuero_m2_por_unidad"));
});

test("a missing field, a short text and a bad number are told in Spanish", () => {
  assert.equal(
    describeValidationErrors([issue(["fecha_de_envio"], "missing")]),
    "Falta completar la fecha de envío.",
  );
  assert.equal(
    describeValidationErrors([
      issue(["nombre_del_modelo"], "string_too_short", { min_length: 1 }),
    ]),
    "Falta completar el nombre del modelo.",
  );
  assert.equal(
    describeValidationErrors([issue(["precio"], "decimal_parsing")]),
    "El precio tiene que ser un número.",
  );
  assert.equal(
    describeValidationErrors([issue(["m2"], "greater_than", { gt: "0" })]),
    "La superficie en m² debe ser mayor que 0.",
  );
});

test("decimals, digits, dates and options have their own sentence", () => {
  assert.equal(
    describeValidationErrors([
      issue(["precio"], "decimal_max_places", { decimal_places: 4 }),
    ]),
    "El precio admite como máximo 4 decimales.",
  );
  assert.equal(
    describeValidationErrors([issue(["fecha"], "date_from_datetime_parsing")]),
    "La fecha tiene que ser una fecha válida (día, mes y año).",
  );
  assert.equal(
    describeValidationErrors([issue(["moneda"], "literal_error")]),
    "La moneda no es una de las opciones permitidas.",
  );
});

test("the failing row of a list is named: Línea 2, Piel 1", () => {
  assert.equal(
    describeValidationErrors([
      issue(["lineas", 1, "cantidad_presentaciones"], "greater_than", {
        gt: "0",
      }),
      issue(["pieles", 0, "precio_por_m2"], "missing"),
    ]),
    "Línea 2: La cantidad de presentaciones debe ser mayor que 0. Piel 1: Falta completar el precio por m².",
  );
});

test("our own validators keep their Spanish text without the Pydantic prefix", () => {
  assert.equal(
    describeValidationErrors(
      [
        issue(
          [],
          "value_error",
          {},
          "Value error, Indicá el precio cotizado, el pagado o los dos.",
        ),
      ].map((i) => ({ ...i, loc: ["body", "cotizado"] })),
    ),
    "Indicá el precio cotizado, el pagado o los dos.",
  );
});

test("the same message is said once and a long list is cut", () => {
  const same = describeValidationErrors([
    issue(["nota"], "string_too_long", { max_length: 2000 }),
    issue(["nota"], "string_too_long", { max_length: 2000 }),
  ]);
  assert.equal(same, "La nota admite como máximo 2000 caracteres.");
  const many = describeValidationErrors(
    ["precio", "moneda", "fecha", "nota", "cuit", "telefono"].map((f) =>
      issue([f], "missing"),
    ),
  );
  assert.match(many, /\(y 2 errores más\)\.$/);
});

test("an unknown field is shown without underscores and an empty list falls back to the generic text", () => {
  assert.equal(
    describeValidationErrors([issue(["campo_nuevo_raro"], "missing")]),
    "Falta completar el dato «campo nuevo raro».",
  );
  assert.equal(describeValidationErrors([]), "Revise los datos ingresados.");
  assert.equal(
    describeValidationErrors([{ type: "json_invalid" }]),
    "Revise los datos ingresados.",
  );
});

test("no label shows an internal name", () => {
  for (const [name, label] of Object.entries(FIELD_LABELS)) {
    assert.ok(!label.includes("_"), `${name}: ${label}`);
    assert.ok(
      /^(el|la|los|las|dónde|quién)\b/.test(label),
      `${name}: ${label}`,
    );
  }
});

test("an error body of the API gives its text and its avisos; a 422 list is humanized", () => {
  assert.deepEqual(
    readErrorBody({ detail: "Ya hay un precio.", avisos: ["a", 3, "b"] }),
    { detail: "Ya hay un precio.", avisos: ["a", "b"] },
  );
  assert.deepEqual(
    readErrorBody({
      detail: [
        issue(["cuero_m2_por_unidad"], "greater_than_equal", { ge: "0" }),
      ],
    }),
    {
      detail: "El consumo de cuero por unidad debe ser mayor o igual a 0.",
      avisos: [],
    },
  );
  assert.deepEqual(readErrorBody(null), { detail: "", avisos: [] });
  assert.deepEqual(readErrorBody({ detail: 5 }), { detail: "", avisos: [] });
});
