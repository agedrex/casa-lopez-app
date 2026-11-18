import assert from "node:assert/strict";
import { test } from "node:test";
import { agruparAlertas, nombreDeAlerta } from "./alertas-grupos";
import type { GrupoCalidad, Hallazgo } from "./types";

function h(
  severidad: Hallazgo["severidad"],
  entidad: string,
  mensaje: string,
  ruta = "/x",
): Hallazgo {
  return { severidad, entidad, mensaje, ruta };
}

function grupo(
  clave: string,
  titulo: string,
  hallazgos: Hallazgo[],
): GrupoCalidad {
  return { clave, titulo, total: hallazgos.length, hallazgos };
}

const GRUPOS: GrupoCalidad[] = [
  grupo("modelos_sin_validar", "Modelos sin validar", [
    h("baja", "MOD-0018", "Modelo sin validar: Alhajero", "/productos/modelos"),
    h("baja", "MOD-0019", "Modelo sin validar: Billetera"),
  ]),
  grupo("modelos", "Modelos con datos faltantes", [
    h("media", "MOD-0018", "Falta el consumo de cuero: Alhajero"),
  ]),
  grupo("lotes", "Lotes con problemas", [
    h("alta", "LOT-0001", "Sin responsable"),
    h("media", "LOT-0002", "Sin fecha"),
  ]),
  grupo("talleres", "Talleres de ejemplo en uso", []),
];

test("nombreDeAlerta: modelo sin validar toma el nombre después de los dos puntos", () => {
  assert.deepEqual(
    nombreDeAlerta("modelos_sin_validar", GRUPOS[0].hallazgos[0]),
    { nombre: "Alhajero", detalle: "Sin validar" },
  );
});

test("nombreDeAlerta: modelo con datos faltantes deja la falta como detalle", () => {
  assert.deepEqual(nombreDeAlerta("modelos", GRUPOS[1].hallazgos[0]), {
    nombre: "Alhajero",
    detalle: "Falta el consumo de cuero",
  });
});

test("nombreDeAlerta: gasto ficticio corta la sugerencia después del punto y coma", () => {
  const hallazgo = h(
    "baja",
    "GF-0001",
    "Monto ficticio: Alquiler (2026-10); reemplazalo por el real",
  );
  assert.deepEqual(nombreDeAlerta("gastos_fijos", hallazgo), {
    nombre: "Alquiler (2026-10)",
    detalle: "Monto ficticio",
  });
});

test("nombreDeAlerta: grupos sin nombre humano devuelven el mensaje entero", () => {
  assert.deepEqual(nombreDeAlerta("lotes", GRUPOS[2].hallazgos[0]), {
    nombre: null,
    detalle: "Sin responsable",
  });
});

test("nombreDeAlerta: si no hay dos puntos no inventa un nombre", () => {
  assert.deepEqual(
    nombreDeAlerta("modelos", h("media", "MOD-1", "Algo raro")),
    { nombre: null, detalle: "Algo raro" },
  );
});

test("agruparAlertas: un grupo por tipo con su contador y sin grupos vacíos", () => {
  const grupos = agruparAlertas(GRUPOS, "", "");
  assert.deepEqual(
    grupos.map((g) => [g.clave, g.titulo, g.total]),
    [
      ["modelos_sin_validar", "Modelos sin validar", 2],
      ["modelos", "Modelos con datos faltantes", 1],
      ["lotes", "Lotes con problemas", 2],
    ],
  );
});

test("agruparAlertas: cada ítem trae nombre, código, detalle, severidad y ruta", () => {
  const [primero] = agruparAlertas(GRUPOS, "", "")[0].items;
  assert.deepEqual(primero, {
    codigo: "MOD-0018",
    nombre: "Alhajero",
    detalle: "Sin validar",
    severidad: "baja",
    ruta: "/productos/modelos",
  });
});

test("agruparAlertas: el filtro de gravedad deja solo esa y ajusta el contador", () => {
  const grupos = agruparAlertas(GRUPOS, "alta", "");
  assert.deepEqual(
    grupos.map((g) => [g.clave, g.total]),
    [["lotes", 1]],
  );
  assert.equal(grupos[0].items[0].codigo, "LOT-0001");
});

test("agruparAlertas: el filtro de tema deja solo ese grupo", () => {
  const grupos = agruparAlertas(GRUPOS, "", "modelos");
  assert.deepEqual(
    grupos.map((g) => g.clave),
    ["modelos"],
  );
});

test("agruparAlertas: dentro del grupo ordena por gravedad y conserva el orden original", () => {
  const grupos = agruparAlertas(
    [
      grupo("lotes", "Lotes con problemas", [
        h("baja", "LOT-3", "c"),
        h("alta", "LOT-1", "a"),
        h("media", "LOT-2", "b"),
        h("alta", "LOT-4", "d"),
      ]),
    ],
    "",
    "",
  );
  assert.deepEqual(
    grupos[0].items.map((i) => i.codigo),
    ["LOT-1", "LOT-4", "LOT-2", "LOT-3"],
  );
});

test("agruparAlertas: gravedad máxima del grupo para ordenar y mostrar", () => {
  const grupos = agruparAlertas(GRUPOS, "", "");
  assert.deepEqual(
    grupos.map((g) => g.maxima),
    ["baja", "media", "alta"],
  );
});
