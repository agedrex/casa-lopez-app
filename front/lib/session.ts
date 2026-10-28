import "server-only";
import { headers } from "next/headers";
import { redirect } from "next/navigation";
import { auth } from "./auth";
import { hasRole, type Role } from "./permissions";

/** Reads the session from the incoming request cookies (request-time data). */
export async function getSession() {
  return auth.api.getSession({ headers: await headers() });
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
