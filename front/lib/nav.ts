import { ROLES, type Role } from "./permissions";

export type NavItem = {
  href: string;
  label: string;
  /** Shorter label for the mobile tab bar. */
  shortLabel?: string;
  /** Key in ICONS when it differs from the href (filters of one page share it). */
  icon?: string;
  /** Path prefix that keeps this item highlighted when it differs from the href (Negocio y Administración lands on /admin/panel). */
  activePrefix?: string;
  /** Other path prefixes that keep this item highlighted (Lotes y modelos also lives under /taller/modelos). */
  alsoActiveOn?: string[];
  adminOnly?: boolean;
};

export type NavGroup = { title: string; items: NavItem[] };

export const NAV_ITEMS: NavGroup[] = [
  {
    title: "Configuración",
    items: [
      {
        href: "/admin/panel",
        label: "Negocio y Administración",
        shortLabel: "Negocio",
        icon: "/admin",
        activePrefix: "/admin",
        adminOnly: true,
      },
    ],
  },
  {
    title: "1 · Datos de base",
    items: [
      {
        href: "/materiales",
        label: "Materiales y precios",
        shortLabel: "Precios",
      },
      { href: "/proveedores", label: "Proveedores", adminOnly: true },
    ],
  },
  {
    title: "2 · Productos y costos",
    items: [
      { href: "/productos", label: "Productos" },
      { href: "/productos/modelos", label: "Modelos", adminOnly: true },
      { href: "/reventa", label: "Mercadería", adminOnly: true },
      { href: "/unidades", label: "Unidades producidas", adminOnly: true },
      {
        href: "/costos-fijos/impuestos",
        label: "Impuestos",
        icon: "/admin/impuestos",
        adminOnly: true,
      },
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
  {
    title: "Resumen",
    items: [{ href: "/escenarios", label: "Escenarios", adminOnly: true }],
  },
];

const MOBILE_TAB_HREFS: Record<Role, readonly string[]> = {
  admin: ["/admin/panel", "/productos", "/fabricacion"],
  gerente: ["/productos", "/escenarios"],
  // Lotes y modelos and Voz: the two things the taller does from the phone.
  taller: ["/fabricacion", "/voz"],
};

// Menus of the restricted roles. They match the paths of ROLE_ACCESS in permissions.ts.
const GERENTE_NAV: NavGroup[] = [
  {
    title: "Consultas",
    items: [
      { href: "/productos", label: "Productos" },
      { href: "/productos/modelos", label: "Modelos" },
    ],
  },
  {
    title: "Simulador",
    items: [{ href: "/escenarios", label: "Escenarios" }],
  },
];

// Voz is not listed: on desktop it is the microphone button of the header; on mobile it is a bottom tab (TALLER_TAB_EXTRAS).
// A single entry, no groups: the lots (the product sheet is opened from a lot) and the models the admin sent to the taller.
const TALLER_NAV: NavGroup[] = [
  {
    title: "",
    items: [
      {
        href: "/fabricacion",
        label: "Lotes y modelos",
        icon: "/fabricacion",
        alsoActiveOn: ["/taller/modelos"],
      },
    ],
  },
];

/** Tabs of the taller bottom bar that are not entries of its menu (/corte is closed to the role, see ROLE_ACCESS). */
const TALLER_TAB_EXTRAS: NavItem[] = [{ href: "/voz", label: "Voz" }];

/** Simpler, flatter menu for the desktop sidebar. Mobile keeps NAV_ITEMS. */
const DESKTOP_NAV: NavGroup[] = [
  {
    title: "",
    items: [
      {
        href: "/admin/panel",
        label: "Negocio y Administración",
        shortLabel: "Negocio",
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
      { href: "/fabricacion", label: "Lotes" },
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
      {
        href: "/costos-fijos/impuestos",
        label: "Impuestos",
        icon: "/admin/impuestos",
        adminOnly: true,
      },
    ],
  },
  {
    title: "Simulador",
    items: [{ href: "/escenarios", label: "Escenarios", adminOnly: true }],
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

/** Menu of the mobile "Más" sheet: same groups and order as the desktop sidebar. */
export function navForRole(roles: Role[]): NavGroup[] {
  return desktopNavForRole(roles);
}

export function mobileTabs(groups: NavGroup[], roles: Role[]): NavItem[] {
  const menu = groups.flatMap((group) => group.items);
  const extras =
    !roles.includes("admin") && roles.includes("taller")
      ? TALLER_TAB_EXTRAS.filter(
          (extra) => !menu.some((item) => item.href === extra.href),
        )
      : [];
  const items = [...menu, ...extras];
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
