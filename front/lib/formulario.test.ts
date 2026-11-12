import assert from "node:assert/strict";
import { test } from "node:test";
import {
  accionesDe,
  estadosVisibles,
  FORMULARIO_ESTADOS,
  filasDe,
  lineaVacia,
  parseLineas,
  seesValidatedFormulario,
  serializarFilas,
} from "./formulario";
import {
  canAccessPath,
  canReadFormularios,
  canWorkFormularios,
} from "./permissions";
import type { FormularioLinea } from "./types";

test("admin edits until VALIDADO and runs the whole flow", () => {
  assert.deepEqual(accionesDe("admin", "BORRADOR"), {
    editar: true,
    editarArticulo: true,
    enviar: true,
    completar: false,
    devolver: false,
    validar: false,
    duplicar: true,
  });
  assert.equal(accionesDe("admin", "ENVIADO").enviar, true);
  assert.equal(accionesDe("admin", "ENVIADO").completar, true);
  const completado = accionesDe("admin", "COMPLETADO");
  assert.equal(completado.editar, true);
  assert.equal(completado.devolver && completado.validar, true);
  assert.equal(completado.enviar, false);
});

test("VALIDADO is readonly for everybody and only admin may duplicate it", () => {
  for (const role of ["admin", "gerente", "taller"]) {
    const acciones = accionesDe(role, "VALIDADO");
    assert.equal(acciones.editar, false, role);
    assert.equal(acciones.editarArticulo, false, role);
    assert.equal(
      acciones.enviar ||
        acciones.completar ||
        acciones.devolver ||
        acciones.validar,
      false,
      role,
    );
  }
  assert.equal(accionesDe("admin", "VALIDADO").duplicar, true);
  assert.equal(accionesDe("taller", "VALIDADO").duplicar, false);
});

test("taller edits only the rows and only while ENVIADO; it can complete but not validate", () => {
  const enviado = accionesDe("taller", "ENVIADO");
  assert.equal(enviado.editar, true);
  assert.equal(enviado.editarArticulo, false);
  assert.equal(enviado.completar, true);
  assert.equal(enviado.validar || enviado.devolver || enviado.enviar, false);
  for (const estado of ["BORRADOR", "COMPLETADO"] as const) {
    assert.equal(accionesDe("taller", estado).editar, false, estado);
    assert.equal(accionesDe("taller", estado).completar, false, estado);
  }
});

test("gerente only reads: no action in any state", () => {
  for (const estado of FORMULARIO_ESTADOS) {
    assert.deepEqual(
      Object.values(accionesDe("gerente", estado)),
      Array(7).fill(false),
      estado,
    );
  }
});

test("legacy and missing roles map like the rest of the app", () => {
  assert.equal(accionesDe("cotizador", "BORRADOR").enviar, true);
  assert.equal(accionesDe("corte", "ENVIADO").completar, true);
  assert.equal(accionesDe(null, "ENVIADO").editar, false);
});

test("a taller user is listed only ENVIADO and COMPLETADO", () => {
  assert.deepEqual(estadosVisibles("taller"), ["ENVIADO", "COMPLETADO"]);
  assert.deepEqual(estadosVisibles("gerente"), FORMULARIO_ESTADOS);
  assert.deepEqual(estadosVisibles("taller,admin"), FORMULARIO_ESTADOS);
  assert.deepEqual(estadosVisibles(null), []);
});

test("the product sheet shows the validated form to admin and gerente, never to taller", () => {
  assert.equal(seesValidatedFormulario("admin"), true);
  assert.equal(seesValidatedFormulario("gerente"), true);
  assert.equal(seesValidatedFormulario("taller"), false);
  assert.equal(seesValidatedFormulario(null), false);
});

test("the three roles reach /formularios and only admin and taller work on it", () => {
  for (const role of ["admin", "gerente", "taller"]) {
    assert.equal(canAccessPath(role, "/formularios"), true, role);
    assert.equal(canAccessPath(role, "/formularios/FCO-0001"), true, role);
    assert.equal(canReadFormularios(role), true, role);
  }
  assert.equal(canAccessPath(null, "/formularios"), false);
  assert.equal(canAccessPath("desconocido", "/formularios"), false);
  assert.equal(canWorkFormularios("admin"), true);
  assert.equal(canWorkFormularios("taller"), true);
  assert.equal(canWorkFormularios("gerente"), false);
  assert.equal(canReadFormularios(null), false);
});

