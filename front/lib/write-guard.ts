import "server-only";
import { redirect } from "next/navigation";
import { error, type FormState } from "./action-state";
import type { ApiFailure } from "./api";
import { canWrite, hasRole } from "./permissions";
import { getSession } from "./session";

/**
 * Every write action starts here: the form is only rendered for admin and cotizador,
 * but the action must check again because anyone can post to it. The backend checks
 * the role a third time (403).
 */
export async function denyUnlessWriter(): Promise<FormState | null> {
  const session = await getSession();
  if (!session) redirect("/login");
  if (!canWrite(session.user.role)) {
    return error("No tiene permiso para esta acción.");
  }
  return null;
}

export type AdminCheck =
  | { denied: FormState }
  | { denied: null; userId: string };

/**
 * Every action of the admin area starts here. The proxy already keeps non-admins out of
 * /admin, but anyone can post to a server action, so the role is checked again; the
 * backend (and Better Auth for the user list) check it a third time.
 */
export async function denyUnlessAdmin(): Promise<AdminCheck> {
  const session = await getSession();
  if (!session) redirect("/login");
  if (!hasRole(session.user.role, "admin")) {
    return { denied: error("No tiene permiso para esta acción.") };
  }
  return { denied: null, userId: session.user.id };
}

export function text(formData: FormData, key: string): string {
  const value = formData.get(key);
  return typeof value === "string" ? value.trim() : "";
}

/** Empty text is "not given": the API takes null for optional fields. */
export function optional(formData: FormData, key: string): string | null {
  return text(formData, key) || null;
}

/** Turns an API failure into form feedback, with friendlier text for known statuses. */
export function fromFailure(
  failure: ApiFailure,
  byStatus: Partial<Record<number, string>> = {},
): FormState {
  return error(byStatus[failure.status] ?? failure.message, failure.avisos);
}
