import assert from "node:assert/strict";
import { test } from "node:test";
import { estadoDeCuero, resumenDeCuero } from "./lote-cuero";
import type { LoteCuero, LoteCueroGrupo } from "./types";

function grupo(cambios: Partial<LoteCueroGrupo>): LoteCueroGrupo {
  return {
    material: "MAT-CU01",
    material_nombre: "Estándar",
    color: null,
    necesario: "2",
    ya_cortado: "0",
    por_cortar: "2",
    disponible: "3.5",
    reservado_por_otros: "0",
    reservado_por: [],
    libre: "3.5",
    alcanza: true,
    faltante: "0",
    sobrante: "1.5",
    mensaje: null,
    productos: ["PRD-0001"],
    ...cambios,
  };
}

function lote(cueros: LoteCueroGrupo[]): LoteCuero {
  return { lote: "LOT-0001", estado: "PLANIFICADA", cueros, sin_consumo: [] };
}

test("estadoDeCuero distingue falta, alcanza y ya cortado", () => {
  assert.equal(estadoDeCuero(grupo({})), "ALCANZA");
  assert.equal(
    estadoDeCuero(
      grupo({ alcanza: false, faltante: "0.5", disponible: "1.5" }),
    ),
    "FALTA",
  );
  // Nothing left to cut: it is not "short" even with an empty stock.
  assert.equal(
    estadoDeCuero(
      grupo({
        por_cortar: "0.000000",
        ya_cortado: "2",
        disponible: "0",
        sobrante: "0",
      }),
    ),
    "YA_CORTADO",
  );
});

test("resumenDeCuero muestra primero lo que falta, con los m² del API", () => {
  const resumen = resumenDeCuero(
    lote([
      grupo({
        material: "MAT-CU02",
        material_nombre: "Carpincho",
        color: "Azul",
      }),
      grupo({
        alcanza: false,
        faltante: "0.5",
        sobrante: "0",
        disponible: "1.5",
        productos: ["PRD-0001", "PRD-0002"],
      }),
    ]),
  );
  assert.equal(resumen.faltan, 1);
  assert.equal(resumen.titular, "Falta cuero de 1 tipo.");
  const [primera, segunda] = resumen.tarjetas;
  assert.equal(primera?.titulo, "Estándar · Sin color");
  assert.equal(primera?.estado, "FALTA");
  assert.equal(primera?.mensaje, "Falta 0,5 m²");
  assert.deepEqual(primera?.cifras, [
    { label: "Necesita", value: "2 m²" },
    { label: "Hay", value: "1,5 m²" },
  ]);
  assert.deepEqual(primera?.productos, ["PRD-0001", "PRD-0002"]);
  assert.equal(segunda?.titulo, "Carpincho · Azul");
  assert.equal(segunda?.mensaje, "Alcanza · sobran 1,5 m²");
});

test("resumenDeCuero avisa 'Alcanza justo', muestra lo ya cortado y el titular de todo cubierto", () => {
  const resumen = resumenDeCuero(
    lote([
      grupo({ sobrante: "0", disponible: "2" }),
      grupo({
        material: "MAT-CU02",
        material_nombre: "Carpincho",
        necesario: "1",
        ya_cortado: "1",
        por_cortar: "0",
        disponible: "0",
        sobrante: "0",
      }),
    ]),
  );
  assert.equal(resumen.faltan, 0);
  assert.equal(resumen.titular, "Hay cuero para todo el lote.");
  assert.equal(resumen.tarjetas[0]?.mensaje, "Alcanza justo");
  assert.equal(resumen.tarjetas[1]?.mensaje, "Ya está cortado");
  assert.deepEqual(resumen.tarjetas[1]?.cifras[1], {
    label: "Ya cortado",
    value: "1 m²",
  });
});

test("resumenDeCuero sin cueros ni consumos lo dice y no inventa tarjetas", () => {
  const resumen = resumenDeCuero({
    ...lote([]),
    sin_consumo: [{ producto: "PRD-0009", producto_nombre: "Kit regalo" }],
  });
  assert.deepEqual(resumen.tarjetas, []);
  assert.equal(
    resumen.titular,
    "Todavía no hay consumo de cuero para este lote.",
  );
  assert.equal(resumen.sinConsumo.length, 1);
});

test("resumenDeCuero muestra lo reservado por otros lotes y el mensaje del API sin calcular nada", () => {
  const resumen = resumenDeCuero(
    lote([
      grupo({
        disponible: "3",
        reservado_por_otros: "2",
        reservado_por: ["LOT-0001"],
        libre: "1",
        alcanza: false,
        faltante: "1",
        sobrante: "0",
        mensaje:
          "No alcanza: faltan 1 m² de Estándar. Hay 3 m² en stock y LOT-0001 tiene reservados 2 m².",
      }),
    ]),
  );
  const tarjeta = resumen.tarjetas[0];
  assert.equal(tarjeta.estado, "FALTA");
  assert.equal(tarjeta.mensaje, "Falta 1 m²");
  assert.equal(
    tarjeta.aviso,
    "No alcanza: faltan 1 m² de Estándar. Hay 3 m² en stock y LOT-0001 tiene reservados 2 m².",
  );
  assert.deepEqual(
    tarjeta.cifras.map((c) => [c.label, c.value]),
    [
      ["Necesita", "2 m²"],
      ["Hay", "3 m²"],
      ["Reservado por LOT-0001", "2 m²"],
      ["Libre para este lote", "1 m²"],
    ],
  );
  assert.equal(resumen.faltan, 1);
});

test("resumenDeCuero no muestra reserva ni aviso cuando ningún otro lote reserva", () => {
  const tarjeta = resumenDeCuero(lote([grupo({})])).tarjetas[0];
  assert.equal(tarjeta.aviso, null);
  assert.deepEqual(
    tarjeta.cifras.map((c) => c.label),
    ["Necesita", "Hay"],
  );
});
