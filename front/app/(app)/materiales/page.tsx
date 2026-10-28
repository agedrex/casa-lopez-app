import type { Metadata } from "next";
import { ComingSoon } from "@/components/coming-soon";

export const metadata: Metadata = { title: "Materiales y precios" };

export default function Page() {
  return (
    <ComingSoon
      title="Materiales y precios"
      description="Catálogo de materiales, precios con fecha y recotización."
    />
  );
}
