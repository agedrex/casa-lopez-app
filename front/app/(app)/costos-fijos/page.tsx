import type { Metadata } from "next";
import { ComingSoon } from "@/components/coming-soon";

export const metadata: Metadata = { title: "Costos fijos" };

export default function Page() {
  return (
    <ComingSoon
      title="Costos fijos"
      description="Gastos mensuales de fábrica y tienda."
    />
  );
}
