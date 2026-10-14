import assert from "node:assert/strict";
import test from "node:test";
// @ts-expect-error Node's type stripping resolves this TypeScript extension at runtime.
import { hasAdminSession } from "../lib/admin-auth.ts";

test("admin access requires both a valid session and the application admin permission", async () => {
  const headers = new Headers({ cookie: "session=valid" });
  assert.equal(
    await hasAdminSession({
      headers,
      getSession: async () => ({ user: { id: "u1", role: "admin" } }),
      hasPermission: async (requestHeaders, permissions) => {
        assert.equal(requestHeaders, headers);
        assert.deepEqual(permissions, { application: ["admin"] });
        return { success: true };
      },
    }),
    true,
  );
});

test("admin access denies missing sessions, normal roles, false permissions, and lookup errors", async () => {
  const headers = new Headers();
  const cases = [
    {
      getSession: async () => null,
      hasPermission: async () => ({ success: true }),
    },
    {
      getSession: async () => ({ user: { id: "u1", role: "user" } }),
      hasPermission: async () => ({ success: true }),
    },
    {
      getSession: async () => ({ user: { id: "u1", role: "admin" } }),
      hasPermission: async () => ({ success: false }),
    },
    {
      getSession: async () => {
        throw new Error("session lookup failed");
      },
      hasPermission: async () => ({ success: true }),
    },
    {
      getSession: async () => ({ user: { id: "u1", role: "admin" } }),
      hasPermission: async () => {
        throw new Error("permission lookup failed");
      },
    },
  ];

  for (const dependencies of cases) {
    assert.equal(await hasAdminSession({ headers, ...dependencies }), false);
  }
});
