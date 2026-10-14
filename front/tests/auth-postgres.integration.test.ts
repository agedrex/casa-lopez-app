import assert from "node:assert/strict";
import { randomBytes } from "node:crypto";
// @ts-expect-error Node 22 provides this runtime hook, while the project pins Node 20 type declarations.
import { registerHooks } from "node:module";
import { resolve } from "node:path";
import test from "node:test";
import { fileURLToPath, pathToFileURL } from "node:url";
import { Pool } from "pg";

const frontendRoot = new URL("../", import.meta.url);
registerHooks({
  resolve(
    specifier: string,
    context: unknown,
    nextResolve: (specifier: string, context: unknown) => { url: string },
  ) {
    if (specifier.startsWith("@/")) {
      const modulePath = resolve(
        fileURLToPath(frontendRoot),
        `${specifier.slice(2)}.ts`,
      );
      return nextResolve(pathToFileURL(modulePath).href, context);
    }
    return nextResolve(specifier, context);
  },
});

// @ts-expect-error Node's native type stripping resolves this TypeScript entry point.
const { getAuth } = await import("../lib/auth.ts");

const databaseUrl = process.env.AUTH_DATABASE_URL;
assert.ok(databaseUrl, "AUTH_DATABASE_URL is required for the PostgreSQL test");

const auth = getAuth();
const pool = new Pool({ connectionString: databaseUrl });
const baseURL = process.env.BETTER_AUTH_URL;
assert.ok(baseURL, "BETTER_AUTH_URL is required for the PostgreSQL test");

const unique = randomBytes(12).toString("hex");
const adminEmail = `wo7-admin-${unique}@example.test`;
const userEmail = `wo7-user-${unique}@example.test`;
const password = randomBytes(32).toString("base64url");

function endpoint(path: string) {
  return new URL(`/api/auth/${path}`, baseURL);
}

async function request(path: string, body?: unknown, cookie?: string) {
  return auth.handler(
    new Request(endpoint(path), {
      method: body === undefined ? "GET" : "POST",
      headers: {
        ...(body === undefined ? {} : { "content-type": "application/json" }),
        ...(cookie ? { cookie } : {}),
      },
      ...(body === undefined ? {} : { body: JSON.stringify(body) }),
    }),
  );
}

function cookieFrom(response: Response) {
  return response.headers
    .getSetCookie()
    .map((value) => value.split(";", 1)[0])
    .join("; ");
}

test("Better Auth persists identities and enforces configured access", async (t) => {
  t.after(async () => {
    await pool.end();
  });

  const adminResult = await auth.api.createUser({
    body: {
      name: "WO-7 temporary administrator",
      email: adminEmail,
      password,
      role: "admin",
    },
  });
  const userResult = await auth.api.createUser({
    body: {
      name: "WO-7 temporary user",
      email: userEmail,
      password,
      role: "user",
    },
  });
  const admin = adminResult.user;
  const user = userResult.user;

  assert.equal(admin.role, "admin");
  assert.equal(user.role, "user");

  const signUp = await request("sign-up/email", {
    name: "Browser-created user",
    email: `wo7-signup-${unique}@example.test`,
    password,
  });
  assert.ok(signUp.status === 400 || signUp.status === 403);

  const adminLogin = await request("sign-in/email", {
    email: adminEmail,
    password,
  });
  assert.equal(adminLogin.status, 200);
  const adminCookie = cookieFrom(adminLogin);
  assert.notEqual(adminCookie, "");

  const adminSession = await request("get-session", undefined, adminCookie);
  assert.equal(adminSession.status, 200);
  const sessionBody = (await adminSession.json()) as {
    user?: { id?: string; role?: string };
    session?: { id?: string };
  };
  assert.equal(sessionBody.user?.id, admin.id);
  assert.equal(sessionBody.user?.role, "admin");
  assert.ok(sessionBody.session?.id);

  const persisted = await pool.query<{
    user_count: string;
    account_count: string;
    session_count: string;
  }>(
    `SELECT
       (SELECT count(*) FROM public."user" WHERE id = $1) AS user_count,
       (SELECT count(*) FROM public.account WHERE "userId" = $1) AS account_count,
       (SELECT count(*) FROM public.session WHERE "userId" = $1) AS session_count`,
    [admin.id],
  );
  assert.deepEqual(persisted.rows[0], {
    user_count: "1",
    account_count: "1",
    session_count: "1",
  });

  const adminPermission = await auth.api.userHasPermission({
    body: { userId: admin.id, permissions: { application: ["admin"] } },
    headers: new Headers({ cookie: adminCookie }),
  });
  assert.equal(adminPermission.success, true);

  const userLogin = await request("sign-in/email", {
    email: userEmail,
    password,
  });
  assert.equal(userLogin.status, 200);
  const userCookie = cookieFrom(userLogin);
  assert.notEqual(userCookie, "");

  const userPermission = await auth.api.userHasPermission({
    body: { userId: user.id, permissions: { application: ["admin"] } },
    headers: new Headers({ cookie: userCookie }),
  });
  assert.equal(userPermission.success, false);

  const roleAssignment = await request(
    "admin/set-role",
    { userId: user.id, role: "admin" },
    userCookie,
  );
  assert.ok(roleAssignment.status === 401 || roleAssignment.status === 403);
  const userCreation = await request(
    "admin/create-user",
    {
      name: "Browser-created user",
      email: `wo7-admin-api-${unique}@example.test`,
      password,
    },
    adminCookie,
  );
  assert.ok(userCreation.status === 401 || userCreation.status === 403);

  const logout = await request("sign-out", {}, adminCookie);
  assert.equal(logout.status, 200);
  const loggedOutSession = await request("get-session", undefined, adminCookie);
  assert.equal((await loggedOutSession.text()) === "null", true);

  await pool.query(
    'UPDATE public.session SET "expiresAt" = now() - interval \'1 second\' WHERE "userId" = $1',
    [user.id],
  );
  const expiredSession = await request("get-session", undefined, userCookie);
  assert.equal((await expiredSession.text()) === "null", true);
});
