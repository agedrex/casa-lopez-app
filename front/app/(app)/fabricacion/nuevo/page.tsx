import type { Metadata } from "next";
import Link from "next/link";
import { ReadOnlyNote } from "@/components/form";
import { Card, ErrorNotice, PageHeader } from "@/components/ui";
import { apiGet } from "@/lib/api";
import { todayIso } from "@/lib/format";
import { canWrite } from "@/lib/permissions";
import { requireSession } from "@/lib/session";
import type { ItemCatalogo, Material, Persona, Taller } from "@/lib/types";
import { CargarCueroForm } from "../../cueros/cargar-cuero-form";
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
        description="Elija quién lo hace (la fábrica o un taller), la fecha de envío y busque los productos; verá si alcanza el cuero. Lo demás está en «Más opciones». Los costos los calcula la aplicación."
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
  const [talleres, personas, materiales, colores] = await Promise.all([
    apiGet<Taller[]>("/talleres"),
    apiGet<Persona[]>("/personas"),
    apiGet<Material[]>("/materiales"),
    apiGet<ItemCatalogo[]>("/colores"),
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

  // Leather data is a nice-to-have: if it fails the lot can still be created.
  const todosLosMateriales = materiales.ok ? materiales.data : [];
  const cueros = todosLosMateriales.filter((item) => item.etapa === "CUERO");
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
          personas={personas.data
            .filter((p) => p.activo)
            .map((p) => ({ codigo: p.codigo, label: p.nombre }))}
          nombresCuero={nombresCuero}
          today={todayIso()}
        />
      </Card>
      {/* Outside the lot form: a form cannot sit inside another one. */}
      <details className="mt-6 rounded-card border border-line px-4">
        <summary className="min-h-11 cursor-pointer py-3 text-base text-muted">
          Cargar cuero nuevo
        </summary>
        <div className="pb-4">
          {cueros.length === 0 ? (
            <ErrorNotice
              title="No se puede cargar cuero todavía."
              message={
                materiales.ok
                  ? "No hay materiales de tipo cuero cargados."
                  : materiales.message
              }
            />
          ) : (
            <CargarCueroForm
              materiales={cueros.map((item) => ({
                value: item.codigo,
                label: item.nombre,
              }))}
              colores={
                colores.ok
                  ? colores.data.map((item) => ({
                      value: item.nombre,
                      label: item.nombre,
                    }))
                  : []
              }
              today={todayIso()}
            />
          )}
        </div>
      </details>
    </>
  );
}
