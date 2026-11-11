import type { Metadata } from "next";
import Link from "next/link";
import { inputClass } from "@/components/form";
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
import { CostosGrid } from "./costos-grid";
import { CopiarMesForm } from "./forms";
import { PeriodSelect } from "./period-select";

export const metadata: Metadata = { title: "Costos fijos" };

const PERSONAL = ["SUELDOS", "CARGAS_SOCIALES"];
type Bloque = "personal" | "servicios";

/** Un bloque del menú: solo sus gastos, con su propio título. */
const BLOQUES: Record<Bloque, { title: string; help: string }> = {
  personal: {
    title: "Mano de obra",
    help: "Sueldos y cargas sociales del personal.",
  },
  servicios: {
    title: "Servicios básicos",
    help: "Luz, agua, internet y demás servicios del mes.",
  },
};

function enBloque(gasto: Gasto, bloque: Bloque): boolean {
  return bloque === "personal"
    ? PERSONAL.includes(gasto.categoria)
    : gasto.categoria === "SERVICIOS";
}
const PERIODO = /^\d{4}-(0[1-9]|1[0-2])$/;

/** `2026-10` -> `2026-09`, `2026-01` -> `2025-12`. Only the calendar, no money. */
function previousPeriod(periodo: string): string | null {
  if (!PERIODO.test(periodo)) return null;
  const year = Number(periodo.slice(0, 4));
  const month = Number(periodo.slice(5, 7));
  return new Date(Date.UTC(year, month - 2, 1)).toISOString().slice(0, 7);
}

/** Same order as the sections of the read-only view: known categories first, then the concept. */
function byCategoryThenConcept(a: Gasto, b: Gasto): number {
  const rank = (gasto: Gasto) => {
    const index = EXPENSE_CATEGORIES.indexOf(gasto.categoria);
    return index === -1 ? EXPENSE_CATEGORIES.length : index;
  };
  return (
    rank(a) - rank(b) ||
    a.categoria.localeCompare(b.categoria, "es-AR") ||
    a.concepto.localeCompare(b.concepto, "es-AR")
  );
}

