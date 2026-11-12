import { Card, ErrorNotice } from "@/components/ui";
import { apiGet } from "@/lib/api";
import { formatDate, formatRate, todayIso } from "@/lib/format";
import type { Dolar } from "@/lib/types";
import { DolarAlDia } from "../../dolar/dolar-al-dia";

const TIPO_LABELS: Record<string, string> = {
  VENDEDOR: "vendedor",
  COMPRADOR: "comprador",
};

function origen(rate: Dolar): string {
  const fuente = rate.fuente === "BNA" ? "Banco Nación" : rate.fuente;
  const tipo = rate.tipo ? TIPO_LABELS[rate.tipo] : null;
  return tipo ? `${fuente} · ${tipo}` : fuente;
}

/** One card with the newest stored rate; the page tops it up on its own when it is out of date. */
export async function DolarPanel({ canWrite }: { canWrite: boolean }) {
  const result = await apiGet<Dolar[]>("/dolar");
  const today = todayIso();
  const latest = result.ok ? result.data[0] : undefined;

  return (
    <section id="dolar" aria-labelledby="dolar-titulo" className="scroll-mt-6">
      {result.ok ? (
        <Card>
          <h2
            id="dolar-titulo"
            className="text-xs font-semibold uppercase tracking-caps-sm text-muted"
          >
            Dólar del día
          </h2>
          {latest ? (
            <>
              <p className="mt-3 text-3xl font-bold tabular-nums text-ink">
                $ {formatRate(latest.ars_por_usd)}
              </p>
              <p className="mt-2 text-xs text-muted">
                {origen(latest)} · {formatDate(latest.fecha)}
              </p>
            </>
          ) : (
            <p className="mt-3 text-sm text-muted">
              Todavía no hay cotización cargada.
            </p>
          )}
          {canWrite ? (
            <DolarAlDia today={today} stale={!latest || latest.fecha < today} />
          ) : null}
        </Card>
      ) : (
        <ErrorNotice message={result.message} />
      )}
    </section>
  );
}
