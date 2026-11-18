import assert from "node:assert/strict";
import { test } from "node:test";
import {
  ariaSort,
  ordenar,
  PAGE_SIZE,
  paginar,
  siguienteOrden,
} from "./paginacion";

type Fila = { id: string; valor: string | number | null };

function filas(...valores: Array<string | number | null>): Fila[] {
  return valores.map((valor, index) => ({ id: `f${index}`, valor }));
}

const porValor = (fila: Fila) => fila.valor;

test("ordenar: ascendente y descendente con números", () => {
  const items = filas(10, 2, 33);
  assert.deepEqual(
    ordenar(items, porValor, "asc").map((f) => f.valor),
    [2, 10, 33],
  );
  assert.deepEqual(
    ordenar(items, porValor, "desc").map((f) => f.valor),
    [33, 10, 2],
  );
});

test("ordenar: textos sin distinguir mayúsculas ni acentos, y números dentro del texto", () => {
  const items = filas("modelo 10", "Árbol", "modelo 2", "arco");
  assert.deepEqual(
    ordenar(items, porValor, "asc").map((f) => f.valor),
    ["Árbol", "arco", "modelo 2", "modelo 10"],
  );
});

test("ordenar: los vacíos van siempre al final, en cualquier sentido", () => {
  const items = filas(null, 5, null, 1);
  assert.deepEqual(
    ordenar(items, porValor, "asc").map((f) => f.valor),
    [1, 5, null, null],
  );
  assert.deepEqual(
    ordenar(items, porValor, "desc").map((f) => f.valor),
    [5, 1, null, null],
  );
});

test("ordenar: es estable (los iguales conservan su orden) y no toca la lista original", () => {
  const items = filas(1, 1, 0);
  const original = [...items];
  const asc = ordenar(items, porValor, "asc");
  assert.deepEqual(
    asc.map((f) => f.id),
    ["f2", "f0", "f1"],
  );
  const desc = ordenar(items, porValor, "desc");
  assert.deepEqual(
    desc.map((f) => f.id),
    ["f0", "f1", "f2"],
  );
  assert.deepEqual(items, original);
});

test("paginar: 25 por página por defecto", () => {
  assert.equal(PAGE_SIZE, 25);
  const items = Array.from({ length: 60 }, (_, i) => i);
  const primera = paginar(items, 1);
  assert.equal(primera.items.length, 25);
  assert.deepEqual(
    { pagina: primera.pagina, paginas: primera.paginas, total: primera.total },
    { pagina: 1, paginas: 3, total: 60 },
  );
  assert.deepEqual([primera.desde, primera.hasta], [1, 25]);
  const ultima = paginar(items, 3);
  assert.deepEqual(ultima.items, items.slice(50));
  assert.deepEqual([ultima.desde, ultima.hasta], [51, 60]);
});

test("paginar: una página fuera de rango se corrige a la más cercana", () => {
  const items = Array.from({ length: 30 }, (_, i) => i);
  assert.equal(paginar(items, 0).pagina, 1);
  assert.equal(paginar(items, -4).pagina, 1);
  assert.equal(paginar(items, 99).pagina, 2);
  assert.equal(paginar(items, Number.NaN).pagina, 1);
});

test("paginar: lista vacía tiene una sola página y 0 de 0", () => {
  const vacia = paginar([], 1);
  assert.deepEqual(vacia.items, []);
  assert.deepEqual(
    [vacia.pagina, vacia.paginas, vacia.total, vacia.desde, vacia.hasta],
    [1, 1, 0, 0, 0],
  );
});

test("siguienteOrden: primer clic ascendente, el mismo encabezado alterna, otro vuelve a ascendente", () => {
  assert.deepEqual(siguienteOrden(null, "nombre"), {
    clave: "nombre",
    dir: "asc",
  });
  assert.deepEqual(siguienteOrden({ clave: "nombre", dir: "asc" }, "nombre"), {
    clave: "nombre",
    dir: "desc",
  });
  assert.deepEqual(siguienteOrden({ clave: "nombre", dir: "desc" }, "nombre"), {
    clave: "nombre",
    dir: "asc",
  });
  assert.deepEqual(siguienteOrden({ clave: "nombre", dir: "desc" }, "cuero"), {
    clave: "cuero",
    dir: "asc",
  });
});

test("ariaSort: solo la columna ordenada declara el sentido", () => {
  const orden = { clave: "cuero", dir: "desc" } as const;
  assert.equal(ariaSort(orden, "cuero"), "descending");
  assert.equal(ariaSort({ clave: "cuero", dir: "asc" }, "cuero"), "ascending");
  assert.equal(ariaSort(orden, "nombre"), "none");
  assert.equal(ariaSort(null, "nombre"), "none");
});
