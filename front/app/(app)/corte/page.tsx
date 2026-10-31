import type { Metadata } from "next";
import { PageHeader } from "@/components/ui";

export const metadata: Metadata = { title: "Corte" };

export default function CortePage() {
  return (
    <PageHeader eyebrow="Producción" title="Próximamente: corte paso a paso" />
  );
}
