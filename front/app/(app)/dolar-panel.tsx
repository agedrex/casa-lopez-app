import { ReadOnlyNote } from "@/components/form";
import {
  Badge,
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
import { formatDate, formatRate, todayIso } from "@/lib/format";
import { canWrite } from "@/lib/permissions";
import type { Dolar } from "@/lib/types";
import { DolarBnaForm, DolarForm } from "./dolar/dolar-form";

const TIPO_LABELS: Record<string, string> = {
  VENDEDOR: "Vendedor",
  COMPRADOR: "Comprador",
};

/** Dollar rate block of the main panel: load a rate and see the history. */
export async function DolarPanel({
  role,
}: {
  role: string | null | undefined;
}) {
  const result = await apiGet<Dolar[]>("/dolar");
  return (
    <section id="dolar" aria-labelledby="dolar-titulo" className="scroll-mt-6">
      <SectionTitle>
        <span id="dolar-titulo">Dólar</span>
      </SectionTitle>
      <p className="mb-5 text-sm text-muted">
        Historial de cotizaciones. El costo de hoy usa el valor más reciente
        cargado.
      </p>
      <div className="space-y-6">
        {canWrite(role) ? (
          <div className="space-y-5">
            <Card>
              <DolarBnaForm />
            </Card>
            <Card>
              <DolarForm today={todayIso()} />
            </Card>
          </div>
        ) : (
          <ReadOnlyNote />
        )}
        {result.ok ? (
          <RateTable rates={result.data} />
        ) : (
          <ErrorNotice message={result.message} />
        )}
      </div>
    </section>
  );
}

function RateTable({ rates }: { rates: Dolar[] }) {
  if (rates.length === 0) {
    return <Notice tone="info" title="Todavía no hay dólares cargados." />;
  }
  return (
    <TableWrap>
      <table className={tableClass}>
        <thead>
          <tr>
            <th className={thClass}>Fecha</th>
            <th className={`${thClass} ${numClass}`}>Pesos por dólar</th>
            <th className={thClass}>Tipo</th>
            <th className={thClass}>Fuente</th>
            <th className={thClass}>Nota</th>
          </tr>
        </thead>
        <tbody>
          {rates.map((rate, index) => (
            <tr
              key={`${rate.fecha}-${rate.tipo ?? ""}-${rate.fuente}-${index}`}
              className={index === 0 ? "bg-paper-mid/70 font-bold" : ""}
              aria-current={index === 0 ? "true" : undefined}
            >
              <td className={tdClass}>
                {formatDate(rate.fecha)}{" "}
                {index === 0 ? <Badge tone="good">Último</Badge> : null}
              </td>
              <td className={`${tdClass} ${numClass}`}>
                {formatRate(rate.ars_por_usd)}
              </td>
              <td className={tdClass}>
                {rate.tipo ? (TIPO_LABELS[rate.tipo] ?? rate.tipo) : "—"}
              </td>
              <td className={tdClass}>{rate.fuente}</td>
              <td className={tdClass}>{rate.nota ?? "—"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </TableWrap>
  );
}
