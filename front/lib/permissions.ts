import { createAccessControl } from "better-auth/plugins/access";
import { defaultStatements } from "better-auth/plugins/admin/access";

export const ROLES = ["admin", "gerente", "taller"] as const;
export type Role = (typeof ROLES)[number];

// SUPUESTO: validar. A new user is a read-only manager unless an admin says otherwise
// (the previous default, `consulta`, was also read-only).
export const DEFAULT_ROLE: Role = "gerente";

export const ROLE_LABELS: Record<Role, string> = {
  admin: "Administrador",
  gerente: "Gerente",
  taller: "Taller",
};

/**
 * Role names that may still be stored in `public."user"`. They are only mapped when READING
 * (see `parseRoles`), so existing users keep their access with no database update. New
 * writes (create user, set role) accept only ROLES.
 */
const LEGACY_ROLES: Record<string, Role> = {
  cotizador: "admin",
  corte: "taller",
  consulta: "gerente",
};

const ac = createAccessControl(defaultStatements);

// Only `admin` manages users (Better Auth admin plugin statements). `gerente` and `taller`
// carry no user-management permission; modules decide what these roles may do inside the app.
// Nothing is deleted from the app: the admin role does not get `delete` (remove-user),
// `update` (admin update-user could change a role or a ban around the guards in auth.ts),
// `set-email`, nor impersonation, so those endpoints answer 403 even to an admin.
export const roles = {
  admin: ac.newRole({
    user: ["create", "list", "get", "set-role", "ban", "set-password"],
    session: ["list", "revoke"],
  }),
  gerente: ac.newRole({}),
  taller: ac.newRole({}),
};

export { ac };

/** Better Auth stores several roles as a comma separated string. */
function splitRoles(value: string | null | undefined): string[] {
  return (value ?? "")
    .split(",")
    .map((role) => role.trim())
    .filter(Boolean);
}

/**
 * Roles of a stored value, in ROLES order and without repeats. Legacy names are mapped
 * (cotizador -> admin, corte -> taller, consulta -> gerente) and several roles give the
 * union; any other name is dropped.
 */
export function parseRoles(value: string | null | undefined): Role[] {
  const found = new Set<Role>();
  for (const name of splitRoles(value)) {
    if ((ROLES as readonly string[]).includes(name)) found.add(name as Role);
    else if (name in LEGACY_ROLES) found.add(LEGACY_ROLES[name]);
  }
  return ROLES.filter((role) => found.has(role));
}

export function hasRole(value: string | null | undefined, role: Role): boolean {
  return parseRoles(value).includes(role);
}

/**
 * True only when the stored value literally holds `admin`. A legacy `cotizador` is an admin
 * for the app (parseRoles) but NOT for Better Auth, which never knew that role: the
 * "last admin" rules of the user list must count only the accounts that can really manage users.
 */
export function isStoredAdmin(value: string | null | undefined): boolean {
  return splitRoles(value).includes("admin");
}

// Only admin writes: every form, the save-price button and every server action.
// The UI hides them from everybody else; the backend still answers 403.
export const WRITE_ROLES: readonly Role[] = ["admin"];

export function canWrite(value: string | null | undefined): boolean {
  return parseRoles(value).some((role) => WRITE_ROLES.includes(role));
}

/**
 * The sale price of a product (S4 of flujo-modelos-lotes-precio): admin and gerente see the price block of the product
 * sheet and choose the margin; both may save it. The one write the gerente has; the backend checks it again (403).
 */
export function canSetPrice(value: string | null | undefined): boolean {
  const roles = parseRoles(value);
  return roles.includes("admin") || roles.includes("gerente");
}

/** Voice: interpreting a request is open to admin and taller (confirming a load stays admin only). */
export function canUseVoice(value: string | null | undefined): boolean {
  const roles = parseRoles(value);
  return roles.includes("admin") || roles.includes("taller");
}

/**
 * The consumption sheet of a new model (the screens under /taller/modelos): admin and taller work on it, the taller fills
 * it with real data and the admin reviews it. The gerente never opens it. The backend checks it again (403).
 */
