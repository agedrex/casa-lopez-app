"use client";

import { createAuthClient } from "better-auth/react";

export const authClient = createAuthClient();

export function getSafeRedirectPath(candidate: string | undefined) {
  return candidate === "/admin" ? candidate : "/admin";
}

type EmailSignIn = {
  email: (input: {
    email: string;
    password: string;
    callbackURL: string;
  }) => Promise<{ error?: unknown | null }>;
};

export async function submitLogin(
  signIn: EmailSignIn,
  input: { email: string; password: string; callbackURL: string },
): Promise<{ ok: true } | { ok: false; reason: "credentials" | "network" }> {
  try {
    const result = await signIn.email(input);
    return result.error ? { ok: false, reason: "credentials" } : { ok: true };
  } catch {
    return { ok: false, reason: "network" };
  }
}

export async function submitLogout(
  signOut: () => Promise<{ error?: unknown | null }>,
) {
  try {
    const result = await signOut();
    return !result.error;
  } catch {
    return false;
  }
}
