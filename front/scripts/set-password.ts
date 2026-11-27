/**
 * Resets the password of an existing user, for the case where nobody can reach
 * `/admin/usuarios` any more (the only admin forgot their password): this project has no
 * password-reset-by-email flow.
 *
 * It does NOT call `auth.api.setUserPassword`: that endpoint sits behind the admin
 * plugin's `adminMiddleware`, which throws UNAUTHORIZED whenever there is no session,
 * with no server-side exception (better-auth/dist/plugins/admin/routes.mjs:17-21, :807).
 * `scripts/seed-user.ts` works only because `/admin/create-user` has an explicit escape
 * for callers with no request and no headers (routes.mjs:154); set-user-password has none.
 *
 * So it performs exactly what that endpoint does internally (routes.mjs:829-839), through
 * Better Auth's own context: the hash comes from `context.password.hash`, so a normal
 * sign-in verifies it the same way. Old sessions are deleted, as the admin screen does.
 *
 * Because the endpoint is bypassed, the `before` hook in lib/auth.ts does NOT run, which
 * makes `passwordProblem` here the only strength validation. It must stay.
 *
 * Dry-run by default: it only reports whether the user exists. Writing needs both
 * `--entorno` (staging or production) and `--confirmar`, like `importar_productos.py`.
 * `--entorno` must equal RAILWAY_ENVIRONMENT_NAME, and `--entorno production` needs the
 * production environment injected.
 *
 * The password is read only from NEW_USER_PASSWORD, never from an argument, and is never
 * printed. Type it so it stays out of the shell history and the process list:
 *
 *     read -rs NEW_USER_PASSWORD && export NEW_USER_PASSWORD
 *
 * Dry-run (no password needed):
 *     pnpm set:password -- --email alguien@ejemplo.com
 *
 * Write:
 *     pnpm set:password -- --email alguien@ejemplo.com --entorno production --confirmar
 *
 * Both need DATABASE_URL and BETTER_AUTH_SECRET in the environment.
 */
import { auth } from "../lib/auth";
import { passwordProblem } from "../lib/password";
import {
  environmentProblem,
  isEntorno,
  parseArgs,
} from "../lib/set-password-guards";

function reject(message: string): number {
  console.error(message);
  return 1;
}

/** Only the host, never the credentials inside DATABASE_URL. */
function databaseHost(): string {
  try {
    return new URL(process.env.DATABASE_URL ?? "").host || "host desconocido";
  } catch {
    return "host desconocido";
  }
}

async function main(argv: string[]): Promise<number> {
  const options = parseArgs(argv);
  if (!options.email) {
    return reject("Falta --email: indicá el correo del usuario a resetear.");
  }
  if (!process.env.DATABASE_URL) return reject("Falta DATABASE_URL.");
  if (!process.env.BETTER_AUTH_SECRET) {
    return reject("Falta BETTER_AUTH_SECRET: sin el secreto el hash no sirve.");
  }

  const write = options.entorno !== null || options.confirmar;
  let password = "";
  if (write) {
    if (!isEntorno(options.entorno) || !options.confirmar) {
      return reject(
        "No se cambió nada: para escribir hacen falta los dos avisos juntos, --entorno (staging o production) y --confirmar. " +
          "Sin ellos el script solo informa si el usuario existe.",
      );
    }
    const problem = environmentProblem(
      options.entorno,
      process.env.RAILWAY_ENVIRONMENT_NAME,
    );
    if (problem) return reject(problem);

    password = process.env.NEW_USER_PASSWORD ?? "";
    if (!password) {
      return reject(
        "Falta NEW_USER_PASSWORD: la contraseña se pasa solo por variable de entorno, nunca como argumento.",
      );
    }
    // The endpoint is bypassed, so the `before` hook of lib/auth.ts does not run:
    // this is the only strength check. The password itself is never echoed.
    const weak = passwordProblem(password, { email: options.email });
    if (weak) return reject(weak);
  }

  console.log(`Base de datos: ${databaseHost()}`);
  const context = await auth.$context;
  const found = await context.internalAdapter.findUserByEmail(options.email);
  if (!found) {
    return reject(`No existe un usuario con el correo ${options.email}.`);
  }
  const user = found.user;
  // `role` is added by the admin plugin and is not in the base User type, so it is read
  // defensively: it is only shown to confirm the right account, never used to decide.
  const role = (user as { role?: unknown }).role;
  console.log(
    `Usuario encontrado: ${options.email} (rol ${typeof role === "string" ? role : "sin rol"}).`,
  );

  if (!write) {
    console.log(
      "Dry-run: no se cambió nada. Para cambiar la contraseña agregá --entorno y --confirmar.",
    );
    return 0;
  }

  // Same steps as /admin/set-user-password (routes.mjs:829-839).
  const hashed = await context.password.hash(password);
  if (await context.internalAdapter.findCredentialAccount(user.id)) {
    await context.internalAdapter.updatePassword(user.id, hashed);
    console.log("Contraseña cambiada.");
  } else {
    // No credential account yet (e.g. the user only ever signed in with a provider).
    await context.internalAdapter.createAccount({
      userId: user.id,
      providerId: "credential",
      accountId: user.id,
      password: hashed,
    });
    console.log("Contraseña creada (el usuario no tenía una).");
  }

  // Changing the password leaves the old sessions alive, so they are closed here,
  // exactly as app/(app)/admin/usuarios/actions.ts does after setPassword.
  await context.internalAdapter.deleteUserSessions(user.id);
  console.log("Sesiones abiertas cerradas.");
  return 0;
}

main(process.argv.slice(2))
  .then((code) => process.exit(code))
  .catch((error: unknown) => {
    // Only the message: a failure must not spill the password or the database URL.
    console.error(
      "Falló el cambio de contraseña:",
      error instanceof Error ? error.message : "error desconocido",
    );
    process.exit(1);
  });
