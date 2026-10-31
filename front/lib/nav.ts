import type { Role } from "./permissions";

export type NavItem = {
  href: string;
  label: string;
  /** Shorter label for the mobile tab bar. */
  shortLabel?: string;
  adminOnly?: boolean;
};

export type NavGroup = { title: string; items: NavItem[] };

export const NAV_ITEMS: NavGroup[] = [
  {
    title: "Resumen",
    items: [{ href: "/", label: "Panel del negocio", shortLabel: "Panel" }],
  },
  {
    title: "1 · Datos de base",
    items: [
      { href: "/dolar", label: "Dólar" },
      {
        href: "/materiales",
        label: "Materiales y precios",
        shortLabel: "Precios",
      },
      { href: "/admin/modelos", label: "Modelos", adminOnly: true },
    ],
  },
  {
    title: "2 · Productos y costos",
    items: [{ href: "/productos", label: "Productos" }],
  },
  {
    title: "3 · Producción",
    items: [
      { href: "/fabricacion", label: "Lotes" },
      { href: "/talleres", label: "Talleres" },
    ],
  },
  {
    title: "4 · Fin de mes",
    items: [{ href: "/costos-fijos", label: "Costos fijos" }],
  },
  {
    title: "Consultas",
    items: [
      { href: "/grilla", label: "Grilla completa", shortLabel: "Grilla" },
    ],
  },
  { title: "Control", items: [{ href: "/calidad", label: "Alertas" }] },
  {
    title: "Herramientas",
    items: [
      { href: "/voz", label: "Voz" },
      { href: "/admin", label: "Administración", adminOnly: true },
    ],
  },
];

const MOBILE_TAB_HREFS: Record<Role, readonly string[]> = {
  admin: ["/", "/productos", "/materiales", "/fabricacion"],
  cotizador: ["/", "/productos", "/materiales", "/fabricacion"],
  consulta: ["/", "/grilla", "/productos", "/calidad"],
  corte: ["/corte", "/cueros", "/voz"],
};

const CORTE_NAV: NavGroup[] = [
  {
    title: "Producción",
    items: [
      { href: "/corte", label: "Corte" },
      { href: "/cueros", label: "Cueros" },
      { href: "/voz", label: "Voz" },
    ],
  },
];

export function navForRole(roles: Role[]): NavGroup[] {
  if (
    roles.includes("corte") &&
    !roles.includes("admin") &&
    !roles.includes("cotizador")
  ) {
    return CORTE_NAV;
  }
  return NAV_ITEMS.map((group) => ({
    ...group,
    items: group.items.filter(
      (item) => !item.adminOnly || roles.includes("admin"),
    ),
  })).filter((group) => group.items.length > 0);
}

export function mobileTabs(groups: NavGroup[], roles: Role[]): NavItem[] {
  const items = groups.flatMap((group) => group.items);
  const role = roles.includes("admin")
    ? "admin"
    : roles.includes("cotizador")
      ? "cotizador"
      : roles.includes("corte")
        ? "corte"
        : "consulta";
  const hrefs = MOBILE_TAB_HREFS[role];
  return hrefs.flatMap((href) => items.filter((item) => item.href === href));
}
