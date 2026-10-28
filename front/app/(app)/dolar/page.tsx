import type { Metadata } from "next";
import { ReadOnlyNote } from "@/components/form";
import {
  Badge,
  Card,
  ErrorNotice,
  Notice,
  numClass,
  PageHeader,
  SectionTitle,
  TableWrap,
  tableClass,
  tdClass,
  thClass,
} from "@/components/ui";
import { apiGet } from "@/lib/api";
import { formatDate, formatRate, todayIso } from "@/lib/format";
import { canWrite } from "@/lib/permissions";
import { requireSession } from "@/lib/session";
import type { Dolar } from "@/lib/types";
import { DolarBnaForm, DolarForm } from "./dolar-form";

export const metadata: Metadata = { title: "Dólar" };

const TIPO_LABELS: Record<string, string> = {
  VENDEDOR: "Vendedor",
  COMPRADOR: "Comprador",
};

export default async function DolarPage() {
  const { user } = await requireSession();
  const result = await apiGet<Dolar[]>("/dolar");

  return (
    <>
      <PageHeader
        eyebrow="Costos"
        title="Dólar"
        description="Historial de cotizaciones. El costo de hoy usa el valor más reciente cargado."
      />
      <div className="space-y-10">
        <section>
          <SectionTitle>Cargar dólar</SectionTitle>
          {canWrite(user.role) ? (
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
        </section>
        <section>
          <SectionTitle>Historial</SectionTitle>
          {result.ok ? (
            <RateTable rates={result.data} />
          ) : (
            <ErrorNotice message={result.message} />
          )}
        </section>
      </div>
    </>
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
