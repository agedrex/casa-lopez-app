import { isAPIError } from "better-auth/api";

export const ADMIN_PERMISSION: { application: ["admin"] } = {
  application: ["admin"],
};

type Session = {
  user?: { id?: string; role?: string | null; email?: string } | null;
} | null;

type AdminAuthDependencies = {
  headers: Headers;
  getSession: (headers: Headers) => Promise<Session>;
  hasPermission: (
    headers: Headers,
    permissions: typeof ADMIN_PERMISSION,
  ) => Promise<{ success?: boolean } | null>;
};

export async function hasAdminSession(dependencies: AdminAuthDependencies) {
  return (await getAdminSession(dependencies)) !== null;
}

export async function getAdminSession({
  headers,
  getSession,
  hasPermission,
}: AdminAuthDependencies) {
  try {
    const session = await getSession(headers);
    if (!session?.user?.id || session.user.role !== "admin") return null;
    const permission = await hasPermission(headers, ADMIN_PERMISSION);
    return permission?.success === true ? session : null;
  } catch (error) {
    if (isAPIError(error) && [401, 403].includes(error.statusCode)) return null;
    throw new Error("Authentication service unavailable.");
  }
}

export async function requireAdminSession(headers: Headers) {
  const { getAuth } = await import("@/lib/auth");
  return getAdminSession({
    headers,
    getSession: (requestHeaders) =>
      getAuth().api.getSession({ headers: requestHeaders }),
    hasPermission: async (requestHeaders, permissions) =>
      getAuth().api.userHasPermission({
        headers: requestHeaders,
        body: { permissions },
      }),
  });
}