type Search = Promise<{
  periodo?: string | string[];
  vista?: string | string[];
  area?: string | string[];
  categoria?: string | string[];
  bloque?: string | string[];
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
  const selectedCategory = Array.isArray(params.categoria)
    ? params.categoria[0]
    : params.categoria;
  const categoria = EXPENSE_CATEGORIES.includes(selectedCategory ?? "")
    ? (selectedCategory ?? "")
    : "";
  const selectedBloque = Array.isArray(params.bloque)
    ? params.bloque[0]
    : params.bloque;
  const bloque: Bloque | "" =
    selectedBloque === "personal" || selectedBloque === "servicios"
      ? selectedBloque
      : "";
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
        title={bloque ? BLOQUES[bloque].title : "Costos fijos"}
        description={
          bloque
            ? `${BLOQUES[bloque].help} Cargá, cambiá o quitá cada línea.`
            : "Sueldos y servicios del mes. Cargá, cambiá o quitá cada línea."
        }
      />
      <div className="space-y-10">
        <PeriodSelector
          current={result.ok ? result.data.periodo : requested}
          periodos={periodos.ok ? periodos.data.periodos : []}
          view={view}
          area={area}
          bloque={bloque}
        />
        <div className="space-y-3">
          {writer ? null : (
            <ViewSelector
              path="/costos-fijos"
              view={view}
              params={
                new URLSearchParams({
                  ...(requested ? { periodo: requested } : {}),
                  ...(area ? { area } : {}),
                  ...(categoria ? { categoria } : {}),
                  ...(bloque ? { bloque } : {}),
                })
              }
            />
          )}
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
              if (categoria) query.set("categoria", categoria);
              if (bloque) query.set("bloque", bloque);
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
            categoria={categoria}
            bloque={bloque}
            order={order}
            direction={direction}
          />
        ) : (
          <ErrorNotice message={result.message} />
        )}
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
  bloque,
}: {
  current: string;
  periodos: string[];
  view: View;
  area: string;
  bloque: Bloque | "";
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
        {bloque ? <input type="hidden" name="bloque" value={bloque} /> : null}
        <div className="w-full sm:w-auto sm:min-w-48">
          <label
            htmlFor="periodo"
            className="mb-1.5 block text-xs uppercase tracking-caps-sm text-muted"
          >
            Período
          </label>
          <PeriodSelect
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
          </PeriodSelect>
        </div>
        <button type="submit" className="sr-only">
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
  categoria,
  bloque,
  order,
  direction,
}: {
  data: CostosFijos;
  writer: boolean;
  people: Persona[];
  view: View;
  area: string;
  categoria: string;
  bloque: Bloque | "";
  order: string;
  direction: "asc" | "desc";
}) {
  const gastos = data.gastos
    .filter((g) => !bloque || enBloque(g, bloque))
    .filter((g) => !area || g.fabrica_o_tienda === area)
    .filter((g) => !categoria || g.categoria === categoria);
  // The API only totals by area: a category filter shows no total rather than one computed here.
  const selectedTotal = categoria
    ? undefined
    : area === "FABRICA"
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

  const previous = previousPeriod(data.periodo);

  return (
    <>
      {data.gastos.length === 0 ? (
        <section aria-label="Mes sin gastos">
          <Card>
            <SectionTitle>
              {formatPeriod(data.periodo)} todavía no tiene gastos
            </SectionTitle>
            {writer && previous ? (
              <div className="space-y-4">
                <CopiarMesForm desde={previous} hasta={data.periodo} />
              </div>
            ) : (
              <p className="text-sm text-muted">
                Cuando se carguen los gastos de este mes, van a aparecer acá.
              </p>
            )}
          </Card>
        </section>
      ) : null}
      <section aria-label={`Totales de ${formatPeriod(data.periodo)}`}>
        {/* El API solo totaliza el mes entero: en una pestaña de un bloque no se repite. */}
        {bloque ? null : (
          <dl className="grid gap-5 sm:grid-cols-3">
            <Metric label="Fábrica" value={formatArs(data.total_fabrica)} />
            <Metric label="Tienda" value={formatArs(data.total_tienda)} />
            <Metric label="Total del mes" value={formatArs(data.total)} />
          </dl>
        )}
        <div className={bloque ? "space-y-3" : "mt-5 space-y-3"}>
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
      {writer ? (
        (
          [
            ["personal", ...Object.values(BLOQUES.personal)],
            ["servicios", ...Object.values(BLOQUES.servicios)],
            ["otros", "Otros gastos", "Alquiler, impuestos y el resto."],
          ] as const
        ).map(([id, title, help]) => {
          if (bloque && id !== bloque) return null;
          const del = gastos.filter((g) =>
            id === "personal"
              ? PERSONAL.includes(g.categoria)
              : id === "servicios"
                ? g.categoria === "SERVICIOS"
                : !PERSONAL.includes(g.categoria) &&
                  g.categoria !== "SERVICIOS",
          );
          // "Otros gastos" no se usa por ahora: solo aparece si el mes ya trae filas de esas
          // categorías, para que nada que cuente en los totales quede escondido.
          if (id === "otros" && del.length === 0) return null;
          return (
            <section key={id} aria-label={title}>
              {/* Con un bloque elegido, el título de la página ya lo dice. */}
              {bloque ? null : (
                <>
                  <SectionTitle>{title}</SectionTitle>
                  <p className="-mt-2 mb-4 text-sm text-muted">{help}</p>
                </>
              )}
              <CostosGrid
                key={`${data.periodo}|${area}|${id}`}
                periodo={data.periodo}
                gastos={[...del].sort(byCategoryThenConcept)}
                personas={people}
                area={area}
                bloque={id}
              />
            </section>
          );
        })
      ) : data.gastos.length === 0 ? null : gastos.length === 0 ? (
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
            <Expenses gastos={group.gastos} people={people} />
          </section>
        ))
      )}
    </>
  );
}

function Expenses({
  gastos,
  people,
  table = false,
  total,
  period,
  area,
  order,
  direction,
}: {
  gastos: Gasto[];
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
                {gasto.monto_ars_del_mes === null
                  ? "—"
                  : formatArs(gasto.monto_ars_del_mes)}
              </td>
              <td className={tdClass}>
                <span className="flex flex-wrap gap-1.5">
                  {gasto.monto_ars_del_mes === null ? (
                    <Badge tone="warn">Pendiente de monto</Badge>
                  ) : null}
                  {gasto.ficticio ? <Badge tone="warn">Ficticio</Badge> : null}
                  {gasto.reemplaza_a ? (
                    <Badge title="Este monto reemplaza al anterior, que quedó en el historial.">
                      Corrige a {gasto.reemplaza_a}
                    </Badge>
                  ) : null}
                  {gasto.monto_ars_del_mes !== null &&
                  !gasto.ficticio &&
                  !gasto.reemplaza_a ? (
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
