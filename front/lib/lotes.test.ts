import assert from "node:assert/strict";
import { test } from "node:test";
import { ordenarLotes, sumarDecimales, ultimoLote } from "./lotes";
import type {
  HistorialDeTaller,
  LoteDeTaller,
  ProductoDeTaller,
} from "./types";

function lote(codigo: string, fecha: string | null): LoteDeTaller {
  return {
    lote: codigo,
    fecha,
    estado: "CERRADA",
    productos: 1,
    unidades: "10",
    unidades_con_precio_pagado: "10",
    total_cotizado: "0",
    total_pagado: "1000",
    precio_pagado_promedio: "100",
    barra_pct: null,
  };
}

function producto(
  codigo: string,
  pagos: { lote: string; cantidad: string; pagado: string | null }[],
): ProductoDeTaller {
  return {
    producto: codigo,
    producto_nombre: codigo,
    categoria: null,
    lotes: pagos.length,
    unidades: "0",
    primer_pagado: null,
    ultimo_pagado: null,
    variacion_ultima_pct: null,
    variacion_total_pct: null,
    ultima_fecha: null,
    historial: pagos.map((pago, i) => ({
      item: `LIT-${i}`,
      fecha: null,
      lote: pago.lote,
      cantidad: pago.cantidad,
      cotizado: null,
      pagado: pago.pagado,
      variacion_pct: null,
      salto_grande: false,
      barra_pct: null,
    })),
  };
}

test("ordenarLotes: newest date first, ties by code, undated last", () => {
  const orden = ordenarLotes([
    lote("LOT-0001", "2026-10-01"),
    lote("LOT-0002", null),
    lote("LOT-0004", "2026-10-05"),
    lote("LOT-0003", "2026-10-05"),
  ]).map((l) => l.lote);
  assert.deepEqual(orden, ["LOT-0004", "LOT-0003", "LOT-0001", "LOT-0002"]);
});

test("ordenarLotes does not mutate its input", () => {
  const lotes = [
    lote("LOT-0001", "2026-10-01"),
    lote("LOT-0002", "2026-10-02"),
  ];
  ordenarLotes(lotes);
  assert.equal(lotes[0]?.lote, "LOT-0001");
});

test("ultimoLote is null for a workshop without lots", () => {
  const vacio: HistorialDeTaller = {
    taller: "TAL-0001",
    taller_nombre: "Taller",
    lotes: [],
    productos: [],
  };
  assert.equal(ultimoLote(vacio), null);
});

test("ultimoLote keeps only the products of the newest lot", () => {
  const historial: HistorialDeTaller = {
    taller: "TAL-0001",
    taller_nombre: "Taller",
    lotes: [lote("LOT-0001", "2026-09-01"), lote("LOT-0002", "2026-10-01")],
    productos: [
      producto("PRD-0001", [
        { lote: "LOT-0001", cantidad: "5", pagado: "900" },
        { lote: "LOT-0002", cantidad: "8", pagado: "1000" },
      ]),
      producto("PRD-0002", [{ lote: "LOT-0001", cantidad: "3", pagado: "50" }]),
    ],
  };
  const ultimo = ultimoLote(historial);
  assert.equal(ultimo?.lote.lote, "LOT-0002");
  assert.deepEqual(ultimo?.productos, {
    "PRD-0001": { cantidad: "8", pagado: "1000" },
  });
});

test("ultimoLote adds repeated lines and keeps the first paid price", () => {
  const historial: HistorialDeTaller = {
    taller: "TAL-0001",
    taller_nombre: "Taller",
    lotes: [lote("LOT-0002", "2026-10-01")],
    productos: [
      producto("PRD-0001", [
        { lote: "LOT-0002", cantidad: "2.5", pagado: null },
        { lote: "LOT-0002", cantidad: "1.25", pagado: "700" },
      ]),
    ],
  };
  assert.deepEqual(ultimoLote(historial)?.productos["PRD-0001"], {
    cantidad: "3.75",
    pagado: "700",
  });
});

test("sumarDecimales is exact", () => {
  assert.equal(sumarDecimales("0.1", "0.2"), "0.3");
  assert.equal(sumarDecimales("10", "5"), "15");
  assert.equal(sumarDecimales("0.5", "0.5"), "1.0");
  assert.equal(sumarDecimales("999.9", "0.1"), "1000.0");
});
