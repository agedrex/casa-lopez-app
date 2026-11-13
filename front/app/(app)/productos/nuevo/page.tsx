import type { Metadata } from "next";
import Link from "next/link";
import { ReadOnlyNote } from "@/components/form";
import { Card, ErrorNotice, PageHeader } from "@/components/ui";
import { apiGet } from "@/lib/api";
import { todayIso } from "@/lib/format";
import { canWrite } from "@/lib/permissions";
import { requireSession } from "@/lib/session";
import type { Catalogos, Material, Modelo } from "@/lib/types";
import { ModeloNuevoForm } from "../modelos/modelo-nuevo-form";
import { ProductoForm } from "./producto-form";

export const metadata: Metadata = { title: "Nuevo producto" };

export default async function NuevoProductoPage({
  searchParams,
}: {
  searchParams: Promise<{ modelo?: string }>;
}) {
  const { modelo: modeloInicial } = await searchParams;
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
        title={modeloInicial ? "Producto del modelo" : "Nuevo modelo"}
        description={
          modeloInicial
            ? "Elija el cuero y el color: las medidas ya están validadas en el modelo."
            : "Escriba el nombre, la categoría y las notas del modelo: el taller recibe la hoja para cargar los consumos y usted la valida. Después se crea el producto (cuero y color)."
        }
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
  if (!modelos.ok || !materiales.ok || !catalogos.ok) {
    const failure = !modelos.ok
      ? modelos
      : !materiales.ok
        ? materiales
        : catalogos;
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
        <ModeloNuevoForm categorias={catalogos.data.categorias} />
      </Card>
      <details className="mt-6" open={Boolean(modeloInicial)}>
        <summary className="cursor-pointer text-sm text-muted">
          Avanzado: kit, o producto de un modelo que ya existe
        </summary>
        <Card>
          <ProductoForm
            modeloInicial={modeloInicial}
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
            colores={catalogos.data.colores}
            today={todayIso()}
          />
        </Card>
      </details>
    </>
  );
}
