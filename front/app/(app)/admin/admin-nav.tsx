import { SectionTabs } from "@/components/section-tabs";
import { ADMIN_SECTIONS } from "./sections";

/** Sub-navigation shared by every page under /admin: one row of tabs. */
export function AdminNav() {
  return (
    <SectionTabs
      label="Secciones de negocio y administración"
      tabs={ADMIN_SECTIONS}
    />
  );
}
