import type { Metadata } from "next";
import { ComingSoon } from "@/components/coming-soon";

export const metadata: Metadata = { title: "Histórico (Excel viejo)" };

export default function HistoricoPage() {
  return (
    <ComingSoon
      title="Histórico (Excel viejo)"
      description="Consulta de los datos del Excel anterior."
    />
  );
}
