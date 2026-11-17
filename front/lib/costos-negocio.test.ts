import assert from "node:assert/strict";
import { test } from "node:test";
import { cueroYColor, retazosSinPrecioAviso } from "./costos-negocio";

test("no notice when every remainder has a price", () => {
  assert.equal(retazosSinPrecioAviso(0), null);
});

test("notice counts the remainders without price", () => {
  assert.equal(
    retazosSinPrecioAviso(1),
    "Hay 1 retazo sin precio: el total no lo incluye.",
  );
  assert.equal(
    retazosSinPrecioAviso(3),
    "Hay 3 retazos sin precio: el total no los incluye.",
  );
});

test("leather and color are joined, color is optional", () => {
  assert.equal(
    cueroYColor("Cuero estándar", "Negro"),
    "Cuero estándar · Negro",
  );
  assert.equal(cueroYColor("Cuero estándar", null), "Cuero estándar");
});
