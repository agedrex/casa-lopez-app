import "server-only";
import { isAPIError } from "better-auth/api";
import { headers } from "next/headers";
import { error, type FormState } from "./action-state";
import { auth } from "./auth";
import { parseRoles, type Role } from "./permissions";
import { GUARD_CODE } from "./user-guards";

export type AdminUser = {
  id: string;
  email: string;
  name: string;
  /** First valid role, or null when the stored value is not one of ours. */
  role: Role | null;
  banned: boolean;
  createdAt: string;
};

export type UsersResult =
  | { ok: true; users: AdminUser[] }
  | { ok: false; message: string };

// The team is a handful of people; one page is plenty.
const USER_LIMIT = 200;

export async function listAdminUsers(): Promise<UsersResult> {
  try {
    const result = await auth.api.listUsers({
      query: { limit: USER_LIMIT, sortBy: "createdAt", sortDirection: "asc" },
      headers: await headers(),
    });
    return {
      ok: true,
      users: result.users.map((user) => ({
        id: user.id,
        email: user.email,
        name: user.name,
        role: parseRoles(user.role)[0] ?? null,
        banned: user.banned === true,
        createdAt: new Date(user.createdAt).toISOString(),
      })),
    };
  } catch (failure) {
    return { ok: false, message: describeFailure(failure).message ?? "" };
  }
}

const KNOWN: Record<string, string> = {
  USER_ALREADY_EXISTS: "Ya existe un usuario con ese correo.",
  USER_ALREADY_EXISTS_USE_ANOTHER_EMAIL: "Ya existe un usuario con ese correo.",
  INVALID_EMAIL: "El correo no es válido.",
  USER_NOT_FOUND: "No se encontró el usuario.",
  YOU_CANNOT_BAN_YOURSELF: "No puede desactivar su propio usuario.",
};

/**
 * Turns whatever Better Auth threw into form feedback. Messages of our own guards are
 * already in Spanish and pass through; the library's English ones are replaced, and
 * nothing else (no request body, no password) is ever echoed or logged.
 */
export function describeFailure(failure: unknown): FormState {
  if (isAPIError(failure)) {
    const body = failure.body as
      | { code?: string; message?: string }
      | undefined;
    if (body?.code === GUARD_CODE && body.message) return error(body.message);
    if (body?.code && KNOWN[body.code]) return error(KNOWN[body.code]);
    if (failure.statusCode === 403) {
      return error("No tiene permiso para esta acción.");
    }
  }
  return error("No se pudo completar la acción. Intente de nuevo.");
}

// Two administrators acting at once could each pass the "someone else stays admin" check
// and leave none. Within one server process the role and ban changes run one at a time.
let queue: Promise<unknown> = Promise.resolve();

export function serialized<T>(task: () => Promise<T>): Promise<T> {
  const run = queue.then(task, task);
  queue = run.catch(() => undefined);
  return run;
}
