import Link from "next/link";
import { inputClass } from "@/components/form";
import { Badge, Card, Notice } from "@/components/ui";
import { agruparAlertas } from "@/lib/alertas-grupos";
import { safeNext } from "@/lib/redirect";
import type { Calidad, Severidad } from "@/lib/types";

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

export type AlertasSearch = {
  severidad?: string | string[];
  grupo?: string | string[];
};

function first(value: string | string[] | undefined): string {
  return (Array.isArray(value) ? value[0] : value)?.trim() ?? "";
}

/** Reads the alert filters out of the panel's query string. */
export function alertasFilters(params: AlertasSearch) {
  return {
    severidad: SEVERIDADES.find((s) => s === first(params.severidad)) ?? "",
    grupo: first(params.grupo),
  };
}

/**
 * Everything that needs attention, grouped by type. Groups start collapsed (<details>) so 300+
 * alerts do not push the page down; the filters narrow the groups and their counters.
 */
export function Alertas({
  data,
  severidad,
  grupo,
}: {
  data: Calidad;
  severidad: string;
  grupo: string;
}) {
  const grupos = agruparAlertas(data.grupos, severidad, grupo);
  const filtered = Boolean(severidad || grupo);
  const { resumen } = data;

  return (
    <Card>
      <div className="mb-4 flex flex-wrap items-baseline justify-between gap-2">
        <h2 id="alertas-titulo" className="text-lg">
          Alertas
        </h2>
        <p className="text-sm text-muted">
          {resumen.total} · {resumen.alta} altas · {resumen.media} medias ·{" "}
          {resumen.baja} bajas
        </p>
      </div>

      <search>
        <form
          method="get"
          action="/admin/panel#alertas"
          className="mb-4 flex flex-wrap items-end gap-3"
        >
          <div className="w-full sm:w-auto sm:min-w-40">
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
                  {SEVERITY_LABELS[s]} ({resumen[s]})
                </option>
              ))}
            </select>
          </div>
          <div className="w-full sm:w-auto sm:min-w-64">
            <label
              htmlFor="filtro-grupo"
              className="mb-1.5 block text-xs uppercase tracking-caps-sm text-muted"
            >
              Tipo
            </label>
            <select
              id="filtro-grupo"
              name="grupo"
              defaultValue={grupo}
              className={inputClass}
            >
              <option value="">Todos</option>
              {data.grupos
                .filter((g) => g.total > 0)
                .map((g) => (
                  <option key={g.clave} value={g.clave}>
                    {g.titulo} ({g.total})
                  </option>
                ))}
            </select>
          </div>
          <button
            type="submit"
            className="inline-flex min-h-11 items-center justify-center sm:min-h-0 rounded-card border border-ink px-5 py-2.5 text-sm uppercase tracking-caps-sm hover:bg-ink hover:text-white"
          >
            Filtrar
          </button>
          {filtered ? (
            <Link
              href="/admin/panel#alertas"
              className="py-2.5 text-sm text-muted underline decoration-gold underline-offset-4"
            >
              Limpiar
            </Link>
          ) : null}
        </form>
      </search>

      {grupos.length === 0 ? (
        <Notice
          tone="info"
          title={filtered ? "Sin alertas con ese filtro." : "Sin alertas."}
        />
      ) : (
        <div className="border-t border-line/70">
          {grupos.map((g) => (
            <details key={g.clave} className="group border-b border-line/70">
              <summary className="flex min-h-11 cursor-pointer list-none items-center gap-3 py-2.5 text-sm [&::-webkit-details-marker]:hidden">
                <span
                  aria-hidden="true"
                  className="text-muted transition-transform group-open:rotate-90"
                >
                  ▸
                </span>
                <span className="flex-1 font-semibold">{g.titulo}</span>
                <Badge tone={SEVERITY_TONES[g.maxima]}>{g.total}</Badge>
              </summary>
              <ul className="pb-2 pl-6">
                {g.items.map((item, index) => (
                  <li
                    key={`${item.codigo}-${item.detalle}-${index}`}
                    className="flex flex-wrap items-baseline gap-x-3 gap-y-1 border-t border-line/50 py-2 text-sm"
                  >
                    <Badge tone={SEVERITY_TONES[item.severidad]}>
                      {SEVERITY_LABELS[item.severidad]}
                    </Badge>
                    <span className="min-w-0 flex-1 basis-64">
                      <span className="font-semibold">
                        {item.nombre ?? item.codigo}
                      </span>
                      {item.nombre ? (
                        <span className="text-muted"> · {item.codigo}</span>
                      ) : null}
                      <span className="text-muted"> · {item.detalle}</span>
                    </span>
                    {item.ruta ? (
                      <Link
                        href={safeNext(item.ruta)}
                        className="underline decoration-gold underline-offset-4"
                      >
                        Corregir
                        <span className="sr-only">
                          {" "}
                          {item.nombre ?? item.codigo}
                        </span>
                      </Link>
                    ) : null}
                  </li>
                ))}
              </ul>
            </details>
          ))}
        </div>
      )}
    </Card>
  );
}
