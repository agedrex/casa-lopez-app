"use server";

import { cookies, headers } from "next/headers";
import { redirect } from "next/navigation";
import { auth } from "./auth";
import { hasRole, homePath } from "./permissions";
import {
  PREVIEW_COOKIE,
  parsePreviewRole,
  previewEnabled,
} from "./role-preview";

/** Staging only: switch the role the interface is shown as, then go to that role's home. */
export async function setPreviewRole(role: string): Promise<void> {
  const session = await auth.api.getSession({ headers: await headers() });
  if (!session) redirect("/login");
  const wanted = parsePreviewRole(role);
  // Checked against the stored role: a previewed gerente must not be able to switch again by posting here.
  if (!previewEnabled() || !hasRole(session.user.role, "admin") || !wanted) {
    return;
  }
  (await cookies()).set(PREVIEW_COOKIE, wanted, {
    path: "/",
    httpOnly: true,
    sameSite: "lax",
    secure: process.env.NODE_ENV === "production",
  });
  redirect(homePath(wanted));
}

/** Called on sign out so the next admin on this browser does not start in someone else's preview. */
export async function clearPreviewRole(): Promise<void> {
  (await cookies()).delete(PREVIEW_COOKIE);
}
