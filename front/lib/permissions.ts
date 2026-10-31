import { createAccessControl } from "better-auth/plugins/access";
import { defaultStatements } from "better-auth/plugins/admin/access";

export const ROLES = ["admin", "cotizador", "consulta", "corte"] as const;
export type Role = (typeof ROLES)[number];

export const DEFAULT_ROLE: Role = "consulta";

export const ROLE_LABELS: Record<Role, string> = {
  admin: "Administrador",
  cotizador: "Cotizador",
  consulta: "Gerente",
  corte: "Corte",
};

const ac = createAccessControl(defaultStatements);

// Only `admin` manages users (Better Auth admin plugin statements). `cotizador` and
// `consulta` and `corte` carry no user-management permission; modules decide
// what these roles may do inside the app.
// Nothing is deleted from the app: the admin role does not get `delete` (remove-user),
// `update` (admin update-user could change a role or a ban around the guards in auth.ts),
// `set-email`, nor impersonation, so those endpoints answer 403 even to an admin.
export const roles = {
  admin: ac.newRole({
    user: ["create", "list", "get", "set-role", "ban", "set-password"],
    session: ["list", "revoke"],
  }),
  cotizador: ac.newRole({}),
  consulta: ac.newRole({}),
  corte: ac.newRole({}),
};

export { ac };

/** Better Auth stores several roles as a comma separated string. */
export function parseRoles(value: string | null | undefined): Role[] {
  if (!value) return [];
  return value
    .split(",")
    .map((role) => role.trim())
    .filter((role): role is Role =>
      (ROLES as readonly string[]).includes(role),
    );
}

export function hasRole(value: string | null | undefined, role: Role): boolean {
  return parseRoles(value).includes(role);
}

// Mirrors the backend: only these roles may write (every POST needs one of them).
// The UI hides the forms from everybody else; the backend still answers 403.
export const WRITE_ROLES: readonly Role[] = ["admin", "cotizador"];

export function canWrite(value: string | null | undefined): boolean {
  return parseRoles(value).some((role) => WRITE_ROLES.includes(role));
}

export function isCorteOnly(value: string | null | undefined): boolean {
  return hasRole(value, "corte") && !canWrite(value);
}

export function isCortePath(pathname: string): boolean {
  return ["/corte", "/cueros", "/voz"].some(
    (route) => pathname === route || pathname.startsWith(`${route}/`),
  );
}
