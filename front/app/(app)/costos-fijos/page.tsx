import type { Metadata } from "next";
import { inputClass, ReadOnlyNote } from "@/components/form";
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
import {
  EXPENSE_CATEGORIES,
  expenseCategoryLabel,
  formatArs,
  formatPeriod,
} from "@/lib/format";
import { canWrite } from "@/lib/permissions";
import { requireSession } from "@/lib/session";
import type {
  CostosFijos,
  Gasto,
  PeriodosCostosFijos,
  Persona,
} from "@/lib/types";
import { GastoForm, MontoForm } from "./forms";

export const metadata: Metadata = { title: "Costos fijos" };

const PERIODO = /^\d{4}-(0[1-9]|1[0-2])$/;

type Search = Promise<{ periodo?: string | string[] }>;

export default async function CostosFijosPage({
  searchParams,
}: {
  searchParams: Search;
}) {
  const { user } = await requireSession();
  const raw = (await searchParams).periodo;
  const requested = (Array.isArray(raw) ? raw[0] : raw)?.trim() ?? "";
  // Without a valid ?periodo= the API picks PERIODO_VIGENTE.
  const query = PERIODO.test(requested)
    ? `?periodo=${encodeURIComponent(requested)}`
    : "";
  const [periodos, result, personas] = await Promise.all([
    apiGet<PeriodosCostosFijos>("/costos-fijos/periodos"),
    apiGet<CostosFijos>(`/costos-fijos${query}`),
    apiGet<Persona[]>("/personas"),
  ]);
  const writer = canWrite(user.role);
  const people = personas.ok ? personas.data : [];

  return (
    <>
      <PageHeader
        eyebrow="Costos"
        title="Costos fijos"
        description="Gastos del mes que no dependen de cuánto se produce, separados en fábrica y tienda. Los totales los calcula la aplicación."
      />
      <div className="space-y-10">
        <PeriodSelector
          current={result.ok ? result.data.periodo : requested}
          periodos={periodos.ok ? periodos.data.periodos : []}
        />
        {result.ok ? (
          <Month data={result.data} writer={writer} people={people} />
        ) : (
          <ErrorNotice message={result.message} />
        )}
        <section>
          <SectionTitle>Cargar un gasto</SectionTitle>
          {writer ? (
            <Card>
              <GastoForm
                periodo={
                  result.ok
                    ? result.data.periodo
                    : ((periodos.ok ? periodos.data.vigente : null) ?? "")
                }
                personas={people
                  .filter((p) => p.activo)
                  .map((p) => ({ codigo: p.codigo, label: p.nombre }))}
              />
            </Card>
          ) : (
            <ReadOnlyNote />
          )}
        </section>
      </div>
    </>
  );
}

// A plain GET form: it works without JavaScript and keeps the period in the URL.
function PeriodSelector({
  current,
  periodos,
}: {
  current: string;
  periodos: string[];
}) {
  const options = periodos.includes(current)
    ? periodos
    : [current, ...periodos].filter(Boolean);
  return (
    <search>
      <form
        method="get"
        action="/costos-fijos"
        className="flex flex-wrap items-end gap-4"
      >
        <div className="min-w-48">
          <label
            htmlFor="periodo"
            className="mb-1.5 block text-xs uppercase tracking-caps-sm text-muted"
          >
            Período
          </label>
          <select
            id="periodo"
            name="periodo"
            defaultValue={current}
            className={inputClass}
          >
            {options.map((periodo) => (
              <option key={periodo} value={periodo}>
                {formatPeriod(periodo)}
              </option>
            ))}
          </select>
        </div>
        <button
          type="submit"
          className="rounded-card border border-ink px-5 py-2.5 text-sm uppercase tracking-caps-sm hover:bg-ink hover:text-white"
        >
          Ver período
        </button>
      </form>
    </search>
  );
}

