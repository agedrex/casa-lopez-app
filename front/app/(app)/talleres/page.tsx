import type { Metadata } from "next";
import { ComingSoon } from "@/components/coming-soon";

export const metadata: Metadata = { title: "Talleres" };

export default function Page() {
  return (
    <ComingSoon
      title="Talleres"
      description="Agenda de talleres y personas que confeccionan."
    />
  );
}
