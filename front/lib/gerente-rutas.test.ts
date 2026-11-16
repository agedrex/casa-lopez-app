import assert from "node:assert/strict";
import { readdirSync } from "node:fs";
import { join } from "node:path";
import { test } from "node:test";
import { canAccessPath } from "./permissions";

/** Every page of `app/(app)` as a path, with a sample value in each dynamic segment. */
function appRoutes(dir = join(process.cwd(), "app", "(app)")): string[] {
  const found: string[] = [];
  const walk = (current: string, segments: string[]) => {
    for (const entry of readdirSync(current, { withFileTypes: true })) {
      if (entry.isDirectory()) {
        walk(join(current, entry.name), [...segments, entry.name]);
      } else if (entry.name === "page.tsx") {
        found.push(
          `/${segments.map((s) => (s.startsWith("[") ? "X-1" : s)).join("/")}`.replace(
            /\/$/,
            "",
          ) || "/",
        );
      }
    }
  };
  walk(dir, []);
  return found.sort();
}

// What the gerente opens (S8): Productos (list and sheet), Modelos (list and sheet) and the scenario simulator. Nothing else.
const RUTAS_DEL_GERENTE = [
  "/escenarios",
  "/productos",
  "/productos/X-1",
  "/productos/modelos",
  "/productos/modelos/X-1",
];

test("the pages the gerente opens are exactly Productos, Modelos and Escenarios (S8)", () => {
  const routes = appRoutes();
  assert.ok(routes.includes("/productos/X-1"), "the page scan found nothing");
  const abiertas = routes.filter((route) => canAccessPath("gerente", route));
  assert.deepEqual(abiertas, RUTAS_DEL_GERENTE);
});

test("the legacy role consulta opens the same pages as gerente", () => {
  const abiertas = appRoutes().filter((route) =>
    canAccessPath("consulta", route),
  );
  assert.deepEqual(abiertas, RUTAS_DEL_GERENTE);
});

test("the gerente opens none of the admin only pages under /productos", () => {
  for (const path of ["/productos/nuevo", "/productos/modelos/nuevo"]) {
    assert.equal(canAccessPath("gerente", path), false, path);
  }
});

// What the taller opens: the lots (list and detail), Voz, the product sheet and the three screens of the new model flow
// (modelo-taller-foto T4: my models, new model and the sheet of a model). Nothing else.
const RUTAS_DEL_TALLER = [
  "/fabricacion",
  "/fabricacion/X-1",
  "/productos/X-1",
  "/taller/modelos",
  "/taller/modelos/X-1",
  "/taller/modelos/nuevo",
  "/voz",
];

test("the pages the taller opens are exactly Lotes, Voz, the product sheet and the model screens", () => {
  const abiertas = appRoutes().filter((route) =>
    canAccessPath("taller", route),
  );
  assert.deepEqual(abiertas, RUTAS_DEL_TALLER);
});

test("the legacy role corte opens the same pages as taller", () => {
  const abiertas = appRoutes().filter((route) => canAccessPath("corte", route));
  assert.deepEqual(abiertas, RUTAS_DEL_TALLER);
});

// Admin only pages that must stay closed to the other roles: Negocio (gastos, fábrica and tienda scenarios), a tab of Negocio y Administración.
test("Negocio is open to admin and closed to gerente, taller and the legacy roles", () => {
  assert.ok(
    appRoutes().includes("/admin/negocio"),
    "the Negocio page is missing",
  );
  assert.equal(canAccessPath("admin", "/admin/negocio"), true);
  for (const role of ["gerente", "consulta", "taller", "corte", ""]) {
    assert.equal(canAccessPath(role, "/admin/negocio"), false, role);
  }
});

// The old standalone pages are gone for good.
test("Catálogos, Formularios and Ventas y stock no longer exist as pages", () => {
  const routes = appRoutes();
  for (const gone of ["/productos/catalogos", "/formularios", "/ventas"]) {
    assert.ok(!routes.includes(gone), `${gone} should not exist`);
  }
});
