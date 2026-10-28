import type { Metadata } from "next";
import { ComingSoon } from "@/components/coming-soon";

export const metadata: Metadata = { title: "Calidad de datos" };

export default function Page() {
  return (
    <ComingSoon
      title="Calidad de datos"
      description="Productos con avisos para ir completando y corrigiendo."
    />
  );
}
