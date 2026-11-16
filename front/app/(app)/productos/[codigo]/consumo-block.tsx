import {
  Card,
  ErrorNotice,
  Notice,
  numClass,
  SectionTitle,
  TableWrap,
  tableClass,
  tdClass,
  thClass,
} from "@/components/ui";
import { apiGet } from "@/lib/api";
import {
  formatArs,
  formatQuantity,
  formatRate,
  formatUsd,
  stageLabel,
} from "@/lib/format";
import type { Ficha, LineaReceta, ModeloDetalle } from "@/lib/types";

/** Hilo y cemento is fixed at 1 USD per unit; shown in pesos with the reference dollar. */
const HILO_Y_CEMENTO_USD = "1";

type Row = { insumo: string; porUnidad: string; material: string };

function materialsOf(
  stage: string,
  ficha: Ficha,
  modelo: ModeloDetalle | null,
): string {
  const fromRecipe = ficha.receta
    .filter((line: LineaReceta) => line.etapa === stage)
    .map((line) => line.material);
  const fromInsumos = (modelo?.insumos ?? [])
    .filter((insumo) => insumo.etapa === stage)
    .map((insumo) => `${insumo.nombre} (${insumo.material})`);
  const all = [...fromRecipe, ...fromInsumos];
  if (stage === "CUERO" && ficha.cuero) all.unshift(ficha.cuero);
  return all.length > 0 ? Array.from(new Set(all)).join(", ") : "—";
}

function rowsOf(ficha: Ficha, modelo: ModeloDetalle | null): Row[] {
  // Without access to the model (taller role) only the recipe lines are known.
  if (modelo === null) {
    return ficha.receta.map((line) => ({
      insumo: stageLabel(line.etapa),
      porUnidad: formatQuantity(line.consumo),
      material: line.material,
    }));
  }
  const qty = (value: string | null | undefined, unit: string) =>
    value === null || value === undefined
      ? "Falta el dato"
      : `${formatQuantity(value)} ${unit}`;
  const dolar = ficha.costo_hoy?.dolar ?? null;
  const hiloArs =
    dolar === null
      ? null
      : formatArs((Number(HILO_Y_CEMENTO_USD) * Number(dolar)).toFixed(2));
  return [
    {
      insumo: "Cuero",
      porUnidad: qty(modelo.cuero_m2_por_unidad, "m²"),
      material: materialsOf("CUERO", ficha, modelo),
    },
    {
      insumo: "Forro",
      porUnidad: qty(modelo.forro_m2_por_unidad, "m²"),
      material: materialsOf("FORRO", ficha, modelo),
    },
    {
      insumo: "Flex",
      porUnidad: qty(modelo.flex_m2_por_unidad, "m²"),
      material: materialsOf("FLEX", ficha, modelo),
    },
    {
      insumo: "Goma EVA",
      porUnidad: qty(modelo.goma_eva_m2_por_unidad, "m²"),
      material: materialsOf("GOMA_EVA", ficha, modelo),
    },
    {
      insumo: "Herrajes",
      porUnidad: qty(modelo.herrajes_usd_por_unidad, "USD"),
      material: materialsOf("HERRAJES", ficha, modelo),
    },
    {
      insumo: "Hilo y cemento",
      porUnidad: `${formatUsd(HILO_Y_CEMENTO_USD)}${hiloArs ? ` · ${hiloArs}` : ""}`,
      material:
        dolar === null
          ? "Fijo en 1 USD"
          : `Fijo en 1 USD, dólar de referencia ${formatRate(dolar)}`,
    },
  ];
}

/**
 * "Consumo": what the product uses per unit, with no money from the quote. Read-only: the model
 * consumptions are edited in Modelos, not here. The role that cannot read /modelos sees the
 * recipe lines only.
 */
export async function ConsumoBlock({ ficha }: { ficha: Ficha }) {
  const result = ficha.modelo
    ? await apiGet<ModeloDetalle>(
        `/modelos/${encodeURIComponent(ficha.modelo)}`,
      )
    : null;
  const modelo = result?.ok ? result.data : null;
  return (
    <section id="consumo" className="space-y-4">
      <SectionTitle>Consumo</SectionTitle>
      {result && !result.ok && result.status !== 403 ? (
        <ErrorNotice
          title="No pudimos cargar los consumos."
          message={result.message}
        />
      ) : null}
      {ficha.modelo === null && ficha.receta.length === 0 ? (
        <Notice tone="info" title="Este producto no tiene consumos cargados." />
      ) : (
        <Card>
          <TableWrap>
            <table className={tableClass}>
              <thead>
                <tr>
                  <th className={thClass}>Insumo</th>
                  <th className={`${thClass} ${numClass}`}>Por unidad</th>
                  <th className={thClass}>Material</th>
                </tr>
              </thead>
              <tbody>
                {rowsOf(ficha, modelo).map((row) => (
                  <tr key={row.insumo}>
                    <td className={tdClass}>{row.insumo}</td>
                    <td className={`${tdClass} ${numClass}`}>
                      {row.porUnidad}
                    </td>
                    <td className={tdClass}>{row.material}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </TableWrap>
        </Card>
      )}
    </section>
  );
}
