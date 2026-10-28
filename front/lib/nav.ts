export type NavItem = {
  href: string;
  label: string;
  /** Shorter label for the mobile tab bar. */
  shortLabel?: string;
  /** Shown as a tab in the mobile bottom bar; the rest go under "Más". */
  primary?: boolean;
  adminOnly?: boolean;
};

export const NAV_ITEMS: NavItem[] = [
  { href: "/", label: "Tablero", primary: true },
  { href: "/productos", label: "Productos", primary: true },
  {
    href: "/materiales",
    label: "Materiales y precios",
    shortLabel: "Precios",
    primary: true,
  },
  {
    href: "/fabricacion",
    label: "Fabricación",
    shortLabel: "Lotes",
    primary: true,
  },
  { href: "/dolar", label: "Dólar" },
  { href: "/talleres", label: "Talleres" },
  { href: "/costos-fijos", label: "Costos fijos" },
  { href: "/calidad", label: "Calidad de datos" },
  { href: "/voz", label: "Voz" },
  { href: "/admin", label: "Administración", adminOnly: true },
];
