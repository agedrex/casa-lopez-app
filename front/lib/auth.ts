import { betterAuth } from "better-auth";
import {
  APIError,
  createAuthMiddleware,
  getSessionFromCtx,
} from "better-auth/api";
import { nextCookies } from "better-auth/next-js";
import { admin } from "better-auth/plugins";
import { Pool } from "pg";
import { passwordProblem } from "./password";
import { ac, DEFAULT_ROLE, roles } from "./permissions";
import {
  type AccountRow,
  banProblem,
  GUARD_CODE,
  parseRoleInput,
  roleChangeProblem,
} from "./user-guards";

// Better Auth tables (user, session, account, verification) live in the `public`
// schema of the same database the API uses for the `costos` schema. Alembic never
// touches `public`: these tables are created only by `pnpm auth:migrate`.
const globalForPool = globalThis as unknown as { authPool?: Pool };

const pool =
  globalForPool.authPool ??
  new Pool({ connectionString: process.env.DATABASE_URL, max: 5 });

if (process.env.NODE_ENV !== "production") globalForPool.authPool = pool;

/** Every account with the two facts the guards need. Read at the moment of the change, never cached. */
async function accountRows(): Promise<AccountRow[]> {
  const { rows } = await pool.query<{
    id: string;
    role: string | null;
    banned: boolean | null;
    banExpires: Date | null;
  }>('select id, role, banned, "banExpires" from "user"');
  const now = Date.now();
  return rows.map((row) => ({
    id: row.id,
    role: row.role,
    banned:
      row.banned === true &&
      (row.banExpires === null || row.banExpires.getTime() > now),
  }));
}

function refuse(
  message: string,
  status: "FORBIDDEN" | "BAD_REQUEST" = "FORBIDDEN",
): never {
  throw new APIError(status, { message, code: GUARD_CODE });
}

/**
 * Server-side rules of the user list. They live in a Better Auth hook, not only in the
 * screens, so a direct call to /api/auth/admin/* by a signed-in admin hits them too.
 * A call without a session (the seed script) has no actor: only the account rules apply.
 */
const guardUserAdministration = createAuthMiddleware(async (ctx) => {
  const body = (ctx.body ?? {}) as Record<string, unknown>;
  switch (ctx.path) {
    case "/admin/remove-user":
      // Nothing is deleted: a user who leaves is deactivated and their history stays.
      refuse("Los usuarios no se borran: desactívelo.");
      break;
    case "/admin/set-role": {
      const rows = await accountRows();
      const target = rows.find((row) => row.id === body.userId);
      if (!target) return;
      const session = await getSessionFromCtx(ctx);
      const problem = roleChangeProblem({
        actorId: session?.user.id ?? null,
        target,
        newRole: body.role,
        rows,
      });
      if (problem) refuse(problem);
      return;
    }
    case "/admin/ban-user": {
      const rows = await accountRows();
      const target = rows.find((row) => row.id === body.userId);
      if (!target) return;
      const session = await getSessionFromCtx(ctx);
      const problem = banProblem({
        actorId: session?.user.id ?? null,
        target,
        rows,
      });
      if (problem) refuse(problem);
      return;
    }
    case "/admin/create-user": {
      const email = typeof body.email === "string" ? body.email : null;
      const password = typeof body.password === "string" ? body.password : "";
      const problem = passwordProblem(password, { email });
      if (problem) refuse(problem, "BAD_REQUEST");
      const data = (body.data ?? {}) as Record<string, unknown>;
      const requested = body.role ?? data.role;
      if (requested !== undefined && parseRoleInput(requested) === null) {
        refuse("El rol indicado no existe.", "BAD_REQUEST");
      }
      return;
    }
    case "/admin/set-user-password": {
      const target = (await accountEmail(ctx, body.userId)) ?? null;
      const password =
        typeof body.newPassword === "string" ? body.newPassword : "";
      const problem = passwordProblem(password, { email: target });
      if (problem) refuse(problem, "BAD_REQUEST");
      return;
    }
  }
});

async function accountEmail(
  ctx: {
    context: {
      internalAdapter: {
        findUserById: (id: string) => Promise<{ email: string } | null>;
      };
    };
  },
  userId: unknown,
): Promise<string | null> {
  if (typeof userId !== "string") return null;
  return (
    (await ctx.context.internalAdapter.findUserById(userId))?.email ?? null
  );
}

export const auth = betterAuth({
  database: pool,
  secret: process.env.BETTER_AUTH_SECRET,
  baseURL: process.env.BETTER_AUTH_URL,
  emailAndPassword: {
    enabled: true,
    // Users are created by an administrator, never self-registered.
    disableSignUp: true,
  },
  hooks: { before: guardUserAdministration },
  plugins: [
    admin({
      ac,
      roles,
      defaultRole: DEFAULT_ROLE,
      bannedUserMessage:
        "Su usuario está desactivado. Consulte con un administrador.",
    }),
    nextCookies(), // must be the last plugin
  ],
});

export type Session = typeof auth.$Infer.Session;
