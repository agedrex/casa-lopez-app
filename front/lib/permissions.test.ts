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

test("gerente reads Producción and Abastecimiento but not the write forms", () => {
  for (const path of [
    "/fabricacion",
    "/fabricacion/LOT-1",
    "/cueros",
    "/talleres",
    "/proveedores/PRV-1",
    "/productos/modelos",
  ]) {
    assert.equal(canAccessPath("gerente", path), true, path);
  }
  for (const path of [
    "/fabricacion/nuevo",
    "/talleres/nuevo",
    "/productos/nuevo",
    "/productos/catalogos",
    "/materiales",
    "/costos-fijos",
  ]) {
    assert.equal(canAccessPath("gerente", path), false, path);
  }
});

test("taller keeps Corte, Cueros and Voz and reads what quoting a product needs", () => {
  for (const path of [
    "/corte",
    "/cueros",
    "/voz",
    "/productos",
    "/productos/PRD-1",
    "/productos/modelos",
    "/materiales",
  ]) {
    assert.equal(canAccessPath("taller", path), true, path);
  }
  for (const path of [
    "/productos/nuevo",
    "/productos/modelos/nuevo",
    "/productos/catalogos",
    "/fabricacion",
    "/talleres",
    "/proveedores",
    "/costos-fijos",
  ]) {
    assert.equal(canAccessPath("taller", path), false, path);
  }
});
