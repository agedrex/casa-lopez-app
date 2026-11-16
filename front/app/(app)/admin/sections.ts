import type { SectionTab } from "@/components/section-tabs";

/** The tabs of the admin sub-navigation, in one place so they never drift apart (Impuestos lives in Costos variables). */
export const ADMIN_SECTIONS: SectionTab[] = [
  { href: "/admin/panel", title: "Panel" },
  { href: "/admin/usuarios", title: "Usuarios" },
  { href: "/admin/sync", title: "Google Sheets" },
];
