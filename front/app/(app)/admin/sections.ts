import type { SectionTab } from "@/components/section-tabs";

/** The tabs of the admin sub-navigation, in one place so they never drift apart. */
export const ADMIN_SECTIONS: SectionTab[] = [
  { href: "/admin/usuarios", title: "Usuarios" },
  { href: "/admin/impuestos", title: "Impuestos" },
  { href: "/admin/sync", title: "Google Sheets" },
];
