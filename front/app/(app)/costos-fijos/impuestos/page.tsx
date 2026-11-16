import type { Metadata } from "next";
import { ErrorNotice, PageHeader } from "@/components/ui";
import { apiGet } from "@/lib/api";
import { requireRole } from "@/lib/session";
import type { Impuesto } from "@/lib/types";
import { ImpuestosGrid } from "./impuesto-forms";

export const metadata: Metadata = { title: "Impuestos" };

export default async function ImpuestosPage() {
  await requireRole("admin");
  const result = await apiGet<Impuesto[]>("/impuestos");

  return (
    <>
      <PageHeader eyebrow="Costos variables" title="Impuestos" />
      {result.ok ? (
        <ImpuestosGrid impuestos={result.data} />
      ) : (
        <ErrorNotice message={result.message} />
      )}
    </>
  );
}
