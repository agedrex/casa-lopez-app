import type { Metadata } from "next";
import Link from "next/link";
import { ReadOnlyNote } from "@/components/form";
import { Card, PageHeader } from "@/components/ui";
import { canWrite } from "@/lib/permissions";
import { requireSession } from "@/lib/session";
import { TallerForm } from "./taller-form";

export const metadata: Metadata = { title: "Nuevo taller" };

export default async function NuevoTallerPage() {
  const { user } = await requireSession();
  return (
    <>
      <p className="mb-6 text-sm">
        <Link
          href="/talleres"
          className="text-muted underline decoration-gold underline-offset-4"
        >
          ← Talleres
        </Link>
      </p>
      <PageHeader
        eyebrow="Talleres"
        title="Nuevo taller"
        description="El código lo asigna la aplicación. Nada se borra: un taller que ya no se usa se desactiva."
      />
      {canWrite(user.role) ? (
        <Card>
          <TallerForm />
        </Card>
      ) : (
        <ReadOnlyNote />
      )}
    </>
  );
}
