import type { Metadata } from "next";
import Link from "next/link";
import { Card, ErrorNotice, PageHeader } from "@/components/ui";
import { apiGet } from "@/lib/api";
import { requireRole } from "@/lib/session";
import type { Catalogos } from "@/lib/types";
import { ModeloNuevoForm } from "../modelo-nuevo-form";

export const metadata: Metadata = { title: "Nuevo modelo" };

export default async function NuevoModeloPage() {
  await requireRole("admin");
  const catalogos = await apiGet<Catalogos>("/catalogos");

  return (
    <>
      <p className="mb-6 text-sm">
        <Link
          href="/productos/modelos"
          className="text-muted underline decoration-gold underline-offset-4"
        >
          ← Modelos
        </Link>
      </p>
      <PageHeader
        eyebrow="Productos"
        title="Nuevo modelo"
        description="Escriba el nombre, la categoría y las notas del modelo: el taller recibe la hoja para cargar todos los consumos y usted la valida. Al validarla queda como la receta del modelo."
      />
      {catalogos.ok ? (
        <Card>
          <ModeloNuevoForm categorias={catalogos.data.categorias} />
        </Card>
      ) : (
        <ErrorNotice message={catalogos.message} />
      )}
    </>
  );
}
