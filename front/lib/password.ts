// Strength rules for the passwords an administrator types for other people.
// SUPUESTO: validar. Casa López did not define a password policy; these are conservative defaults.
// Pure text checks, no server-only import (also used by the Better Auth hooks).
export const MIN_PASSWORD_LENGTH = 12;
export const MAX_PASSWORD_LENGTH = 128; // Better Auth's own upper limit

/** A Spanish message when the password is too weak, else null. The password itself is never echoed. */
export function passwordProblem(
  password: string,
  context: { email?: string | null } = {},
): string | null {
  if (password.length < MIN_PASSWORD_LENGTH) {
    return `La contraseña debe tener al menos ${MIN_PASSWORD_LENGTH} caracteres.`;
  }
  if (password.length > MAX_PASSWORD_LENGTH) {
    return `La contraseña no puede superar los ${MAX_PASSWORD_LENGTH} caracteres.`;
  }
  const classes = [/[a-z]/, /[A-Z]/, /\d/, /[^A-Za-z0-9]/].filter((pattern) =>
    pattern.test(password),
  ).length;
  if (classes < 3) {
    return "Combine al menos tres tipos de caracteres: minúsculas, mayúsculas, números y símbolos.";
  }
  if (/^(.)\1+$/.test(password)) return "La contraseña es demasiado simple.";
  const local = context.email?.split("@")[0]?.toLowerCase() ?? "";
  if (local.length >= 3 && password.toLowerCase().includes(local)) {
    return "La contraseña no puede contener el correo del usuario.";
  }
  return null;
}
