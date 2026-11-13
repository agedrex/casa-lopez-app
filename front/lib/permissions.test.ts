import assert from "node:assert/strict";
import { test } from "node:test";
import { desktopNavForRole, mobileTabs, navForRole } from "./nav";
import { canAccessPath, homePath, isTallerOnly } from "./permissions";

test("gerente opens nothing under /admin, not even the Panel (S8)", () => {
  for (const path of [
    "/admin",
    "/admin/panel",
    "/admin/usuarios",
    "/admin/impuestos",
    "/admin/panel/otro",
  ]) {
    assert.equal(canAccessPath("gerente", path), false, path);
  }
});

test("taller and users without a role are refused the Panel", () => {
  assert.equal(canAccessPath("taller", "/admin/panel"), false);
  assert.equal(canAccessPath(null, "/admin/panel"), false);
});

test("admin opens the whole admin area", () => {
  assert.equal(canAccessPath("admin", "/admin/panel"), true);
  assert.equal(canAccessPath("admin", "/admin/usuarios"), true);
});

test("gerente opens Productos, Modelos and the scenario simulator", () => {
  for (const path of [
    "/productos",
    "/productos/PRD-1",
    "/productos/modelos",
    "/productos/modelos/MOD-1",
    "/escenarios",
  ]) {
    assert.equal(canAccessPath("gerente", path), true, path);
  }
});

test("gerente is refused Lotes, Formularios, Cueros, Proveedores, Talleres and every write form", () => {
  for (const path of [
    "/fabricacion",
    "/fabricacion/LOT-1",
    "/formularios",
    "/formularios/FCO-1",
    "/cueros",
    "/cueros/PZC-1",
    "/proveedores",
    "/proveedores/PRV-1",
    "/talleres",
    "/talleres/TAL-1",
    "/fabricacion/nuevo",
    "/talleres/nuevo",
    "/productos/nuevo",
    "/productos/modelos/nuevo",
    "/productos/catalogos",
    "/materiales",
    "/costos-fijos",
    "/corte",
    "/voz",
  ]) {
    assert.equal(canAccessPath("gerente", path), false, path);
  }
});

test("gerente lands on /productos", () => {
  assert.equal(homePath("gerente"), "/productos");
  assert.equal(homePath("consulta"), "/productos");
});

test("taller and users without a role are refused the scenario simulator; admin opens it", () => {
  assert.equal(canAccessPath("taller", "/escenarios"), false);
  assert.equal(canAccessPath(null, "/escenarios"), false);
  assert.equal(canAccessPath("admin", "/escenarios"), true);
});

test("taller has one entry (Lotes): it opens lots, Formularios, Voz and the product sheet only", () => {
  for (const path of [
    "/fabricacion",
    "/fabricacion/LOT-1",
    "/formularios",
    "/formularios/FCO-1",
    "/voz",
    "/productos/PRD-1",
  ]) {
    assert.equal(canAccessPath("taller", path), true, path);
  }
  for (const path of [
    "/productos",
    "/productos/modelos",
    "/productos/modelos/MOD-1",
    "/productos/nuevo",
    "/productos/catalogos",
    "/fabricacion/nuevo",
    "/corte",
    "/cueros",
    "/cueros/PZC-1",
    "/materiales",
    "/talleres",
    "/proveedores",
    "/costos-fijos",
    "/escenarios",
    "/admin/panel",
  ]) {
    assert.equal(canAccessPath("taller", path), false, path);
  }
});

test("taller lands on the lots list", () => {
  assert.equal(homePath("taller"), "/fabricacion");
  assert.equal(homePath("corte"), "/fabricacion");
});

test("a user with admin and taller keeps the admin access (the taller holes do not apply)", () => {
  for (const path of [
    "/productos",
    "/productos/modelos",
    "/corte",
    "/fabricacion/nuevo",
  ]) {
    assert.equal(canAccessPath("taller,admin", path), true, path);
  }
});

test("the gerente menu lists only Productos, Modelos and Escenarios, and each entry is a path it can open", () => {
  const hrefs = (groups: { items: { href: string }[] }[]) =>
    groups.flatMap((group) => group.items.map((item) => item.href));
  for (const groups of [
    desktopNavForRole(["gerente"]),
    navForRole(["gerente"]),
  ]) {
    assert.deepEqual(hrefs(groups), [
      "/productos",
      "/productos/modelos",
      "/escenarios",
    ]);
    for (const href of hrefs(groups)) {
      assert.equal(canAccessPath("gerente", href), true, href);
    }
  }
  const tabs = mobileTabs(navForRole(["gerente"]), ["gerente"]);
  assert.deepEqual(
    tabs.map((tab) => tab.href),
    ["/productos", "/escenarios"],
  );
});

test("the taller menu lists only Lotes and Formularios, and each entry is a path it can open", () => {
  const hrefs = (groups: { items: { href: string }[] }[]) =>
    groups.flatMap((group) => group.items.map((item) => item.href));
  for (const groups of [
    desktopNavForRole(["taller"]),
    navForRole(["taller"]),
  ]) {
    assert.deepEqual(hrefs(groups), ["/fabricacion", "/formularios"]);
    for (const href of hrefs(groups)) {
      assert.equal(canAccessPath("taller", href), true, href);
    }
  }
  const tabs = mobileTabs(navForRole(["taller"]), ["taller"]);
  assert.deepEqual(
    tabs.map((tab) => tab.href),
    ["/fabricacion", "/formularios"],
  );
});

test("taller is a taller-only user; admin is not", () => {
  assert.equal(isTallerOnly("taller"), true);
  assert.equal(isTallerOnly("corte"), true);
  assert.equal(isTallerOnly("taller,admin"), false);
  assert.equal(isTallerOnly("gerente"), false);
});
