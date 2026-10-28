import { createAccessControl } from "better-auth/plugins/access";
import { adminAc, defaultStatements } from "better-auth/plugins/admin/access";

export const ROLES = ["admin", "cotizador", "consulta"] as const;
export type Role = (typeof ROLES)[number];

export const DEFAULT_ROLE: Role = "consulta";

export const ROLE_LABELS: Record<Role, string> = {
  admin: "Administrador",
  cotizador: "Cotizador",
  consulta: "Consulta",
};

const ac = createAccessControl(defaultStatements);

// Only `admin` manages users (Better Auth admin plugin statements).
// `cotizador` and `consulta` carry no user-management permission; what they may
// do inside the costing modules is decided by the modules themselves.
export const roles = {
  admin: ac.newRole({ ...adminAc.statements }),
  cotizador: ac.newRole({}),
  consulta: ac.newRole({}),
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
