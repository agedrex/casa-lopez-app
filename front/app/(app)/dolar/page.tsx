import type { Metadata } from "next";
import { ComingSoon } from "@/components/coming-soon";

export const metadata: Metadata = { title: "Dólar" };

export default function Page() {
  return (
    <ComingSoon
      title="Dólar"
      description="Historial de cotizaciones del dólar y carga del valor del día."
    />
  );
}
