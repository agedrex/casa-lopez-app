import Link from "next/link";
import { inputClass } from "@/components/form";
import { Badge, Card, Notice } from "@/components/ui";
import { safeNext } from "@/lib/redirect";
import type { Calidad, Hallazgo, Severidad } from "@/lib/types";

const SEVERIDADES: Severidad[] = ["alta", "media", "baja"];
const SEVERITY_LABELS: Record<Severidad, string> = {
  alta: "Alta",
  media: "Media",
  baja: "Baja",
};
const SEVERITY_ORDER: Record<Severidad, number> = {
  alta: 0,
  media: 1,
  baja: 2,
};
const SEVERITY_TONES = {
  alta: "alert",
  media: "warn",
  baja: "neutral",
} as const;
// The list shows this many findings until "Ver todas" is pressed.
const PREVIEW = 15;

export type AlertasSearch = {
  severidad?: string | string[];
  grupo?: string | string[];
  todas?: string | string[];
};

function first(value: string | string[] | undefined): string {
  return (Array.isArray(value) ? value[0] : value)?.trim() ?? "";
}

/** Reads the alert filters out of the panel's query string. */
export function alertasFilters(params: AlertasSearch) {
  return {
    severidad: SEVERIDADES.find((s) => s === first(params.severidad)) ?? "",
    grupo: first(params.grupo),
    todas: first(params.todas) === "1",
  };
}

function href(filter: { severidad?: string; grupo?: string; todas?: boolean }) {
  const query = new URLSearchParams();
  if (filter.severidad) query.set("severidad", filter.severidad);
  if (filter.grupo) query.set("grupo", filter.grupo);
  if (filter.todas) query.set("todas", "1");
  const text = query.toString();
  return text ? `/admin/panel?${text}#alertas` : "/admin/panel#alertas";
}

type Fila = { tema: string; hallazgo: Hallazgo };

/**
 * One compact list for everything that needs attention: data that is missing, contradictory
 * or unconfirmed (including parameters), filtered by severity and topic.
 */
export function Alertas({
  data,
  severidad,
  grupo,
  todas,
}: {
  data: Calidad;
  severidad: string;
  grupo: string;
  todas: boolean;
}) {
  const filas: Fila[] = data.grupos
    .filter((g) => !grupo || g.clave === grupo)
    .flatMap((g) =>
      g.hallazgos.map((hallazgo) => ({ tema: g.titulo, hallazgo })),
    )
    .filter(({ hallazgo }) => !severidad || hallazgo.severidad === severidad);
  filas.sort(
    (a, b) =>
      SEVERITY_ORDER[a.hallazgo.severidad] -
      SEVERITY_ORDER[b.hallazgo.severidad],
  );
  const shown = todas ? filas : filas.slice(0, PREVIEW);
  const filtered = Boolean(severidad || grupo);
  const { resumen } = data;

  return (
    <Card>
      <div className="mb-4 flex flex-wrap items-baseline justify-between gap-2">
        <h2 id="alertas-titulo" className="text-lg">
          Alertas
        </h2>
        <p className="text-sm text-muted">
          {resumen.total} en total · {resumen.alta} altas · {resumen.media}{" "}
          medias · {resumen.baja} bajas
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
              Qué falta o qué revisar
            </label>
            <select
              id="filtro-grupo"
              name="grupo"
              defaultValue={grupo}
              className={inputClass}
            >
              <option value="">Todo</option>
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
              href={href({})}
              className="py-2.5 text-sm text-muted underline decoration-gold underline-offset-4"
            >
              Limpiar
            </Link>
          ) : null}
        </form>
      </search>

      {filas.length === 0 ? (
        <Notice
          tone="info"
          title={
            filtered
              ? "Ninguna alerta coincide con el filtro."
              : "No hay alertas: los datos están en orden."
          }
        />
      ) : (
        <>
          <ul>
            {shown.map(({ tema, hallazgo }, index) => (
              <li
                key={`${hallazgo.entidad}-${hallazgo.mensaje}-${index}`}
                className="flex flex-wrap items-baseline gap-x-3 gap-y-1 border-b border-line/70 py-2.5 text-sm last:border-0"
              >
                <Badge tone={SEVERITY_TONES[hallazgo.severidad]}>
                  {SEVERITY_LABELS[hallazgo.severidad]}
                </Badge>
                <span className="font-semibold">{hallazgo.entidad}</span>
                <span className="min-w-0 flex-1 basis-64">
                  {hallazgo.mensaje}
                  <span className="text-muted"> · {tema}</span>
                </span>
                {hallazgo.ruta ? (
                  <Link
                    href={safeNext(hallazgo.ruta)}
                    className="underline decoration-gold underline-offset-4"
                  >
                    Corregir
                    <span className="sr-only"> {hallazgo.entidad}</span>
                  </Link>
                ) : null}
              </li>
            ))}
          </ul>
          {shown.length < filas.length ? (
            <p className="mt-3 text-sm text-muted">
              Se muestran {shown.length} de {filas.length}.{" "}
              <Link
                href={href({ severidad, grupo, todas: true })}
                className="underline decoration-gold underline-offset-4"
              >
                Ver todas
              </Link>
            </p>
          ) : null}
        </>
      )}
      <p className="mt-4 text-xs text-muted">
        Gravedad (propuesta): alta = no se puede cotizar o cerrar; media = se
        puede, pero hay algo raro; baja = informativo.
      </p>
    </Card>
  );
}
