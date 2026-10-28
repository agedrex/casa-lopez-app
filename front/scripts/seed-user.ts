/**
 * Creates the test user (admin) through Better Auth's own admin API, so the password
 * is hashed exactly as a normal sign-in expects. Idempotent: an existing user is left
 * untouched. The password comes only from SEED_USER_PASSWORD and is never printed.
 *
 * Usage: SEED_USER_PASSWORD=... pnpm seed:user   (DATABASE_URL and BETTER_AUTH_SECRET too)
 */
import { auth } from "../lib/auth";

const EMAIL = "contacto@agedrex.com";
const NAME = "Usuario de prueba";
const ROLE = "admin";

function databaseHost(): string {
  try {
    return new URL(process.env.DATABASE_URL ?? "").host || "unknown host";
  } catch {
    return "unknown host";
  }
}

async function main(): Promise<number> {
  const password = process.env.SEED_USER_PASSWORD;
  if (!password) {
    console.error(
      "SEED_USER_PASSWORD is required. Set it in the environment and run again.",
    );
    return 1;
  }
  if (!process.env.DATABASE_URL) {
    console.error("DATABASE_URL is required.");
    return 1;
  }

  console.log(`Seeding ${EMAIL} on database host ${databaseHost()}`);
  const context = await auth.$context;
  const existing = await context.internalAdapter.findUserByEmail(EMAIL);
  if (existing) {
    console.log("The user already exists; nothing to do.");
    return 0;
  }

  // No headers or request: a server-side call is trusted by the admin plugin.
  await auth.api.createUser({
    body: { email: EMAIL, password, name: NAME, role: ROLE },
  });
  console.log(`Created ${EMAIL} with role ${ROLE}.`);
  return 0;
}

main()
  .then((code) => process.exit(code))
  .catch((error: unknown) => {
    console.error(
      "Seeding failed:",
      error instanceof Error ? error.message : "unknown error",
    );
    process.exit(1);
  });