function Month({
  data,
  writer,
  people,
}: {
  data: CostosFijos;
  writer: boolean;
  people: Persona[];
}) {
  const known = new Set(EXPENSE_CATEGORIES);
  const groups = [
    ...EXPENSE_CATEGORIES,
    ...new Set(
      data.gastos.map((g) => g.categoria).filter((c) => !known.has(c)),
    ),
  ]
    .map((categoria) => ({
      categoria,
      gastos: data.gastos.filter((g) => g.categoria === categoria),
    }))
    .filter((group) => group.gastos.length > 0);

  return (
    <>
      <section aria-label={`Totales de ${formatPeriod(data.periodo)}`}>
        <dl className="grid gap-5 sm:grid-cols-3">
          <Metric label="Fábrica" value={formatArs(data.total_fabrica)} />
          <Metric label="Tienda" value={formatArs(data.total_tienda)} />
          <Metric label="Total del mes" value={formatArs(data.total)} />
        </dl>
        <div className="mt-5 space-y-3">
          {data.pendientes > 0 ? (
            <Notice
              title={`${data.pendientes} ${data.pendientes === 1 ? "gasto" : "gastos"} pendiente${data.pendientes === 1 ? "" : "s"} de monto`}
            >
              No entran en los totales hasta que se cargue su monto.
            </Notice>
          ) : null}
          {data.incluye_ficticios ? (
            <Notice title="Los totales incluyen montos ficticios">
              Son valores de prueba: se reemplazan por los reales.
            </Notice>
          ) : null}
        </div>
      </section>
      {data.gastos.length === 0 ? (
        <Notice tone="info" title="Este período todavía no tiene gastos." />
      ) : (
        groups.map((group) => (
          <section key={group.categoria}>
            <SectionTitle>{expenseCategoryLabel(group.categoria)}</SectionTitle>
            <Expenses gastos={group.gastos} writer={writer} people={people} />
          </section>
        ))
      )}
    </>
  );
}

function Expenses({
  gastos,
  writer,
  people,
}: {
  gastos: Gasto[];
  writer: boolean;
  people: Persona[];
}) {
  const names = new Map(people.map((p) => [p.codigo, p.nombre]));
  return (
    <TableWrap>
      <table className={tableClass}>
        <thead>
          <tr>
            <th className={thClass}>Concepto</th>
            <th className={thClass}>Es de</th>
            <th className={thClass}>Persona</th>
            <th className={`${thClass} ${numClass}`}>Monto del mes</th>
            <th className={thClass}>Estado</th>
            <th className={thClass}>Nota o fuente</th>
          </tr>
        </thead>
        <tbody>
          {gastos.map((gasto) => (
            <tr key={gasto.codigo}>
              <td className={tdClass}>
                {gasto.concepto}
                <span className="block text-xs text-muted">{gasto.codigo}</span>
              </td>
              <td className={tdClass}>
                {gasto.fabrica_o_tienda === "FABRICA" ? "Fábrica" : "Tienda"}
              </td>
              <td className={tdClass}>
                {gasto.persona
                  ? (names.get(gasto.persona) ?? gasto.persona)
                  : "—"}
              </td>
              <td className={`${tdClass} ${numClass}`}>
                {gasto.monto_ars_del_mes === null ? (
                  writer ? (
                    <MontoForm
                      codigo={gasto.codigo}
                      concepto={gasto.concepto}
                    />
                  ) : (
                    "—"
                  )
                ) : (
                  formatArs(gasto.monto_ars_del_mes)
                )}
              </td>
              <td className={tdClass}>
                <span className="flex flex-wrap gap-1.5">
                  {gasto.monto_ars_del_mes === null ? (
                    <Badge tone="warn">Pendiente de monto</Badge>
                  ) : null}
                  {gasto.ficticio ? <Badge tone="warn">Ficticio</Badge> : null}
                  {gasto.monto_ars_del_mes !== null && !gasto.ficticio ? (
                    <span className="text-muted">—</span>
                  ) : null}
                </span>
              </td>
              <td className={`${tdClass} max-w-xs`}>
                {gasto.nota_fuente ?? "—"}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </TableWrap>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-card border border-line bg-surface p-5 shadow-card">
      <dt className="text-xs uppercase tracking-caps-sm text-muted">{label}</dt>
      <dd className="mt-2 font-display text-2xl tabular-nums">{value}</dd>
    </div>
  );
}
