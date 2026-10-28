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
  formatPercent,
  formatPeriod,
  formatQuantity,
} from "@/lib/format";
import type { CasaVsTaller } from "@/lib/types";

/**
 * House vs workshop, last 12 months. Everything shown (percentages, totals) comes from the API;
 * the bar width is the API's percentage used as a CSS length, nothing is calculated here.
 */
export async function CasaVsTallerSection() {
  const result = await apiGet<CasaVsTaller>("/fabricacion/casa-vs-taller");
  return (
    <section>
      <SectionTitle>En casa o en taller</SectionTitle>
      {result.ok ? (
        <Summary data={result.data} />
      ) : (
        <ErrorNotice message={result.message} />
      )}
    </section>
  );
}

function Summary({ data }: { data: CasaVsTaller }) {
  const withUnits = data.meses.filter((mes) => mes.porcentaje_taller !== null);
  if (withUnits.length === 0) {
    return (
      <Notice
        tone="info"
        title="Todavía no hay lotes con fecha en los últimos 12 meses."
      >
        Cada lote cuenta en el mes de su fecha de entrega o, si todavía no
        volvió, de su fecha de envío.
      </Notice>
    );
  }
  return (
    <Card className="space-y-4 p-0">
      <p className="px-6 pt-6 text-sm text-muted">
        Cada lote cuenta en el mes de su fecha de entrega o, si todavía no
        volvió, de su fecha de envío. La barra oscura es la parte hecha en
        talleres.
      </p>
      <TableWrap>
        <table className={tableClass}>
          <caption className="sr-only">
            Lotes y unidades hechos en casa y en taller, por mes
          </caption>
          <thead>
            <tr>
              <th className={thClass} scope="col">
                Mes
              </th>
              <th className={`${thClass} ${numClass}`} scope="col">
                Lotes en casa
              </th>
              <th className={`${thClass} ${numClass}`} scope="col">
                Lotes en taller
              </th>
              <th className={`${thClass} ${numClass}`} scope="col">
                Unidades en casa
              </th>
              <th className={`${thClass} ${numClass}`} scope="col">
                Unidades en taller
              </th>
              <th className={thClass} scope="col">
                Parte en taller
              </th>
              <th className={`${thClass} ${numClass}`} scope="col">
                Pagado a talleres
              </th>
              {data.talleres.map((taller) => (
                <th
                  key={taller.codigo}
                  className={`${thClass} ${numClass}`}
                  scope="col"
                >
                  Unidades: {taller.nombre}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {data.meses.map((mes) => (
              <tr key={mes.periodo}>
                <th scope="row" className={`${tdClass} font-normal`}>
                  {formatPeriod(mes.periodo)}
                </th>
                <td className={`${tdClass} ${numClass}`}>{mes.lotes_casa}</td>
                <td className={`${tdClass} ${numClass}`}>{mes.lotes_taller}</td>
                <td className={`${tdClass} ${numClass}`}>
                  {formatQuantity(mes.unidades_casa)}
                </td>
                <td className={`${tdClass} ${numClass}`}>
                  {formatQuantity(mes.unidades_taller)}
                </td>
                <td className={tdClass}>
                  {mes.porcentaje_taller === null ? (
                    <span className="text-muted">Sin unidades</span>
                  ) : (
                    <span className="flex items-center gap-3">
                      <span
                        aria-hidden="true"
                        className="block h-2.5 w-32 overflow-hidden rounded-full bg-sage/30"
                      >
                        <span
                          className="block h-full bg-ink"
                          style={{ width: `${mes.porcentaje_taller}%` }}
                        />
                      </span>
                      <span className="tabular-nums">
                        {formatPercent(mes.porcentaje_taller)}
                      </span>
                    </span>
                  )}
                </td>
                <td className={`${tdClass} ${numClass}`}>
                  {formatArs(mes.pagado_a_talleres)}
                </td>
                {data.talleres.map((taller) => (
                  <td key={taller.codigo} className={`${tdClass} ${numClass}`}>
                    {formatQuantity(mes.unidades_por_taller[taller.codigo])}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </TableWrap>
    </Card>
  );
}
