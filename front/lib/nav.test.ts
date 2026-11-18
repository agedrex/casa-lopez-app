import assert from "node:assert/strict";
import { test } from "node:test";
import { mobileTabs, navForRole } from "./nav";
import type { Role } from "./permissions";

const hrefs = (roles: Role[]) =>
  mobileTabs(navForRole(roles), roles).map((tab) => tab.href);

test("S5: the taller bottom bar has Lotes and Voz", () => {
  assert.deepEqual(hrefs(["taller"]), ["/fabricacion", "/voz"]);
});

test("S5: Corte stays out of the taller menu (the route is closed to the role)", () => {
  const items = navForRole(["taller"]).flatMap((group) => group.items);
  assert.ok(items.every((item) => item.href !== "/corte"));
});

test("PRESERVE: admin and gerente keep their bottom bars", () => {
  assert.deepEqual(hrefs(["admin"]), [
    "/admin/panel",
    "/productos",
    "/fabricacion",
  ]);
  assert.deepEqual(hrefs(["gerente"]), ["/productos", "/escenarios"]);
});
