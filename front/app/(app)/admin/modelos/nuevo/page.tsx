import type { Metadata } from "next";
import Link from "next/link";
import { Card, ErrorNotice, PageHeader } from "@/components/ui";
import { apiGet } from "@/lib/api";
import { requireRole } from "@/lib/session";
import type { Catalogos, Material } from "@/lib/types";
import { ModeloNuevoForm } from "../modelo-nuevo-form";

export const metadata: Metadata = { title: "Nuevo modelo" };

export default async function NuevoModeloPage() {
  await requireRole("admin");
  const [catalogos, materiales] = await Promise.all([
    apiGet<Catalogos>("/catalogos"),
    apiGet<Material[]>("/materiales"),
  ]);
  const error = !catalogos.ok ? catalogos : !materiales.ok ? materiales : null;

  return (
    <>
      <p className="mb-6 text-sm">
        <Link
          href="/admin/modelos"
          className="text-muted underline decoration-gold underline-offset-4"
        >
          ← Modelos
        </Link>
      </p>
      <PageHeader
        eyebrow="Administración"
        title="Nuevo modelo"
        description="El código lo asigna la aplicación y el modelo nace sin validar. Los consumos de un modelo ya creado se editan desde su ficha."
      />
      {error ? (
        <ErrorNotice message={error.message} />
      ) : catalogos.ok && materiales.ok ? (
        <Card>
          <ModeloNuevoForm
            categorias={catalogos.data.categorias}
            forros={materiales.data
              .filter((m) => m.etapa === "FORRO" && m.cotizable)
              .map((m) => ({
                codigo: m.codigo,
                label: `${m.codigo} · ${m.nombre}`,
              }))}
          />
        </Card>
      ) : null}
    </>
  );
}
