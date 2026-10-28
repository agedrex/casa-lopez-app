"use server";

import { refresh } from "next/cache";
import { headers } from "next/headers";
import { redirect } from "next/navigation";
import { error, type FormState, ok } from "@/lib/action-state";
import { describeFailure, serialized } from "@/lib/admin-users";
import { auth } from "@/lib/auth";
import { passwordProblem } from "@/lib/password";
import { ROLES } from "@/lib/permissions";
import { denyUnlessAdmin, text } from "@/lib/write-guard";

// Passwords travel only inside these actions: they are read from the form, handed to
// Better Auth and dropped. They are never returned, logged or put in a message.
const EMAIL = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

function chosenRole(formData: FormData): (typeof ROLES)[number] | null {
  const role = text(formData, "role");
  return ROLES.find((candidate) => candidate === role) ?? null;
}

function passwordFrom(formData: FormData): string | FormState {
  // Not trimmed: spaces may be part of the password.
  const password = formData.get("password");
  const confirm = formData.get("confirm");
  if (typeof password !== "string" || password === "") {
    return error("Escriba la contraseña inicial.");
  }
  if (password !== confirm) return error("Las contraseñas no coinciden.");
  return password;
}

export async function createUser(
  _previous: FormState,
  formData: FormData,
): Promise<FormState> {
  const check = await denyUnlessAdmin();
  if (check.denied) return check.denied;

  const email = text(formData, "email").toLowerCase();
  const name = text(formData, "name");
  const role = chosenRole(formData);
  if (!EMAIL.test(email)) return error("Indique un correo válido.");
  if (!name || name.length > 120)
    return error("Indique el nombre (hasta 120 letras).");
  if (!role) return error("Elija el rol.");
  const password = passwordFrom(formData);
  if (typeof password !== "string") return password;
  const weak = passwordProblem(password, { email });
  if (weak) return error(weak);

  try {
    await auth.api.createUser({
      body: { email, name, role, password },
      headers: await headers(),
    });
  } catch (failure) {
    return describeFailure(failure);
  }
  refresh();
  return ok(
    `Usuario ${email} creado. Pásele la contraseña por un canal seguro.`,
  );
}

export async function changeRole(
  userId: string,
  _previous: FormState,
  formData: FormData,
): Promise<FormState> {
  const check = await denyUnlessAdmin();
  if (check.denied) return check.denied;
  const role = chosenRole(formData);
  if (!role) return error("Elija el rol.");

  try {
    // The guards (not oneself, never the last active admin) run inside Better Auth.
    await serialized(async () =>
      auth.api.setRole({ body: { userId, role }, headers: await headers() }),
    );
  } catch (failure) {
    return describeFailure(failure);
  }
  refresh();
  return ok("Rol actualizado.");
}

/** Deactivating bans the user (their sessions end); nothing is deleted. */
export async function setBanned(
  userId: string,
  banned: boolean,
  _previous: FormState,
  _formData: FormData,
): Promise<FormState> {
  const check = await denyUnlessAdmin();
  if (check.denied) return check.denied;

  try {
    await serialized(async () => {
      const requestHeaders = await headers();
      if (banned) {
        await auth.api.banUser({
          body: { userId, banReason: "Desactivado por un administrador" },
          headers: requestHeaders,
        });
      } else {
        await auth.api.unbanUser({ body: { userId }, headers: requestHeaders });
      }
    });
  } catch (failure) {
    return describeFailure(failure);
  }
  refresh();
  return ok(banned ? "Usuario desactivado." : "Usuario activado.");
}

export async function setPassword(
  userId: string,
  _previous: FormState,
  formData: FormData,
): Promise<FormState> {
  const check = await denyUnlessAdmin();
  if (check.denied) return check.denied;

  const password = passwordFrom(formData);
  if (typeof password !== "string") return password;
  const weak = passwordProblem(password);
  if (weak) return error(weak);

  const requestHeaders = await headers();
  try {
    await auth.api.setUserPassword({
      body: { userId, newPassword: password },
      headers: requestHeaders,
    });
  } catch (failure) {
    return describeFailure(failure);
  }
  // Better Auth's set-user-password keeps the old sessions alive, so they are closed here.
  try {
    await auth.api.revokeUserSessions({
      body: { userId },
      headers: requestHeaders,
    });
  } catch {
    return error(
      "La contraseña se cambió, pero no se pudieron cerrar las sesiones abiertas. Desactive y vuelva a activar al usuario.",
    );
  }
  // Changing one's own password ends one's own session too.
  if (userId === check.userId) redirect("/login");
  refresh();
  return ok("Contraseña cambiada y sesiones cerradas.");
}
