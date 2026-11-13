import type { Metadata } from "next";
import Link from "next/link";
import { ReadOnlyNote } from "@/components/form";
import { Card, ErrorNotice, PageHeader } from "@/components/ui";
import { apiGet } from "@/lib/api";
import { todayIso } from "@/lib/format";
import { canWrite } from "@/lib/permissions";
import { requireSession } from "@/lib/session";
import type { Persona, Taller } from "@/lib/types";
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
        description="Elija quién lo hace (la fábrica o un taller), la fecha de envío y busque los productos. Lo demás está en «Más opciones». Los costos los calcula la aplicación."
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
  const [talleres, personas] = await Promise.all([
    apiGet<Taller[]>("/talleres"),
    apiGet<Persona[]>("/personas"),
  ]);
  const failed = [talleres, personas].find((r) => !r.ok);
  if (failed && !failed.ok) {
    return (
      <>
        {header}
        <ErrorNotice message={failed.message} />
      </>
    );
  }
  if (!talleres.ok || !personas.ok) return header;

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
          personas={personas.data
            .filter((p) => p.activo)
            .map((p) => ({ codigo: p.codigo, label: p.nombre }))}
          today={todayIso()}
        />
      </Card>
    </>
  );
}
