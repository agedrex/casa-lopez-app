import type { Metadata } from "next";
import Link from "next/link";
import { ReadOnlyNote } from "@/components/form";
import { Card, ErrorNotice, PageHeader } from "@/components/ui";
import { apiGet } from "@/lib/api";
import { canWrite } from "@/lib/permissions";
import { requireSession } from "@/lib/session";
import type { Material, Taller } from "@/lib/types";
import { LoteForm } from "./lote-form";

export const metadata: Metadata = { title: "Nuevo lote" };

export default async function NuevoLotePage() {
  const { user } = await requireSession();
  const header = (
    <>
      <p className="mb-6 text-sm">
        <Link
          href="/fabricacion"
          className="text-muted underline decoration-gold underline-offset-4"
        >
          ← Lotes
        </Link>
      </p>
      <PageHeader
        eyebrow="Lotes"
        title="Nuevo lote"
        description="Elegí quién lo hace y buscá los productos."
      />
    </>
  );
  if (!canWrite(user.role)) {
    return (
      <>
        {header}
        <ReadOnlyNote />
      </>
    );
  }

  // Products are not loaded here: the form searches the whole catalog while the person types.
  const [talleres, materiales] = await Promise.all([
    apiGet<Taller[]>("/talleres"),
    apiGet<Material[]>("/materiales"),
  ]);
  if (!talleres.ok) {
    return (
      <>
        {header}
        <ErrorNotice message={talleres.message} />
      </>
    );
  }

  // Leather data is a nice-to-have: if it fails the lot can still be created.
  const todosLosMateriales = materiales.ok ? materiales.data : [];
  const nombresCuero: Record<string, string> = Object.fromEntries(
    todosLosMateriales.map((item) => [item.codigo, item.nombre]),
  );

  return (
    <>
      {header}
      <Card>
        <LoteForm
          talleres={talleres.data
            .filter((t) => t.activo)
            .map((t) => ({
              codigo: t.codigo,
              label: t.nombre,
            }))}
          nombresCuero={nombresCuero}
        />
      </Card>
    </>
  );
}
