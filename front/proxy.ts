import { getSessionCookie } from "better-auth/cookies";
import { type NextRequest, NextResponse } from "next/server";
import { auth } from "./lib/auth";
import { hasRole } from "./lib/permissions";

// Optimistic gate: a missing session cookie sends the visitor to /login. The real
// authorization happens close to the data (pages and the API verifier); only /admin
// is validated against the database here because its role decides access.
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

  if (pathname === "/admin" || pathname.startsWith("/admin/")) {
    const session = await auth.api.getSession({ headers: request.headers });
    if (!session) return NextResponse.redirect(new URL("/login", request.url));
    if (!hasRole(session.user.role, "admin")) {
      return NextResponse.redirect(new URL("/", request.url));
    }
  }

  return NextResponse.next();
}

export const config = {
  matcher: ["/((?!_next/static|_next/image|favicon.ico).*)"],
};
