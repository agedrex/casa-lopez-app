import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { Badge, Card, PageHeader, SectionTitle } from "@/components/ui";
import { getAdminUser } from "@/lib/admin-users";
import { requireRole } from "@/lib/session";
import {
  ArchiveForm,
  BanForm,
  PasswordForm,
  ProfileForm,
  RoleForm,
} from "../user-forms";

export const metadata: Metadata = { title: "Editar usuario" };

export default async function EditarUsuarioPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { user: me } = await requireRole("admin");
  const { id } = await params;
  const user = await getAdminUser(id);
  if (!user) notFound();
  const itself = user.id === me.id;
  const reason = itself
    ? "Es su propio usuario: otro administrador debe hacer este cambio."
    : null;

  return (
    <>
      <p className="mb-6 text-sm">
        <Link
          href="/admin/usuarios"
          className="text-muted underline decoration-gold underline-offset-4"
        >
          ← Usuarios
        </Link>
      </p>
      <PageHeader
        eyebrow="Usuarios"
        title={user.name}
        description={user.email}
        actions={
          <Badge tone={user.banned ? "warn" : "good"}>
            {user.archived
              ? "Eliminado"
              : user.banned
                ? "Desactivado"
                : "Activo"}
          </Badge>
        }
      />
      <div className="space-y-10">
        <section>
          <SectionTitle>Datos</SectionTitle>
          <Card>
            <ProfileForm userId={user.id} name={user.name} email={user.email} />
          </Card>
        </section>
        <section>
          <SectionTitle>Rol</SectionTitle>
          <Card>
            <RoleForm
              userId={user.id}
              role={user.role}
              disabledReason={reason}
            />
          </Card>
        </section>
        <section>
          <SectionTitle>Contraseña</SectionTitle>
          <Card>
            <PasswordForm userId={user.id} />
          </Card>
        </section>
        <section>
          <SectionTitle>Acceso</SectionTitle>
          <Card>
            <BanForm
              userId={user.id}
              banned={user.banned}
              archived={user.archived}
              disabledReason={reason}
            />
          </Card>
        </section>
        {user.archived ? null : (
          <section>
            <SectionTitle>Eliminar</SectionTitle>
            <Card>
              <ArchiveForm userId={user.id} disabledReason={reason} />
            </Card>
          </section>
        )}
      </div>
    </>
  );
}
