"use client";

import { SectionTabs } from "@/components/section-tabs";
import { ADMIN_SECTIONS } from "./sections";

/** Sub-navigation shared by every page under /admin: one tab per area. */
export function AdminNav() {
  return (
    <SectionTabs label="Secciones de administración" tabs={ADMIN_SECTIONS} />
  );
}
