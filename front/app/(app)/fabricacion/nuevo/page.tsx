import type { Metadata } from "next";
import Link from "next/link";
import { ReadOnlyNote } from "@/components/form";
import { Card, ErrorNotice, PageHeader } from "@/components/ui";
import { apiGet } from "@/lib/api";
import { todayIso } from "@/lib/format";
import { canWrite } from "@/lib/permissions";
import { requireSession } from "@/lib/session";
import type { Persona, ProductoResumen, Taller } from "@/lib/types";
import { LoteForm } from "./lote-form";

export const metadata: Metadata = { title: "Nuevo lote" };

// The API caps a page at 500 products; the picker offers what it receives.
const PRODUCT_LIMIT = 500;

export default async function NuevoLotePage() {
  const { user } = await requireSession();
  const header = (
    <>
      <p className="mb-6 text-sm">
        <Link
          href="/fabricacion"
          className="text-muted underline decoration-gold underline-offset-4"
        >
          ← Fabricación
        </Link>
      </p>
      <PageHeader
        eyebrow="Fabricación"
        title="Nuevo lote"
        description="Elija dónde se hace, a quién se le manda y qué productos lleva. Los costos los calcula la aplicación."
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

  const [talleres, personas, productos] = await Promise.all([
    apiGet<Taller[]>("/talleres"),
    apiGet<Persona[]>("/personas"),
    apiGet<ProductoResumen[]>(`/productos?limit=${PRODUCT_LIMIT}`),
  ]);
  const failed = [talleres, personas, productos].find((r) => !r.ok);
  if (failed && !failed.ok) {
    return (
      <>
        {header}
        <ErrorNotice message={failed.message} />
      </>
    );
  }
  if (!talleres.ok || !personas.ok || !productos.ok) return header;

  return (
    <>
      {header}
      <Card>
        <LoteForm
          talleres={talleres.data
            .filter((t) => t.activo)
            .map((t) => ({
              codigo: t.codigo,
              label: `${t.nombre}${t.ejemplo ? " (ejemplo)" : ""}`,
            }))}
          personas={personas.data
            .filter((p) => p.activo)
            .map((p) => ({ codigo: p.codigo, label: p.nombre }))}
          productos={productos.data.map((p) => ({
            codigo: p.codigo,
            label: p.nombre,
          }))}
          today={todayIso()}
        />
      </Card>
    </>
  );
}
