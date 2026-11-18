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
import { consumoRows } from "@/lib/ficha-consumo";
import type { Ficha, ModeloDetalle } from "@/lib/types";
import { consumoRowsDelTaller } from "./consumo-taller";

/**
 * "Consumo": what the product uses per unit, with no money from the quote. Read-only: the model
 * consumptions are edited in Modelos, not here. The role that cannot read /modelos sees the
 * recipe lines only. The taller reads quantities only: no amount in $ or USD (see consumo-taller.ts).
 */
export async function ConsumoBlock({
  ficha,
  soloCantidades = false,
}: {
  ficha: Ficha;
  /** The taller: quantities only, no money. */
  soloCantidades?: boolean;
}) {
  const rows = soloCantidades ? consumoRowsDelTaller : consumoRows;
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
                {rows(ficha, modelo).map((row) => (
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
