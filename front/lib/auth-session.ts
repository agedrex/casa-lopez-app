import { createHash, timingSafeEqual } from "node:crypto";

type AuthenticatedSession = {
  user?: {
    id?: string;
    role?: string | null;
  } | null;
} | null;

type InternalSessionDependencies = {
  secret: () => string | undefined;
  getSession: (headers: Headers) => Promise<AuthenticatedSession>;
};

function matchesSecret(
  expected: string | undefined,
  authorization: string | null,
) {
  if (!expected || !authorization?.startsWith("Bearer ")) return false;
  const supplied = authorization.slice("Bearer ".length);
  if (!supplied || supplied.includes(" ")) return false;

  const expectedDigest = createHash("sha256").update(expected).digest();
  const suppliedDigest = createHash("sha256").update(supplied).digest();
  return timingSafeEqual(expectedDigest, suppliedDigest);
}

function jsonResponse(body: object, status: number) {
  return Response.json(body, {
    status,
    headers: { "Cache-Control": "private, no-store" },
  });
}

export function createInternalSessionHandler({
  secret,
  getSession,
}: InternalSessionDependencies) {
  return async function handleInternalSession(
    request: Request,
  ): Promise<Response> {
    if (request.method !== "POST")
      return jsonResponse({ error: "unauthorized" }, 401);
    if (!matchesSecret(secret(), request.headers.get("authorization"))) {
      return jsonResponse({ error: "unauthorized" }, 401);
    }

    const sessionHeaders = new Headers();
    const cookie = request.headers.get("cookie");
    if (cookie) sessionHeaders.set("cookie", cookie);

    try {
      const session = await getSession(sessionHeaders);
      const userId = session?.user?.id;
      const role = session?.user?.role;
      if (!userId || !role) return jsonResponse({ error: "unauthorized" }, 401);
      return jsonResponse({ user_id: userId, role }, 200);
    } catch {
      return jsonResponse({ error: "unauthorized" }, 401);
    }
  };
}
