import type { Metadata } from "next";
import Link from "next/link";
import { Card, PageHeader } from "@/components/ui";
import { requireRole } from "@/lib/session";
import { CreateUserForm } from "../user-forms";

export const metadata: Metadata = { title: "Nuevo usuario" };

export default async function NuevoUsuarioPage() {
  await requireRole("admin");
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
      <PageHeader eyebrow="Usuarios" title="Nuevo usuario" />
      <Card>
        <CreateUserForm />
      </Card>
    </>
  );
}
