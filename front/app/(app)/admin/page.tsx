import type { Metadata } from "next";
import Link from "next/link";
import { PageHeader } from "@/components/ui";
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

export const metadata: Metadata = { title: "Administración" };

type Section = {
  href: string;
  title: string;
  text: string;
  /** The headline count, or null when its data could not be loaded. */
  count: string | null;
  detail: string;
};

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

  const sections: Section[] = [
    {
      href: "/admin/usuarios",
      title: "Usuarios",
      text: "Quién entra a la aplicación, con qué rol, y desactivar o cambiar contraseñas.",
      count: users.ok
        ? plural(users.users.length, "usuario", "usuarios")
        : null,
      detail: users.ok
        ? `${users.users.filter((u) => !u.banned).length} activos`
        : "",
    },
    {
      href: "/admin/parametros",
      title: "Parámetros",
      text: "Tolerancias, arreglos y mes de costos fijos que lee el sistema al calcular.",
      count: parametros.ok
        ? plural(parametros.data.length, "parámetro", "parámetros")
        : null,
      detail: parametros.ok
        ? `${parametros.data.filter((p) => splitStatus(p.fuente_estado).state !== "Confirmado").length} sin confirmar`
        : "",
    },
    {
      href: "/admin/modelos",
      title: "Modelos",
      text: "Consumos de cada modelo, validación y alta de modelos nuevos.",
      count: modelos.ok
        ? plural(modelos.data.length, "modelo", "modelos")
        : null,
      detail: modelos.ok
        ? `${modelos.data.filter((m) => !m.validado).length} sin validar`
        : "",
    },
    {
      href: "/admin/catalogos",
      title: "Catálogos",
      text: "Colores y categorías que se eligen al cargar productos y modelos.",
      count: catalogos.ok
        ? plural(
            catalogos.data.colores.length + catalogos.data.categorias.length,
            "elemento",
            "elementos",
          )
        : null,
      detail: catalogos.ok
        ? `${plural(catalogos.data.colores.length, "color", "colores")} · ${plural(catalogos.data.categorias.length, "categoría", "categorías")}`
        : "",
    },
    {
      href: "/admin/personas",
      title: "Personas",
      text: "Quién cobra un sueldo o hace una tarea en la fábrica.",
      count: personas.ok
        ? plural(personas.data.length, "persona", "personas")
        : null,
      detail: personas.ok
        ? `${personas.data.filter((p) => p.activo).length} activas`
        : "",
    },
    {
      href: "/admin/impuestos",
      title: "Impuestos",
      text: "Solo lectura: cómo se tratan el IVA, Ingresos Brutos y Ganancias.",
      count: impuestos.ok
        ? plural(impuestos.data.length, "impuesto", "impuestos")
        : null,
      detail: impuestos.ok
        ? `${impuestos.data.filter((i) => i.es_costo_del_producto).length} cuentan como costo`
        : "",
    },
    {
      href: "/admin/sync",
      title: "Google Sheets",
      text: "Copia para ver y consultar: simular o sincronizar las pestañas con el Sheet. Nada vuelve del Sheet a la app.",
      count: sync.ok
        ? sync.data.configurado
          ? "Configurado"
          : "Sin configurar"
        : null,
      detail: sync.ok
        ? sync.data.ultima
          ? `Última: ${sync.data.ultima.ok ? (sync.data.ultima.simulacion ? "simulación" : "sincronización") : "con error"}`
          : "Sin ejecuciones desde el último reinicio"
        : "",
    },
  ];

  return (
    <>
      <PageHeader
        eyebrow="Solo administradores"
        title="Administración"
        description="Usuarios, parámetros y datos de referencia. Cada cambio se hace desde acá; nada se borra."
      />
      <ul className="grid gap-5 sm:grid-cols-2 xl:grid-cols-3">
        {sections.map((section) => (
          <li key={section.href}>
            <Link
              href={section.href}
              className="block h-full rounded-card border border-line bg-surface p-6 shadow-card transition-colors hover:border-gold"
            >
              <h2 className="text-xl">{section.title}</h2>
              <p className="mt-3 font-display text-2xl tabular-nums">
                {section.count ?? "No disponible"}
              </p>
              {section.detail ? (
                <p className="text-xs uppercase tracking-caps-sm text-muted">
                  {section.detail}
                </p>
              ) : null}
              <p className="mt-3 text-sm text-muted">{section.text}</p>
            </Link>
          </li>
        ))}
      </ul>
    </>
  );
}
