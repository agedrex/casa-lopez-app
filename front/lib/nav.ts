import { ROLES, type Role } from "./permissions";

export type NavItem = {
  href: string;
  label: string;
  /** Shorter label for the mobile tab bar. */
  shortLabel?: string;
  /** Key in ICONS when it differs from the href (filters of one page share it). */
  icon?: string;
  /** Path prefix that keeps this item highlighted when it differs from the href (Administración lands on /admin/panel). */
  activePrefix?: string;
  adminOnly?: boolean;
};

export type NavGroup = { title: string; items: NavItem[] };

export const NAV_ITEMS: NavGroup[] = [
  {
    title: "Configuración",
    items: [
      {
        href: "/admin/panel",
        label: "Administración",
        shortLabel: "Admin",
        icon: "/admin",
        activePrefix: "/admin",
        adminOnly: true,
      },
    ],
  },
  {
    title: "Resumen",
    items: [{ href: "/escenarios", label: "Escenarios", adminOnly: true }],
  },
  {
    title: "1 · Datos de base",
    items: [
      {
        href: "/materiales",
        label: "Materiales y precios",
        shortLabel: "Precios",
      },
      { href: "/cueros", label: "Cueros" },
      { href: "/proveedores", label: "Proveedores", adminOnly: true },
    ],
  },
  {
    title: "2 · Productos y costos",
    items: [
      { href: "/productos", label: "Productos" },
      { href: "/productos/modelos", label: "Modelos", adminOnly: true },
      { href: "/productos/catalogos", label: "Catálogos", adminOnly: true },
      { href: "/reventa", label: "Mercadería", adminOnly: true },
      { href: "/unidades", label: "Unidades producidas", adminOnly: true },
    ],
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
    title: "Herramientas",
    items: [{ href: "/voz", label: "Voz" }],
  },
];

const MOBILE_TAB_HREFS: Record<Role, readonly string[]> = {
  admin: ["/admin/panel", "/productos", "/materiales", "/fabricacion"],
  gerente: ["/productos"],
  // Three tabs around the "+" button; Voz stays one tap away in that button's quick actions.
  taller: ["/corte", "/cueros", "/productos"],
};

// Menus of the restricted roles. They match the paths of ROLE_ACCESS in permissions.ts.
const GERENTE_NAV: NavGroup[] = [
  {
    title: "Consultas",
    items: [
      { href: "/admin/panel", label: "Panel", icon: "/" },
      { href: "/productos", label: "Productos" },
      { href: "/productos/modelos", label: "Modelos" },
    ],
  },
  {
    title: "Producción",
    items: [
      { href: "/fabricacion", label: "Lotes" },
      { href: "/cueros", label: "Inventario de cuero" },
    ],
  },
  {
    title: "Abastecimiento",
    items: [
      { href: "/proveedores", label: "Proveedores" },
      { href: "/talleres", label: "Talleres" },
    ],
  },
];

// Voz is not listed: on desktop it is the microphone button of the header, on mobile the "+" quick action.
const TALLER_NAV: NavGroup[] = [
  {
    title: "Producción",
    items: [
      { href: "/corte", label: "Corte" },
      { href: "/cueros", label: "Cueros" },
    ],
  },
  {
    title: "Cotizar",
    items: [
      { href: "/productos", label: "Productos" },
      { href: "/productos/modelos", label: "Modelos" },
      { href: "/materiales", label: "Materiales y precios" },
    ],
  },
];

/** Simpler, flatter menu for the desktop sidebar. Mobile keeps NAV_ITEMS. */
const DESKTOP_NAV: NavGroup[] = [
  {
    title: "",
    items: [
      {
        href: "/admin/panel",
        label: "Administración",
        shortLabel: "Admin",
        icon: "/admin",
        activePrefix: "/admin",
        adminOnly: true,
      },
    ],
  },
  {
    title: "Producción",
    items: [
      { href: "/productos", label: "Productos" },
      { href: "/productos/modelos", label: "Modelos", adminOnly: true },
      { href: "/productos/catalogos", label: "Catálogos", adminOnly: true },
      { href: "/fabricacion", label: "Lotes" },
      { href: "/cueros", label: "Inventario de cuero" },
    ],
  },
  {
    title: "Abastecimiento",
    items: [
      { href: "/proveedores", label: "Proveedores", adminOnly: true },
      { href: "/talleres", label: "Talleres" },
    ],
  },
  {
    title: "Costos fijos",
    items: [
      // TODO: Mano de Obra and Servicios Básicos are filters of /costos-fijos until they get their own screens.
      {
        href: "/costos-fijos?bloque=personal",
        label: "Mano de obra",
        icon: "sueldos",
      },
      {
        href: "/costos-fijos?bloque=servicios",
        label: "Servicios básicos",
        icon: "servicios",
      },
    ],
  },
  {
    title: "Costos variables",
    items: [
      { href: "/unidades", label: "Unidades producidas" },
      { href: "/materiales", label: "Materiales y precios" },
      { href: "/reventa", label: "Mercadería", adminOnly: true },
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
  const groups = [
    ...(roles.includes("gerente") ? GERENTE_NAV : []),
    ...(roles.includes("taller") ? TALLER_NAV : []),
  ];
  // gerente and taller share some entries (Productos): the first group keeps them.
  const seen = new Set<string>();
  return groups
    .map((group) => ({
      ...group,
      items: group.items.filter(
        (item) => !seen.has(item.href) && seen.add(item.href),
      ),
    }))
    .filter((group) => group.items.length > 0);
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
    : [
        ...new Set(
          ROLES.flatMap((role) =>
            roles.includes(role) ? MOBILE_TAB_HREFS[role] : [],
          ),
        ),
      ];
  return hrefs.flatMap((href) => items.filter((item) => item.href === href));
}
