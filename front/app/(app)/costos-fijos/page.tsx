import type { Metadata } from "next";
import Link from "next/link";
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
import {
  selectedView,
  type View,
  ViewSelector,
} from "@/components/view-selector";
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

type Search = Promise<{
  periodo?: string | string[];
  vista?: string | string[];
  area?: string | string[];
  orden?: string | string[];
  dir?: string | string[];
}>;

export default async function CostosFijosPage({
  searchParams,
}: {
  searchParams: Search;
}) {
  const { user } = await requireSession();
  const params = await searchParams;
  const raw = params.periodo;
  const requested = (Array.isArray(raw) ? raw[0] : raw)?.trim() ?? "";
  const view = selectedView(params.vista);
  const selectedArea = Array.isArray(params.area)
    ? params.area[0]
    : params.area;
  const area =
    selectedArea === "FABRICA" || selectedArea === "TIENDA" ? selectedArea : "";
  const selectedOrder = Array.isArray(params.orden)
    ? params.orden[0]
    : params.orden;
  const order = ["concepto", "area", "categoria", "monto"].includes(
    selectedOrder ?? "",
  )
    ? (selectedOrder ?? "concepto")
    : "concepto";
  const direction =
    (Array.isArray(params.dir) ? params.dir[0] : params.dir) === "desc"
      ? "desc"
      : "asc";
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
          view={view}
          area={area}
        />
        <div className="space-y-3">
          <ViewSelector
            path="/costos-fijos"
            view={view}
            params={
              new URLSearchParams({
                ...(requested ? { periodo: requested } : {}),
                ...(area ? { area } : {}),
              })
            }
          />
          <nav aria-label="Filtrar gastos" className="flex flex-wrap gap-2">
            {(
              [
                ["", "Todo"],
                ["FABRICA", "Fábrica"],
                ["TIENDA", "Tienda"],
              ] as const
            ).map(([value, label]) => {
              const query = new URLSearchParams({
                ...(requested ? { periodo: requested } : {}),
                ...(view === "tabla" ? { vista: "tabla" } : {}),
              });
              if (value) query.set("area", value);
              return (
                <Link
                  key={label}
                  href={`/costos-fijos?${query}`}
                  aria-current={area === value ? "page" : undefined}
                  className={`inline-flex min-h-11 items-center rounded-card border px-4 py-2 text-sm sm:min-h-0 ${area === value ? "border-ink bg-ink text-white" : "border-line bg-surface hover:border-gold"}`}
                >
                  {label}
                </Link>
              );
            })}
          </nav>
        </div>
        {result.ok ? (
          <Month
            data={result.data}
            writer={writer}
            people={people}
            view={view}
            area={area}
            order={order}
            direction={direction}
          />
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
  view,
  area,
}: {
  current: string;
  periodos: string[];
  view: View;
  area: string;
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
        {view === "tabla" ? (
          <input type="hidden" name="vista" value="tabla" />
        ) : null}
        {area ? <input type="hidden" name="area" value={area} /> : null}
        <div className="w-full sm:w-auto sm:min-w-48">
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
          className="inline-flex min-h-11 items-center justify-center sm:min-h-0 rounded-card border border-ink px-5 py-2.5 text-sm uppercase tracking-caps-sm hover:bg-ink hover:text-white"
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
  view,
  area,
  order,
  direction,
}: {
  data: CostosFijos;
  writer: boolean;
  people: Persona[];
  view: View;
  area: string;
  order: string;
  direction: "asc" | "desc";
}) {
  const gastos = area
    ? data.gastos.filter((g) => g.fabrica_o_tienda === area)
    : data.gastos;
  const selectedTotal =
    area === "FABRICA"
      ? data.total_fabrica
      : area === "TIENDA"
        ? data.total_tienda
        : data.total;
  const pendientes = gastos.filter((g) => g.monto_ars_del_mes === null).length;
  const incluyeFicticios = gastos.some(
    (g) => g.ficticio && g.monto_ars_del_mes !== null,
  );
  const known = new Set(EXPENSE_CATEGORIES);
  const groups = [
    ...EXPENSE_CATEGORIES,
    ...new Set(gastos.map((g) => g.categoria).filter((c) => !known.has(c))),
  ]
    .map((categoria) => ({
      categoria,
      gastos: gastos.filter((g) => g.categoria === categoria),
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
          {pendientes > 0 ? (
            <Notice
              title={`${pendientes} ${pendientes === 1 ? "gasto" : "gastos"} pendiente${pendientes === 1 ? "" : "s"} de monto`}
            >
              No entran en los totales hasta que se cargue su monto.
            </Notice>
          ) : null}
          {incluyeFicticios ? (
            <Notice title="Los totales incluyen montos ficticios">
              Son valores de prueba: se reemplazan por los reales.
            </Notice>
          ) : null}
        </div>
      </section>
      {gastos.length === 0 ? (
        <Notice
          tone="info"
          title="No hay gastos para este filtro en el período."
        />
      ) : view === "tabla" ? (
        <section>
          <SectionTitle>Todos los gastos</SectionTitle>
          <Expenses
            gastos={[...gastos].sort((a, b) => {
              const left =
                order === "monto"
                  ? Number(a.monto_ars_del_mes ?? "-1")
                  : order === "area"
                    ? a.fabrica_o_tienda
                    : order === "categoria"
                      ? a.categoria
                      : a.concepto;
              const right =
                order === "monto"
                  ? Number(b.monto_ars_del_mes ?? "-1")
                  : order === "area"
                    ? b.fabrica_o_tienda
                    : order === "categoria"
                      ? b.categoria
                      : b.concepto;
              const result =
                typeof left === "number" && typeof right === "number"
                  ? left - right
                  : String(left).localeCompare(String(right), "es-AR");
              return direction === "desc" ? -result : result;
            })}
            writer={writer}
            people={people}
            table
            total={selectedTotal}
            period={data.periodo}
            area={area}
            order={order}
            direction={direction}
          />
        </section>
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
  table = false,
  total,
  period,
  area,
  order,
  direction,
}: {
  gastos: Gasto[];
  writer: boolean;
  people: Persona[];
  table?: boolean;
  total?: string;
  period?: string;
  area?: string;
  order?: string;
  direction?: "asc" | "desc";
}) {
  const names = new Map(people.map((p) => [p.codigo, p.nombre]));
  const sortLink = (key: string) => {
    const query = new URLSearchParams({
      periodo: period ?? "",
      vista: "tabla",
      orden: key,
      dir: order === key && direction === "asc" ? "desc" : "asc",
    });
    if (area) query.set("area", area);
    return `/costos-fijos?${query}`;
  };
  const heading = (key: string, label: string) =>
    table ? (
      <Link
        href={sortLink(key)}
        className="underline decoration-gold underline-offset-4"
      >
        {label}
        {order === key ? (direction === "asc" ? " ↑" : " ↓") : ""}
      </Link>
    ) : (
      label
    );
  return (
    <TableWrap>
      <table className={tableClass}>
        <thead>
          <tr>
            <th className={thClass}>{heading("concepto", "Concepto")}</th>
            {table ? (
              <th className={thClass}>{heading("categoria", "Categoría")}</th>
            ) : null}
            <th className={thClass}>{heading("area", "Es de")}</th>
            <th className={thClass}>Persona</th>
            <th className={`${thClass} ${numClass}`}>
              {heading("monto", "Monto del mes")}
            </th>
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
              {table ? (
                <td className={tdClass}>
                  {expenseCategoryLabel(gasto.categoria)}
                </td>
              ) : null}
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
        {table ? (
          <tfoot>
            <tr className="bg-paper-mid font-bold">
              <th className={tdClass} scope="row">
                Total del filtro
              </th>
              <td className={tdClass} colSpan={3} />
              <td className={`${tdClass} ${numClass}`}>{formatArs(total)}</td>
              <td className={tdClass} colSpan={2} />
            </tr>
          </tfoot>
        ) : null}
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
