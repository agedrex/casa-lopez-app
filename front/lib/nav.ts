import { ROLES, type Role } from "./permissions";

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
      { href: "/cueros", label: "Cueros" },
      { href: "/proveedores", label: "Proveedores", adminOnly: true },
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
  gerente: ["/productos", "/grilla"],
  taller: ["/corte", "/cueros", "/voz"],
};

// Menus of the restricted roles. They match the paths of ROLE_ACCESS in permissions.ts.
const GERENTE_NAV: NavGroup[] = [
  {
    title: "Consultas",
    items: [
      { href: "/productos", label: "Productos" },
      { href: "/grilla", label: "Grilla completa", shortLabel: "Grilla" },
    ],
  },
];

const TALLER_NAV: NavGroup[] = [
  {
    title: "Producción",
    items: [
      { href: "/corte", label: "Corte" },
      { href: "/cueros", label: "Cueros" },
      { href: "/voz", label: "Voz" },
    ],
  },
];

/** Simpler, flatter menu for the desktop sidebar. Mobile keeps NAV_ITEMS. */
const DESKTOP_NAV: NavGroup[] = [
  {
    title: "",
    items: [
      { href: "/", label: "Panel del negocio" },
      { href: "/productos", label: "Productos" },
    ],
  },
  {
    title: "Costos",
    items: [
      { href: "/materiales", label: "Materiales y precios" },
      { href: "/cueros", label: "Cueros" },
      { href: "/dolar", label: "Dólar" },
      { href: "/proveedores", label: "Proveedores", adminOnly: true },
      { href: "/admin/modelos", label: "Modelos", adminOnly: true },
    ],
  },
  {
    title: "Producción",
    items: [
      { href: "/fabricacion", label: "Lotes" },
      { href: "/talleres", label: "Talleres" },
      { href: "/costos-fijos", label: "Costos fijos" },
    ],
  },
  {
    title: "Revisión",
    items: [
      { href: "/grilla", label: "Grilla completa" },
      { href: "/calidad", label: "Alertas" },
    ],
  },
  {
    title: "",
    items: [
      { href: "/voz", label: "Voz" },
      { href: "/admin", label: "Administración", adminOnly: true },
    ],
  },
];

function filterByRole(groups: NavGroup[], roles: Role[]): NavGroup[] {
  return groups
    .map((group) => ({
      ...group,
      items: group.items.filter(
        (item) => !item.adminOnly || roles.includes("admin"),
      ),
    }))
    .filter((group) => group.items.length > 0);
}

/** Admin gets the full menu; the other roles get only their own groups (none for no role). */
function restrictedNav(roles: Role[]): NavGroup[] {
  return [
    ...(roles.includes("gerente") ? GERENTE_NAV : []),
    ...(roles.includes("taller") ? TALLER_NAV : []),
  ];
}

export function desktopNavForRole(roles: Role[]): NavGroup[] {
  return roles.includes("admin")
    ? filterByRole(DESKTOP_NAV, roles)
    : restrictedNav(roles);
}

export function navForRole(roles: Role[]): NavGroup[] {
  return roles.includes("admin")
    ? filterByRole(NAV_ITEMS, roles)
    : restrictedNav(roles);
}

export function mobileTabs(groups: NavGroup[], roles: Role[]): NavItem[] {
  const items = groups.flatMap((group) => group.items);
  const hrefs = roles.includes("admin")
    ? MOBILE_TAB_HREFS.admin
    : ROLES.flatMap((role) =>
        roles.includes(role) ? MOBILE_TAB_HREFS[role] : [],
      );
  return hrefs.flatMap((href) => items.filter((item) => item.href === href));
}
