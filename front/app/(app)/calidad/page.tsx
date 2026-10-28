import type { Metadata } from "next";
import Link from "next/link";
import { inputClass } from "@/components/form";
import {
  Badge,
  ErrorNotice,
  Notice,
  PageHeader,
  SectionTitle,
  TableWrap,
  tableClass,
  tdClass,
  thClass,
} from "@/components/ui";
import { apiGet } from "@/lib/api";
import { safeNext } from "@/lib/redirect";
import { requireSession } from "@/lib/session";
import type { Calidad, GrupoCalidad, Hallazgo, Severidad } from "@/lib/types";

export const metadata: Metadata = { title: "Calidad de datos" };

const SEVERIDADES: Severidad[] = ["alta", "media", "baja"];
const SEVERITY_LABELS: Record<Severidad, string> = {
  alta: "Alta",
  media: "Media",
  baja: "Baja",
};
const SEVERITY_TONES = {
  alta: "alert",
  media: "warn",
  baja: "neutral",
} as const;
// A group lists this many findings unless it is filtered to one group (then all of them).
const GROUP_PREVIEW = 50;

type Search = Promise<{
  severidad?: string | string[];
  grupo?: string | string[];
  q?: string | string[];
}>;

function first(value: string | string[] | undefined): string {
  return (Array.isArray(value) ? value[0] : value)?.trim() ?? "";
}

export default async function CalidadPage({
  searchParams,
}: {
  searchParams: Search;
}) {
  await requireSession();
  const params = await searchParams;
  const severidad =
    SEVERIDADES.find((s) => s === first(params.severidad)) ?? "";
  const grupo = first(params.grupo);
  const q = first(params.q);
  const result = await apiGet<Calidad>("/calidad");

  return (
    <>
      <PageHeader
        eyebrow="Control"
        title="Calidad de datos"
        description="Datos que faltan, se contradicen o son de prueba, con el lugar donde corregirlos. La gravedad es una propuesta: alta = no se puede cotizar o cerrar; media = se puede, pero hay algo raro; baja = informativo."
      />
      {result.ok ? (
        <Report data={result.data} severidad={severidad} grupo={grupo} q={q} />
      ) : (
        <ErrorNotice message={result.message} />
      )}
    </>
  );
}

function href(filter: { severidad?: string; grupo?: string; q?: string }) {
  const query = new URLSearchParams();
  for (const [key, value] of Object.entries(filter)) {
    if (value) query.set(key, value);
  }
  const text = query.toString();
  return text ? `/calidad?${text}` : "/calidad";
}

function Report({
  data,
  severidad,
  grupo,
  q,
}: {
  data: Calidad;
  severidad: string;
  grupo: string;
  q: string;
}) {
  const needle = q.toLowerCase();
  const matches = (h: Hallazgo) =>
    (!severidad || h.severidad === severidad) &&
    (!needle ||
      h.entidad.toLowerCase().includes(needle) ||
      h.mensaje.toLowerCase().includes(needle));
  const groups = data.grupos
    .filter((g) => !grupo || g.clave === grupo)
    .map((g) => ({ ...g, visibles: g.hallazgos.filter(matches) }))
    .filter((g) => g.visibles.length > 0);
  const filtered = Boolean(severidad || grupo || q);

  return (
    <div className="space-y-10">
      <section aria-label="Resumen por gravedad">
        <dl className="grid gap-5 sm:grid-cols-4">
          <Count label="Total" value={data.resumen.total} to={href({})} />
          {SEVERIDADES.map((s) => (
            <Count
              key={s}
              label={`Gravedad ${SEVERITY_LABELS[s].toLowerCase()}`}
              value={data.resumen[s]}
              to={href({ severidad: s, grupo, q })}
              active={severidad === s}
            />
          ))}
        </dl>
      </section>

      <search>
        <form
          method="get"
          action="/calidad"
          className="flex flex-wrap items-end gap-4"
        >
          <div className="w-full sm:w-auto sm:min-w-44">
            <label
              htmlFor="filtro-severidad"
              className="mb-1.5 block text-xs uppercase tracking-caps-sm text-muted"
            >
              Gravedad
            </label>
            <select
              id="filtro-severidad"
              name="severidad"
              defaultValue={severidad}
              className={inputClass}
            >
              <option value="">Todas</option>
              {SEVERIDADES.map((s) => (
                <option key={s} value={s}>
                  {SEVERITY_LABELS[s]}
                </option>
              ))}
            </select>
          </div>
          <div className="w-full sm:w-auto sm:min-w-64">
            <label
              htmlFor="filtro-grupo"
              className="mb-1.5 block text-xs uppercase tracking-caps-sm text-muted"
            >
              Tema
            </label>
            <select
              id="filtro-grupo"
              name="grupo"
              defaultValue={grupo}
              className={inputClass}
            >
              <option value="">Todos</option>
              {data.grupos.map((g) => (
                <option key={g.clave} value={g.clave}>
                  {g.titulo} ({g.total})
                </option>
              ))}
            </select>
          </div>
          <div className="w-full sm:w-auto sm:min-w-56 sm:flex-1">
            <label
              htmlFor="filtro-q"
              className="mb-1.5 block text-xs uppercase tracking-caps-sm text-muted"
            >
              Buscar
            </label>
            <input
              id="filtro-q"
              name="q"
              type="search"
              defaultValue={q}
              autoComplete="off"
              placeholder="PRD-0001, taller, precio…"
              className={inputClass}
            />
          </div>
          <button
            type="submit"
            className="inline-flex min-h-11 items-center justify-center sm:min-h-0 rounded-card border border-ink px-5 py-2.5 text-sm uppercase tracking-caps-sm hover:bg-ink hover:text-white"
          >
            Filtrar
          </button>
          {filtered ? (
            <Link
              href="/calidad"
              className="py-2.5 text-sm text-muted underline decoration-gold underline-offset-4"
            >
              Limpiar
            </Link>
          ) : null}
        </form>
      </search>

      {groups.length === 0 ? (
        <Notice
          tone="info"
          title={
            filtered
              ? "Ningún hallazgo coincide con los filtros."
              : "No hay hallazgos: los datos están en orden."
          }
        />
      ) : (
        groups.map((g) => (
          <Group key={g.clave} grupo={g} showAll={Boolean(grupo)} />
        ))
      )}
    </div>
  );
}

