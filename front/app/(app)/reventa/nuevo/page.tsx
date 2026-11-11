import type { Metadata } from "next";
import Link from "next/link";
import { ReadOnlyNote } from "@/components/form";
import { Card, ErrorNotice, PageHeader } from "@/components/ui";
import { apiGet } from "@/lib/api";
import { canWrite } from "@/lib/permissions";
import { requireSession } from "@/lib/session";
import type { Catalogos } from "@/lib/types";
import { ReventaForm } from "./reventa-form";

export const metadata: Metadata = { title: "Nuevo producto de reventa" };

export default async function NuevoReventaPage() {
  const { user } = await requireSession();
  const catalogos = canWrite(user.role)
    ? await apiGet<Catalogos>("/catalogos")
    : null;
  return (
    <>
      <p className="mb-6 text-sm">
        <Link
          href="/reventa"
          className="text-muted underline decoration-gold underline-offset-4"
        >
          ← Reventa
        </Link>
      </p>
      <PageHeader
        eyebrow="Reventa"
        title="Nuevo producto de reventa"
        description="El código lo asigna la aplicación. Después de crearlo registrás la primera compra, con su costo por unidad."
      />
      {catalogos === null ? (
        <ReadOnlyNote />
      ) : catalogos.ok ? (
        <Card>
          <ReventaForm categorias={catalogos.data.categorias} />
        </Card>
      ) : (
        <ErrorNotice message={catalogos.message} />
      )}
    </>
  );
}
