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
  } catch {
    return null;
  }
}

export async function requireAdminSession(headers: Headers) {
  const { getAuth } = await import("@/lib/auth");
  const auth = getAuth();
  return getAdminSession({
    headers,
    getSession: (requestHeaders) =>
      auth.api.getSession({ headers: requestHeaders }),
    hasPermission: async (requestHeaders, permissions) =>
      auth.api.userHasPermission({
        headers: requestHeaders,
        body: { permissions },
      }),
  });
}
