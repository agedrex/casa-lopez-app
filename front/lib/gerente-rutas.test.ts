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
  for (const path of [
    "/productos/nuevo",
    "/productos/catalogos",
    "/productos/modelos/nuevo",
  ]) {
    assert.equal(canAccessPath("gerente", path), false, path);
  }
});
