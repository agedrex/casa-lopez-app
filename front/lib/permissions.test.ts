import assert from "node:assert/strict";
import { test } from "node:test";
import { desktopNavForRole, mobileTabs, navForRole } from "./nav";
import { canAccessPath, homePath } from "./permissions";

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

test("the taller menu is unchanged by S8", () => {
  const hrefs = desktopNavForRole(["taller"]).flatMap((group) =>
    group.items.map((item) => item.href),
  );
  assert.deepEqual(hrefs, [
    "/corte",
    "/cueros",
    "/formularios",
    "/productos",
    "/productos/modelos",
    "/materiales",
  ]);
});
