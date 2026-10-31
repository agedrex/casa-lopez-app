import type { Metadata } from "next";
import { PageHeader } from "@/components/ui";

export const metadata: Metadata = { title: "Cueros" };

export default function CuerosPage() {
  return <PageHeader eyebrow="Producción" title="Próximamente: cueros" />;
}
