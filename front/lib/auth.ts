import { betterAuth } from "better-auth";
import { admin as adminPlugin } from "better-auth/plugins";
import { PostgresDialect } from "kysely";
import { Pool } from "pg";
import {
  adminAccessControl,
  adminRole,
  userRole,
} from "@/lib/auth-permissions";

function createAuth() {
  const databaseUrl = process.env.AUTH_DATABASE_URL;
  const baseURL = process.env.BETTER_AUTH_URL;
  const secret = process.env.BETTER_AUTH_SECRET;

  if (!databaseUrl || !baseURL || !secret) {
    throw new Error("Better Auth server configuration is incomplete");
  }

  return betterAuth({
    baseURL,
    secret,
    database: {
      dialect: new PostgresDialect({
        pool: new Pool({ connectionString: databaseUrl }),
      }),
      type: "postgres",
      schemaName: "public",
    },
    emailAndPassword: {
      enabled: true,
      disableSignUp: true,
    },
    plugins: [
      adminPlugin({
        ac: adminAccessControl,
        roles: {
          admin: adminRole,
          user: userRole,
        },
        adminRoles: ["admin"],
        defaultRole: "user",
      }),
    ],
  });
}

let authInstance: ReturnType<typeof createAuth> | undefined;

export function getAuth() {
  authInstance ??= createAuth();
  return authInstance;
}
