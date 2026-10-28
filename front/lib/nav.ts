export type NavItem = {
  href: string;
  label: string;
  adminOnly?: boolean;
};

export const NAV_ITEMS: NavItem[] = [
  { href: "/", label: "Tablero" },
  { href: "/productos", label: "Productos" },
  { href: "/materiales", label: "Materiales y precios" },
  { href: "/dolar", label: "Dólar" },
  { href: "/fabricacion", label: "Fabricación" },
  { href: "/talleres", label: "Talleres" },
  { href: "/costos-fijos", label: "Costos fijos" },
  { href: "/calidad", label: "Calidad de datos" },
  { href: "/voz", label: "Voz" },
  { href: "/admin", label: "Administración", adminOnly: true },
];
