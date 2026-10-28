import type { Metadata } from "next";
import { ComingSoon } from "@/components/coming-soon";

export const metadata: Metadata = { title: "Fabricación" };

export default function Page() {
  return (
    <ComingSoon
      title="Fabricación"
      description="Órdenes por taller con cantidades, fechas y precios reales."
    />
  );
}
