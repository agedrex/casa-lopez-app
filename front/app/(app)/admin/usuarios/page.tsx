import type { Metadata } from "next";
import Link from "next/link";
import { inputClass, SecondaryButton } from "@/components/form";
import {
  Badge,
  ErrorNotice,
  numClass,
  PageHeader,
  TableWrap,
  tableClass,
  tdClass,
  thClass,
} from "@/components/ui";
import { listAdminUsers } from "@/lib/admin-users";
import { formatDate } from "@/lib/format";
import { ROLE_LABELS } from "@/lib/permissions";
import { requireRole } from "@/lib/session";

export const metadata: Metadata = { title: "Usuarios" };

const STATES = ["activos", "desactivados", "eliminados", "todos"] as const;

type Search = Promise<{ q?: string | string[]; estado?: string | string[] }>;

function first(value: string | string[] | undefined): string {
  return (Array.isArray(value) ? value[0] : value)?.trim() ?? "";
}

export default async function UsuariosPage({
  searchParams,
}: {
  searchParams: Search;
}) {
  const { user: me } = await requireRole("admin");
  const params = await searchParams;
  const q = first(params.q).toLowerCase();
  const estado = STATES.find((s) => s === first(params.estado)) ?? "activos";
  const result = await listAdminUsers();

  const users = result.ok
    ? result.users.filter((user) => {
        const matchesState =
          estado === "todos" ||
          (estado === "activos" && !user.banned) ||
          (estado === "desactivados" && user.banned && !user.archived) ||
          (estado === "eliminados" && user.archived);
        const matchesText =
          !q ||
          user.name.toLowerCase().includes(q) ||
          user.email.toLowerCase().includes(q);
        return matchesState && matchesText;
      })
    : [];

  return (
    <>
      <PageHeader
        eyebrow="Administración"
        title="Usuarios"
        description="Quién puede entrar a la aplicación. Elija un usuario para editar sus datos, rol y contraseña, o para eliminarlo (se archiva y se puede restaurar)."
        actions={
          <Link
            href="/admin/usuarios/nuevo"
            className="rounded-card bg-ink px-5 py-2.5 text-sm uppercase tracking-caps-sm text-white hover:bg-ink-soft"
          >
            Nuevo usuario
          </Link>
        }
      />
      <form className="mb-6 flex flex-wrap items-end gap-3" method="get">
        <label className="text-sm">
          <span className="mb-1 block text-muted">Buscar</span>
          <input
            name="q"
            defaultValue={first(params.q)}
            placeholder="Nombre o correo"
            className={inputClass}
          />
        </label>
        <label className="text-sm">
          <span className="mb-1 block text-muted">Estado</span>
          <select name="estado" defaultValue={estado} className={inputClass}>
            {STATES.map((s) => (
              <option key={s} value={s}>
                {s[0].toUpperCase() + s.slice(1)}
              </option>
            ))}
          </select>
        </label>
        <SecondaryButton pending={false}>Filtrar</SecondaryButton>
      </form>
      {result.ok ? (
        <TableWrap>
          <table className={tableClass}>
            <thead>
              <tr>
                <th className={thClass}>Usuario</th>
                <th className={thClass}>Rol</th>
                <th className={thClass}>Estado</th>
                <th className={`${thClass} ${numClass}`}>Alta</th>
                <th className={thClass}>
                  <span className="sr-only">Acciones</span>
                </th>
              </tr>
            </thead>
            <tbody>
              {users.length === 0 ? (
                <tr>
                  <td className={tdClass} colSpan={5}>
                    No hay usuarios con ese filtro.
                  </td>
                </tr>
              ) : null}
              {users.map((user) => (
                <tr key={user.id} className="hover:bg-paper-mid/50">
                  <td className={tdClass}>
                    {user.name}
                    {user.id === me.id ? " (usted)" : ""}
                    <span className="block text-xs text-muted">
                      {user.email}
                    </span>
                  </td>
                  <td className={tdClass}>
                    {user.role ? ROLE_LABELS[user.role] : "Sin rol"}
                  </td>
                  <td className={tdClass}>
                    <Badge tone={user.banned ? "warn" : "good"}>
                      {user.archived
                        ? "Eliminado"
                        : user.banned
                          ? "Desactivado"
                          : "Activo"}
                    </Badge>
                  </td>
                  <td className={`${tdClass} ${numClass}`}>
                    {formatDate(user.createdAt)}
                  </td>
                  <td className={tdClass}>
                    <Link
                      href={`/admin/usuarios/${user.id}`}
                      className="text-sm underline decoration-gold underline-offset-4"
                    >
                      Editar
                      <span className="sr-only"> a {user.name}</span>
                    </Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </TableWrap>
      ) : (
        <ErrorNotice message={result.message} />
      )}
    </>
  );
}
