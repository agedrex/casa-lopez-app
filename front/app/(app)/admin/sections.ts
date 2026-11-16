import type { SectionTab } from "@/components/section-tabs";

/** The three tabs of the admin sub-navigation, in one place so they never drift apart. */
export const ADMIN_SECTIONS: SectionTab[] = [
  { href: "/admin/panel", title: "Panel" },
  { href: "/admin/negocio", title: "Negocio" },
  { href: "/admin/impuestos", title: "Impuestos" },
  {
    href: "/admin/usuarios",
    title: "Ajustes",
    alsoActiveOn: ["/admin/sync"],
  },
];

/** Second row, shown only inside Ajustes: the pages used rarely (people and the Google Sheet copy). */
export const AJUSTES_SECTIONS: SectionTab[] = [
  { href: "/admin/usuarios", title: "Usuarios" },
  { href: "/admin/sync", title: "Google Sheets" },
];
