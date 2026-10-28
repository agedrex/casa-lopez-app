import type { Metadata } from "next";
import { ComingSoon } from "@/components/coming-soon";

export const metadata: Metadata = { title: "Voz" };

export default function Page() {
  return (
    <ComingSoon
      title="Voz"
      description="Carga por voz: el asistente interpreta lo dicho y una persona confirma antes de guardar."
    />
  );
}
