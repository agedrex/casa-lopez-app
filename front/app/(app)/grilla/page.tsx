import type { Metadata } from "next";
import { ErrorNotice, PageHeader } from "@/components/ui";
import { apiGet } from "@/lib/api";
import { GrillaClient, type GrillaData } from "./grilla-client";

export const metadata: Metadata = { title: "Grilla completa" };

export default async function GrillaPage() {
  const result = await apiGet<GrillaData>("/grilla");
  return (
    <>
      <PageHeader
        eyebrow="Consultas"
        title="Grilla completa"
        description="Todos los productos y sus costos de hoy, etapa por etapa."
      />
      {result.ok ? (
        <GrillaClient data={result.data} />
      ) : (
        <ErrorNotice message={result.message} />
      )}
    </>
  );
}
