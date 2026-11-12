import type { Metadata } from "next";
import Link from "next/link";
import { ICONS, Icon } from "@/components/nav-icons";
import { Badge, PageHeader } from "@/components/ui";
import { listAdminUsers } from "@/lib/admin-users";
import { apiGet } from "@/lib/api";
import { splitStatus } from "@/lib/parametros";
import { requireRole } from "@/lib/session";
import type {
  Catalogos,
  Impuesto,
  ModeloLista,
  Parametro,
  Persona,
  SyncEstado,
} from "@/lib/types";
import { ADMIN_GROUPS } from "./sections";

export const metadata: Metadata = { title: "Administración" };

/** The status line of a card; null when its data could not be loaded. */
type Summary = {
  count: string;
  detail: string;
  /** Something needs a person's attention (unconfirmed, unvalidated, not configured). */
  attention?: boolean;
} | null;

function plural(n: number, one: string, many: string): string {
  return `${n} ${n === 1 ? one : many}`;
}

export default async function AdminPage() {
  // Defense in depth: proxy.ts already redirects non-admins before rendering.
  await requireRole("admin");
  const [users, parametros, modelos, catalogos, personas, impuestos, sync] =
    await Promise.all([
      listAdminUsers(),
      apiGet<Parametro[]>("/parametros"),
      apiGet<ModeloLista[]>("/modelos?limit=1000"),
      apiGet<Catalogos>("/catalogos"),
      apiGet<Persona[]>("/personas"),
      apiGet<Impuesto[]>("/impuestos"),
      apiGet<SyncEstado>("/sync/sheets/estado"),
    ]);

  const unconfirmed = parametros.ok
    ? parametros.data.filter(
        (p) => splitStatus(p.fuente_estado).state !== "Confirmado",
      ).length
    : 0;
  const unvalidated = modelos.ok
    ? modelos.data.filter((m) => !m.validado).length
    : 0;

  const summaries: Record<string, Summary> = {
    "/admin/usuarios": users.ok
      ? {
          count: plural(users.users.length, "usuario", "usuarios"),
          detail: `${users.users.filter((u) => !u.banned).length} activos`,
        }
      : null,
    "/admin/personas": personas.ok
      ? {
          count: plural(personas.data.length, "persona", "personas"),
          detail: `${personas.data.filter((p) => p.activo).length} activas`,
        }
      : null,
    "/admin/parametros": parametros.ok
      ? {
          count: plural(parametros.data.length, "parámetro", "parámetros"),
          detail: `${unconfirmed} sin confirmar`,
          attention: unconfirmed > 0,
        }
      : null,
    "/admin/impuestos": impuestos.ok
      ? {
          count: plural(impuestos.data.length, "impuesto", "impuestos"),
          detail: `${impuestos.data.filter((i) => i.es_costo_del_producto).length} cuentan como costo`,
        }
      : null,
    "/admin/modelos": modelos.ok
      ? {
          count: plural(modelos.data.length, "modelo", "modelos"),
          detail: `${unvalidated} sin validar`,
          attention: unvalidated > 0,
        }
      : null,
    "/admin/catalogos": catalogos.ok
      ? {
          count: plural(
            catalogos.data.colores.length + catalogos.data.categorias.length,
            "elemento",
            "elementos",
          ),
          detail: `${plural(catalogos.data.colores.length, "color", "colores")} · ${plural(catalogos.data.categorias.length, "categoría", "categorías")}`,
        }
      : null,
    "/admin/sync": sync.ok
      ? {
          count: sync.data.configurado ? "Configurado" : "Sin configurar",
          detail: sync.data.ultima
            ? `Última: ${sync.data.ultima.ok ? (sync.data.ultima.simulacion ? "simulación" : "sincronización") : "con error"}`
            : "Sin ejecuciones desde el último reinicio",
          attention: !sync.data.configurado,
        }
      : null,
  };

  return (
    <>
      <PageHeader
        eyebrow="Solo administradores"
        title="Administración"
        description="Las áreas del negocio que se configuran desde acá. Cada cambio queda registrado; nada se borra."
      />
      <div className="space-y-10">
        {ADMIN_GROUPS.map((group) => (
          <section key={group.title} aria-labelledby={`admin-${group.title}`}>
            <h2
              id={`admin-${group.title}`}
              className="mb-4 text-sm font-semibold uppercase tracking-caps-sm text-muted"
            >
              {group.title}
            </h2>
            <ul className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
              {group.sections.map((section) => {
                const summary = summaries[section.href];
                return (
                  <li key={section.href}>
                    <Link
                      href={section.href}
                      className="flex h-full flex-col gap-3 rounded-card border border-line bg-surface p-5 shadow-card transition-colors hover:border-gold"
                    >
                      <span className="flex items-center gap-3">
                        <span
                          aria-hidden="true"
                          className="grid size-10 shrink-0 place-items-center rounded-full bg-parchment text-ink-soft"
                        >
                          <Icon
                            path={ICONS[section.icon] ?? ICONS.more}
                            className="size-5"
                          />
                        </span>
                        <span className="text-lg">{section.title}</span>
                      </span>
                      <span className="text-sm text-muted">{section.text}</span>
                      <span className="mt-auto flex flex-wrap items-center gap-x-2 gap-y-1 border-t border-line/70 pt-3 text-sm">
                        {summary ? (
                          <>
                            <span className="tabular-nums">
                              {summary.count}
                            </span>
                            <Badge
                              tone={summary.attention ? "warn" : "neutral"}
                            >
                              {summary.detail}
                            </Badge>
                          </>
                        ) : (
                          <span className="text-muted">No disponible</span>
                        )}
                      </span>
                    </Link>
                  </li>
                );
              })}
            </ul>
          </section>
        ))}
      </div>
    </>
  );
}
