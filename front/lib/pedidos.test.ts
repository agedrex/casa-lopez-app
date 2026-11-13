import assert from "node:assert/strict";
import { test } from "node:test";
import { PRESENTACIONES, unitPricePreview } from "./pedidos";

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