export function canFillFormularios(value: string | null | undefined): boolean {
  const roles = parseRoles(value);
  return roles.includes("admin") || roles.includes("taller");
}

/**
 * Where each role lands and which paths it may open. `null` paths = everything. `paths` open a
 * route and everything below it; `exact` open only that route. `denyExact` and `denyPrefix` carve
 * holes in `paths` (taller opens the product SHEET, /productos/<code>, but not the product LIST,
 * /productos, nor Modelos).
 */
const ROLE_ACCESS: Record<
  Role,
  {
    home: string;
    paths: readonly string[] | null;
    exact?: readonly string[];
    denyExact?: readonly string[];
    denyPrefix?: readonly string[];
  }
> = {
  admin: { home: "/admin/panel", paths: null },
  // Gerente reads Productos (list, sheet and Modelos) and runs the scenario simulator. Nothing else:
  // no Panel, Lotes, Cueros, Proveedores nor Talleres (S8).
  // `/api/modelos` is the model photo (an <img> source, read only, the backend answers 403 for anything else).
  gerente: {
    home: "/productos",
    paths: ["/productos", "/escenarios", "/api/modelos"],
  },
  // Taller opens the lots list (what to make and how many) and, from each product of a lot, the
  // product sheet (materials and recipe, no prices); Voz is a header button (not in the menu). It also
  // fills the consumption sheet of the models the admin sends it (it does not create models): /taller/modelos
  // (my models) and /taller/modelos/<FCO-nnnn>. The product LIST, Modelos
  // (the admin ones under /productos), Materiales, Corte and Cueros stay closed to it
  // (demo-staging-taller-grilla S2).
  taller: {
    home: "/fabricacion",
    paths: [
      "/fabricacion",
      "/voz",
      "/productos",
      "/taller/modelos",
      "/api/modelos",
    ],
    denyExact: ["/productos"],
    denyPrefix: ["/productos/modelos"],
  },
};

/** Home of a user with no recognized role: a page that only explains it. */
export const NO_ROLE_HOME = "/sin-acceso";

const matchesPath = (pathname: string, route: string) =>
  pathname === route || pathname.startsWith(`${route}/`);

/** Every "new" form: only an admin opens them (the other roles read, they do not write). */
const ADMIN_ONLY_PATHS = [
  "/productos/nuevo",
  "/productos/modelos/nuevo",
  "/fabricacion/nuevo",
  "/talleres/nuevo",
] as const;

/** First role in ROLES order decides the landing page. */
export function homePath(value: string | null | undefined): string {
  const [role] = parseRoles(value);
  return role ? ROLE_ACCESS[role].home : NO_ROLE_HOME;
}

/** Deny by default: a path is open only if one of the user's roles lists it. */
export function canAccessPath(
  value: string | null | undefined,
  pathname: string,
): boolean {
  const roles = parseRoles(value);
  if (roles.length === 0) return matchesPath(pathname, NO_ROLE_HOME);
  if (
    !roles.includes("admin") &&
    ADMIN_ONLY_PATHS.some((route) => matchesPath(pathname, route))
  ) {
    return false;
  }
  return roles.some((role) => {
    const { paths, exact, denyExact, denyPrefix } = ROLE_ACCESS[role];
    if (
      (denyExact?.includes(pathname) ?? false) ||
      (denyPrefix?.some((route) => matchesPath(pathname, route)) ?? false)
    ) {
      return false;
    }
    return (
      paths === null ||
      paths.some((route) => matchesPath(pathname, route)) ||
      (exact?.includes(pathname) ?? false)
    );
  });
}

/** The product sheet (and anything below /productos) is read by every role that opens /productos. */
export function canOpenProductSheet(value: string | null | undefined): boolean {
  return canAccessPath(value, "/productos/ficha");
}

/**
 * A taller user who is not also admin: sees what to make and how many, never money (lots, product
 * sheet and the cueros pages hide prices, costs and amounts for this role).
 */
export function isTallerOnly(value: string | null | undefined): boolean {
  return hasRole(value, "taller") && !hasRole(value, "admin");
}
