import type { Metadata } from "next";
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
import { listAdminUsers } from "@/lib/admin-users";
import { formatDate } from "@/lib/format";
import { ROLE_LABELS } from "@/lib/permissions";
import { requireRole } from "@/lib/session";
import { BackToAdmin } from "../back-link";
import { BanForm, CreateUserForm, PasswordForm, RoleForm } from "./user-forms";

export const metadata: Metadata = { title: "Usuarios" };

export default async function UsuariosPage() {
  const { user: me } = await requireRole("admin");
  const result = await listAdminUsers();

  return (
    <>
      <BackToAdmin />
      <PageHeader
        eyebrow="Administración"
        title="Usuarios"
        description="Quién entra a la aplicación y con qué rol. Nadie se borra: un usuario que ya no usa la aplicación se desactiva y su historia queda."
      />
      <div className="space-y-12">
        <section>
          <SectionTitle>Usuarios</SectionTitle>
          {result.ok ? (
            <TableWrap>
              <table className={tableClass}>
                <thead>
                  <tr>
                    <th className={thClass}>Usuario</th>
                    <th className={thClass}>Rol</th>
                    <th className={thClass}>Estado</th>
                    <th className={`${thClass} ${numClass}`}>Alta</th>
                    <th className={thClass}>Gestionar</th>
                  </tr>
                </thead>
                <tbody>
                  {result.users.map((user) => {
                    const itself = user.id === me.id;
                    const reason = itself
                      ? "Es su propio usuario: otro administrador debe hacer este cambio."
                      : null;
                    return (
                      <tr key={user.id} className="hover:bg-paper-mid/50">
                        <td className={tdClass}>
                          {user.name}
                          {itself ? " (usted)" : ""}
                          <span className="block text-xs text-muted">
                            {user.email}
                          </span>
                        </td>
                        <td className={tdClass}>
                          {user.role ? ROLE_LABELS[user.role] : "Sin rol"}
                        </td>
                        <td className={tdClass}>
                          <Badge tone={user.banned ? "warn" : "good"}>
                            {user.banned ? "Desactivado" : "Activo"}
                          </Badge>
                        </td>
                        <td className={`${tdClass} ${numClass}`}>
                          {formatDate(user.createdAt)}
                        </td>
                        <td className={tdClass}>
                          <details>
                            <summary className="cursor-pointer text-sm underline decoration-gold underline-offset-4">
                              Cambiar rol, estado o contraseña
                              <span className="sr-only"> de {user.name}</span>
                            </summary>
                            <div className="mt-4 w-72 space-y-6">
                              <RoleForm
                                userId={user.id}
                                role={user.role}
                                disabledReason={reason}
                              />
                              <BanForm
                                userId={user.id}
                                banned={user.banned}
                                disabledReason={reason}
                              />
                              <PasswordForm userId={user.id} />
                            </div>
                          </details>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </TableWrap>
          ) : (
            <ErrorNotice message={result.message} />
          )}
          <div className="mt-4">
            <Notice tone="info" title="Reglas que la aplicación hace cumplir">
              Nadie puede quitarse a sí mismo el rol de administrador ni
              desactivarse, y siempre queda al menos un administrador activo.
            </Notice>
          </div>
        </section>
        <section>
          <SectionTitle>Nuevo usuario</SectionTitle>
          <Card>
            <CreateUserForm />
          </Card>
        </section>
      </div>
    </>
  );
}
