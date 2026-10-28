import type { Metadata } from "next";
import { ComingSoon } from "@/components/coming-soon";

export const metadata: Metadata = { title: "Grilla completa" };

export default function GrillaPage() {
  return (
    <ComingSoon
      title="Grilla completa"
      description="Acá vas a poder consultar todos los productos y sus costos juntos."
    />
  );
}
