import type { Metadata } from "next";
import Link from "next/link";
import { ReadOnlyNote } from "@/components/form";
import { Card, ErrorNotice, PageHeader } from "@/components/ui";
import { apiGet } from "@/lib/api";
import { canWrite } from "@/lib/permissions";
import { requireSession } from "@/lib/session";
import type { Taller } from "@/lib/types";
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
        help={[
          "Elegí quién lo hace: la fábrica o un taller.",
          "Buscá los productos y poné las cantidades.",
          "Al crearlo, se abre el lote.",
        ].map((line) => <p key={line}>{line}</p>)}
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
  const talleres = await apiGet<Taller[]>("/talleres");
  if (!talleres.ok) {
    return (
      <>
        {header}
        <ErrorNotice message={talleres.message} />
      </>
    );
  }

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
        />
      </Card>
    </>
  );
}
