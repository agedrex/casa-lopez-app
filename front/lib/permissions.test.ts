import assert from "node:assert/strict";
import { test } from "node:test";
import { canAccessPath } from "./permissions";

test("gerente opens the Panel and nothing else under /admin", () => {
  assert.equal(canAccessPath("gerente", "/admin/panel"), true);
  for (const path of [
    "/admin",
    "/admin/usuarios",
    "/admin/impuestos",
    "/admin/panel/otro",
  ]) {
    assert.equal(canAccessPath("gerente", path), false, path);
  }
});

test("taller and users without a role are still refused the Panel", () => {
  assert.equal(canAccessPath("taller", "/admin/panel"), false);
  assert.equal(canAccessPath(null, "/admin/panel"), false);
});

test("admin opens the whole admin area", () => {
  assert.equal(canAccessPath("admin", "/admin/panel"), true);
  assert.equal(canAccessPath("admin", "/admin/usuarios"), true);
});
