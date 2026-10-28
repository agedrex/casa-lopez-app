import type { Metadata } from "next";
import Link from "next/link";
import { ReadOnlyNote } from "@/components/form";
import { Card, ErrorNotice, PageHeader } from "@/components/ui";
import { apiGet } from "@/lib/api";
import { todayIso } from "@/lib/format";
import { canWrite } from "@/lib/permissions";
import { requireSession } from "@/lib/session";
import type { Catalogos, Material, Modelo } from "@/lib/types";
import { ProductoForm } from "./producto-form";

export const metadata: Metadata = { title: "Nuevo producto" };

export default async function NuevoProductoPage() {
  const { user } = await requireSession();
  const header = (
    <>
      <p className="mb-6 text-sm">
        <Link
          href="/productos"
          className="text-muted underline decoration-gold underline-offset-4"
        >
          ← Productos
        </Link>
      </p>
      <PageHeader
        eyebrow="Productos"
        title="Nuevo producto"
        description="Elija el modelo y el cuero. La receta y el costo los calcula la aplicación."
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

  const [modelos, materiales, catalogos] = await Promise.all([
    apiGet<Modelo[]>("/modelos?limit=1000"),
    apiGet<Material[]>("/materiales"),
    apiGet<Catalogos>("/catalogos"),
  ]);
  if (!modelos.ok || !materiales.ok) {
    const failure = !modelos.ok ? modelos : materiales;
    return (
      <>
        {header}
        <ErrorNotice message={failure.ok ? "" : failure.message} />
      </>
    );
  }

  return (
    <>
      {header}
      <Card>
        <ProductoForm
          modelos={modelos.data.map((modelo) => ({
            codigo: modelo.codigo,
            label: `${modelo.nombre_del_modelo}${modelo.categoria ? ` · ${modelo.categoria}` : ""}`,
          }))}
          cueros={materiales.data
            .filter((m) => m.etapa === "CUERO" && m.cotizable)
            .map((m) => ({
              codigo: m.codigo,
              label: `${m.nombre} (${m.codigo})`,
            }))}
          colores={catalogos.ok ? catalogos.data.colores : []}
          today={todayIso()}
        />
      </Card>
    </>
  );
}
