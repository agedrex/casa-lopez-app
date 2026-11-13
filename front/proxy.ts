import { getSessionCookie } from "better-auth/cookies";
import { type NextRequest, NextResponse } from "next/server";
import { auth } from "./lib/auth";
import { canAccessPath, homePath } from "./lib/permissions";
import { PREVIEW_COOKIE, withPreview } from "./lib/role-preview";

// Optimistic gate: a missing session cookie sends the visitor to /login. The real
// authorization happens close to the data (pages and the API verifier).
export async function proxy(request: NextRequest) {
  const { pathname, search } = request.nextUrl;

  if (pathname === "/login" || pathname.startsWith("/api/auth/")) {
    return NextResponse.next();
  }

  if (!getSessionCookie(request)) {
    const login = new URL("/login", request.url);
    login.searchParams.set("next", `${pathname}${search}`);
    return NextResponse.redirect(login);
  }

  const real = await auth.api.getSession({ headers: request.headers });
  if (!real) return NextResponse.redirect(new URL("/login", request.url));
  const session = withPreview(real, request.cookies.get(PREVIEW_COOKIE)?.value);
  // Deny by default: each role opens only its own paths (/admin is admin only).
  if (!canAccessPath(session.user.role, pathname)) {
    return NextResponse.redirect(
      new URL(homePath(session.user.role), request.url),
    );
  }

  const headers = new Headers(request.headers);
  headers.set("x-app-pathname", pathname);
  return NextResponse.next({ request: { headers } });
}

export const config = {
  matcher: ["/((?!_next/static|_next/image|favicon.ico).*)"],
};