test("opening /formularios does not open the other taller / gerente paths", () => {
  assert.equal(canAccessPath("taller", "/fabricacion"), false);
  assert.equal(canAccessPath("taller", "/costos-fijos"), false);
  assert.equal(canAccessPath("gerente", "/materiales"), false);
  assert.equal(canAccessPath("gerente", "/formulariosx"), false);
});

const lineas: FormularioLinea[] = [
  {
    seccion: "HERRAJE",
    orden: 1,
    nombre: "CIERRE N5",
    cantidad: "2.000000",
    comentario: null,
  },
  {
    seccion: "CONSUMO",
    orden: 2,
    nombre: "FORRO / TELA",
    cantidad: null,
    comentario: "tela lisa",
  },
  {
    seccion: "CONSUMO",
    orden: 1,
    nombre: "CUERO",
    cantidad: "0.250000",
    comentario: null,
  },
];

test("rows come from the API as typed text, sorted by section and position", () => {
  let n = 0;
  const filas = filasDe(lineas, () => `k${n++}`);
  assert.deepEqual(
    filas.CONSUMO.map(({ nombre, cantidad, comentario }) => [
      nombre,
      cantidad,
      comentario,
    ]),
    [
      ["CUERO", "0,25", ""],
      ["FORRO / TELA", "", "tela lisa"],
    ],
  );
  assert.deepEqual(
    filas.HERRAJE.map((f) => f.cantidad),
    ["2"],
  );
  assert.equal(
    new Set([...filas.CONSUMO, ...filas.HERRAJE].map((f) => f.key)).size,
    3,
  );
});

test("the rows round-trip: what the sheet serialises is what the API gets, with 0,25 normalised", () => {
  let n = 0;
  const parsed = parseLineas(serializarFilas(filasDe(lineas, () => `k${n++}`)));
  assert.deepEqual(parsed, {
    ok: true,
    lineas: [
      {
        seccion: "CONSUMO",
        nombre: "CUERO",
        cantidad: "0.25",
        comentario: null,
      },
      {
        seccion: "CONSUMO",
        nombre: "FORRO / TELA",
        cantidad: null,
        comentario: "tela lisa",
      },
      {
        seccion: "HERRAJE",
        nombre: "CIERRE N5",
        cantidad: "2",
        comentario: null,
      },
    ],
  });
});

const fila = (extra: object) =>
  JSON.stringify([
    {
      seccion: "CONSUMO",
      nombre: "CUERO",
      cantidad: "",
      comentario: "",
      ...extra,
    },
  ]);

test("a quantity is accepted with comma or point and kept as text, zero included", () => {
  assert.deepEqual(parseLineas(fila({ cantidad: " 1,5 " })), {
    ok: true,
    lineas: [
      {
        seccion: "CONSUMO",
        nombre: "CUERO",
        cantidad: "1.5",
        comentario: null,
      },
    ],
  });
  const cero = parseLineas(fila({ cantidad: "0" }));
  assert.equal(cero.ok && cero.lineas[0].cantidad, "0");
});

test("an invalid quantity is refused naming the row", () => {
  for (const cantidad of ["abc", "-1", "1.234,5", "0,1234567", "1234567"]) {
    const parsed = parseLineas(fila({ cantidad }));
    assert.equal(parsed.ok, false, cantidad);
    assert.match(!parsed.ok ? parsed.message : "", /CUERO/, cantidad);
  }
});

test("a blank added row is dropped, a half-filled one needs its name", () => {
  const blank = parseLineas(fila({ nombre: "" }));
  assert.deepEqual(blank, { ok: true, lineas: [] });
  const sinNombre = parseLineas(fila({ nombre: " ", cantidad: "2" }));
  assert.equal(sinNombre.ok, false);
  assert.equal(parseLineas(fila({ nombre: "", comentario: "algo" })).ok, false);
});

test("garbage in the hidden field is refused, not guessed", () => {
  for (const raw of [
    "",
    "{",
    "{}",
    '[{"seccion":"OTRA","nombre":"x","cantidad":"","comentario":""}]',
    "[1]",
  ]) {
    assert.equal(parseLineas(raw).ok, false, raw);
  }
});

test("only rows with no quantity and no comment count as empty", () => {
  assert.equal(lineaVacia({ cantidad: null, comentario: null }), true);
  assert.equal(lineaVacia({ cantidad: " ", comentario: "" }), true);
  assert.equal(lineaVacia({ cantidad: "0.000000", comentario: null }), false);
  assert.equal(lineaVacia({ cantidad: null, comentario: "x" }), false);
});
