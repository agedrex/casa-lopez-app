import type { Metadata } from "next";
import { ComingSoon } from "@/components/coming-soon";
import { requireRole } from "@/lib/session";

export const metadata: Metadata = { title: "Administración" };

export default async function AdminPage() {
  // Defense in depth: proxy.ts already redirects non-admins before rendering.
  await requireRole("admin");
  return (
    <ComingSoon
      title="Administración"
      description="Usuarios, roles, parámetros y datos de referencia."
    />
  );
}
