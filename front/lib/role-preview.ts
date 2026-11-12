import { hasRole, ROLES, type Role } from "./permissions";

export const PREVIEW_COOKIE = "preview_role";

/**
 * Staging only: an admin may look at the interface as another role. `RAILWAY_ENVIRONMENT_NAME`
 * is set by Railway; `ROLE_PREVIEW=1` exists to try it locally and is never set in production.
 */
export function previewEnabled(): boolean {
  return (
    process.env.RAILWAY_ENVIRONMENT_NAME === "staging" ||
    process.env.ROLE_PREVIEW === "1"
  );
}

/** A cookie value that names one of the app roles, or null. */
export function parsePreviewRole(
  value: string | null | undefined,
): Role | null {
  return (ROLES as readonly string[]).includes(value ?? "")
    ? (value as Role)
    : null;
}

/**
 * Applies the previewed role to a session. Only a REAL admin, in an environment where the
 * preview is enabled, can change role; anyone else keeps the stored role. This changes what
 * the frontend shows and what its server actions allow: the backend still sees the real user.
 */
export function withPreview<S extends { user: { role?: string | null } }>(
  session: S,
  cookie: string | null | undefined,
) {
  const previewAvailable =
    previewEnabled() && hasRole(session.user.role, "admin");
  const wanted = previewAvailable ? parsePreviewRole(cookie) : null;
  return {
    ...session,
    previewAvailable,
    user: wanted ? { ...session.user, role: wanted } : session.user,
  };
}
