// Pure rules that keep the user list safe. They run inside Better Auth (hooks.before in
// auth.ts), so they cover the server actions and also a direct call to /api/auth/admin/*.
// No server-only import: auth.ts is also loaded by scripts run with tsx.
import { isStoredAdmin, ROLES, type Role } from "./permissions";

export type AccountRow = {
  id: string;
  role: string | null;
  banned: boolean;
};

/** Error code of the APIError thrown by the guards, so the screens can tell it from the library's own English ones. */
export const GUARD_CODE = "CASA_LOPEZ_GUARD";

export const LAST_ADMIN =
  "Debe quedar al menos un administrador activo: no se puede quitar el rol ni desactivar al último.";

export function activeAdmins(rows: AccountRow[]): AccountRow[] {
  return rows.filter((row) => !row.banned && isStoredAdmin(row.role));
}

/** `role` arrives as a string or a list of strings; anything that is not one of ROLES is refused. */
export function parseRoleInput(input: unknown): Role[] | null {
  const items = Array.isArray(input) ? input : [input];
  if (items.length === 0) return null;
  const valid = items.filter((item): item is Role =>
    (ROLES as readonly string[]).includes(item as string),
  );
  return valid.length === items.length ? valid : null;
}

/** A message when the role change must be refused, else null. */
export function roleChangeProblem(args: {
  actorId: string | null;
  target: AccountRow;
  newRole: unknown;
  rows: AccountRow[];
}): string | null {
  const roles = parseRoleInput(args.newRole);
  if (roles === null) return "El rol indicado no existe.";
  const losesAdmin =
    isStoredAdmin(args.target.role) && !roles.includes("admin");
  if (!losesAdmin) return null;
  if (args.actorId !== null && args.actorId === args.target.id) {
    return "No puede quitarse a sí mismo el rol de administrador.";
  }
  const stillActive = activeAdmins(args.rows).filter(
    (row) => row.id !== args.target.id,
  );
  return !args.target.banned && stillActive.length === 0 ? LAST_ADMIN : null;
}

/** A message when the deactivation must be refused, else null. */
export function banProblem(args: {
  actorId: string | null;
  target: AccountRow;
  rows: AccountRow[];
}): string | null {
  if (args.actorId !== null && args.actorId === args.target.id) {
    return "No puede desactivar su propio usuario.";
  }
  const stillActive = activeAdmins(args.rows).filter(
    (row) => row.id !== args.target.id,
  );
  const isActiveAdmin = !args.target.banned && isStoredAdmin(args.target.role);
  return isActiveAdmin && stillActive.length === 0 ? LAST_ADMIN : null;
}

/** Reason stored when a user is "deleted": the account is banned and hidden, never removed. */
export const ARCHIVED_REASON = "ARCHIVADO";

/** A message when an update touches anything besides name and email, else null. Role and ban have their own guarded routes. */
export function profileUpdateProblem(data: unknown): string | null {
  if (typeof data !== "object" || data === null) return "Datos inválidos.";
  const extra = Object.keys(data).filter(
    (key) => key !== "name" && key !== "email",
  );
  return extra.length > 0
    ? "Solo se pueden cambiar el nombre y el correo."
    : null;
}
