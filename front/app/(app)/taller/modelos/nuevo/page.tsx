import type { Metadata } from "next";
import Link from "next/link";
import { redirect } from "next/navigation";
import { Card, ErrorNotice, PageHeader } from "@/components/ui";
import { apiGet } from "@/lib/api";
import { canFillFormularios } from "@/lib/permissions";
import { requireSession } from "@/lib/session";
import type { Catalogos } from "@/lib/types";
import { NuevoModeloForm } from "./nuevo-modelo-form";

export const metadata: Metadata = { title: "Nuevo modelo" };

export default async function NuevoModeloDelTallerPage() {
  const { user } = await requireSession();
  if (!canFillFormularios(user.role)) redirect("/");
  const catalogos = await apiGet<Catalogos>("/catalogos");

  return (
    <>
      <p className="mb-6 text-sm">
        <Link
          href="/taller/modelos"
          className="text-muted underline decoration-gold underline-offset-4"
        >
          ← Mis modelos
        </Link>
      </p>
      <PageHeader
        eyebrow="Modelos"
        title="Nuevo modelo"
        description="Cargá el nombre, la categoría y la foto. Al guardar se abre la hoja de consumos y herrajes para completarla con las medidas reales; después el administrador la revisa y la valida."
      />
      {catalogos.ok ? (
        <Card>
          <NuevoModeloForm categorias={catalogos.data.categorias} />
        </Card>
      ) : (
        <ErrorNotice message={catalogos.message} />
      )}
    </>
  );
}
