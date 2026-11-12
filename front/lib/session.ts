import "server-only";
import { cookies, headers } from "next/headers";
import { redirect } from "next/navigation";
import { auth } from "./auth";
import { hasRole, type Role } from "./permissions";
import { PREVIEW_COOKIE, withPreview } from "./role-preview";

/**
 * Reads the session from the incoming request cookies (request-time data). On staging an admin
 * may be previewing another role (see role-preview.ts): `user.role` is then the previewed one.
 */
export async function getSession() {
  const session = await auth.api.getSession({ headers: await headers() });
  if (!session) return null;
  return withPreview(session, (await cookies()).get(PREVIEW_COOKIE)?.value);
}

/** Authoritative check close to the data; the proxy only does an optimistic one. */
export async function requireSession() {
  const session = await getSession();
  if (!session) redirect("/login");
  return session;
}

export async function requireRole(role: Role) {
  const session = await requireSession();
  if (!hasRole(session.user.role, role)) redirect("/");
  return session;
}
