import { betterAuth } from "better-auth";
import { nextCookies } from "better-auth/next-js";
import { admin } from "better-auth/plugins";
import { Pool } from "pg";
import { ac, DEFAULT_ROLE, roles } from "./permissions";

// Better Auth tables (user, session, account, verification) live in the `public`
// schema of the same database the API uses for the `costos` schema. Alembic never
// touches `public`: these tables are created only by `pnpm auth:migrate`.
const globalForPool = globalThis as unknown as { authPool?: Pool };

const pool =
  globalForPool.authPool ??
  new Pool({ connectionString: process.env.DATABASE_URL, max: 5 });

if (process.env.NODE_ENV !== "production") globalForPool.authPool = pool;

export const auth = betterAuth({
  database: pool,
  secret: process.env.BETTER_AUTH_SECRET,
  baseURL: process.env.BETTER_AUTH_URL,
  emailAndPassword: {
    enabled: true,
    // Users are created by an administrator, never self-registered.
    disableSignUp: true,
  },
  plugins: [
    admin({ ac, roles, defaultRole: DEFAULT_ROLE }),
    nextCookies(), // must be the last plugin
  ],
});

export type Session = typeof auth.$Infer.Session;
