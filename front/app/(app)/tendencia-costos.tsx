import { Badge, Card } from "@/components/ui";
import { formatArs, formatPeriod } from "@/lib/format";
import type { TendenciaCostos } from "@/lib/types";

/** Bar heights only: the amounts shown come already computed by the API. */
const share = (value: string | null, max: number) =>
  value === null || max <= 0 ? 0 : (Number(value) / max) * 100;

export function TendenciaDeCostos({
  tendencia,
}: {
  tendencia: TendenciaCostos;
}) {
  const meses = tendencia.meses;
  const max = Math.max(
    0,
    ...meses.map((mes) => Number(mes.total_por_unidad ?? 0)),
  );

  return (
    <Card>
      <div className="mb-4 flex flex-wrap items-baseline justify-between gap-2">
        <h2 className="text-lg">Costo por unidad, mes a mes</h2>
        <div className="flex gap-4 text-xs text-muted">
          <span className="flex items-center gap-1.5">
            <span className="size-2.5 rounded-sm bg-gold" /> Variable
          </span>
          <span className="flex items-center gap-1.5">
            <span className="size-2.5 rounded-sm bg-ink-soft" /> Fijo
          </span>
        </div>
      </div>

      <ul className="grid auto-cols-fr grid-flow-col gap-2 sm:gap-4">
        {meses.map((mes) => {
          const completo = mes.incompleto.length === 0;
          return (
            <li
              key={mes.periodo}
              className="flex min-w-0 flex-col items-center gap-2"
            >
              <span className="text-xs font-semibold tabular-nums">
                {formatArs(mes.total_por_unidad)}
              </span>
              <div
                className={`flex h-40 w-full max-w-14 flex-col justify-end overflow-hidden rounded-t-card bg-parchment ${completo ? "" : "opacity-60"}`}
                title={
                  completo
                    ? undefined
                    : `Mes incompleto: ${mes.incompleto.join(", ")}`
                }
              >
                <div
                  className="bg-ink-soft"
                  style={{ height: `${share(mes.fijo_por_unidad, max)}%` }}
                />
                <div
                  className="bg-gold"
                  style={{
                    height: `${share(mes.costo_variable_por_unidad, max)}%`,
                  }}
                />
              </div>
              <span className="truncate text-xs text-muted">
                {formatPeriod(mes.periodo)}
              </span>
              {completo ? null : <Badge tone="warn">Incompleto</Badge>}
            </li>
          );
        })}
      </ul>
      {tendencia.nota ? (
        <p className="mt-4 text-xs text-muted">{tendencia.nota}</p>
      ) : null}
    </Card>
  );
}