function Count({
  label,
  value,
  to,
  active = false,
}: {
  label: string;
  value: number;
  to: string;
  active?: boolean;
}) {
  return (
    <div
      className={`rounded-card border bg-surface p-5 shadow-card ${active ? "border-gold" : "border-line"}`}
    >
      <dt className="text-xs uppercase tracking-caps-sm text-muted">{label}</dt>
      <dd className="mt-2 font-display text-3xl tabular-nums">
        <Link
          href={to}
          aria-current={active ? "true" : undefined}
          className="underline decoration-gold underline-offset-4"
        >
          {value}
        </Link>
      </dd>
    </div>
  );
}

function Group({
  grupo,
  showAll,
}: {
  grupo: GrupoCalidad & { visibles: Hallazgo[] };
  showAll: boolean;
}) {
  const shown = showAll
    ? grupo.visibles
    : grupo.visibles.slice(0, GROUP_PREVIEW);
  return (
    <section aria-labelledby={`grupo-${grupo.clave}`}>
      <SectionTitle>
        <span id={`grupo-${grupo.clave}`}>{grupo.titulo}</span>{" "}
        <span className="text-base text-muted">({grupo.visibles.length})</span>
      </SectionTitle>
      <TableWrap>
        <table className={tableClass}>
          <caption className="sr-only">{grupo.titulo}</caption>
          <thead>
            <tr>
              <th className={thClass} scope="col">
                Gravedad
              </th>
              <th className={thClass} scope="col">
                Código
              </th>
              <th className={thClass} scope="col">
                Qué pasa
              </th>
              <th className={thClass} scope="col">
                Dónde corregirlo
              </th>
            </tr>
          </thead>
          <tbody>
            {shown.map((h, index) => (
              <tr key={`${h.entidad}-${h.mensaje}-${index}`}>
                <td className={tdClass}>
                  <Badge tone={SEVERITY_TONES[h.severidad]}>
                    {SEVERITY_LABELS[h.severidad]}
                  </Badge>
                </td>
                <td className={tdClass}>{h.entidad}</td>
                <td className={`${tdClass} max-w-xl`}>{h.mensaje}</td>
                <td className={tdClass}>
                  <Link
                    href={safeNext(h.ruta)}
                    className="underline decoration-gold underline-offset-4"
                  >
                    Ir a corregir
                    <span className="sr-only"> {h.entidad}</span>
                  </Link>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </TableWrap>
      {shown.length < grupo.visibles.length ? (
        <p className="mt-3 text-sm text-muted">
          Se muestran {shown.length} de {grupo.visibles.length}.{" "}
          <Link
            href={href({ grupo: grupo.clave })}
            className="underline decoration-gold underline-offset-4"
          >
            Ver todos los de este tema
          </Link>
        </p>
      ) : null}
    </section>
  );
}
