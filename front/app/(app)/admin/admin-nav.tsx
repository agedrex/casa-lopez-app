"use client";

import { usePathname } from "next/navigation";
import { SectionTabs } from "@/components/section-tabs";
import { ADMIN_SECTIONS, AJUSTES_SECTIONS } from "./sections";

/** Sub-navigation shared by every page under /admin: three tabs, and a second row only inside Ajustes. */
export function AdminNav() {
  const pathname = usePathname();
  const enAjustes =
    pathname.startsWith("/admin/usuarios") ||
    pathname.startsWith("/admin/sync");
  return (
    <>
      <SectionTabs
        label="Secciones de negocio y administración"
        tabs={ADMIN_SECTIONS}
      />
      {enAjustes ? (
        <SectionTabs label="Ajustes" tabs={AJUSTES_SECTIONS} />
      ) : null}
    </>
  );
}
