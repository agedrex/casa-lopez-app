import assert from "node:assert/strict";
import test from "node:test";
import { APIError } from "better-auth/api";
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

test("admin access denies missing sessions, normal roles, and false permissions", async () => {
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
  ];

  for (const dependencies of cases) {
    assert.equal(await hasAdminSession({ headers, ...dependencies }), false);
  }
});

test("admin verification failures reject with sanitized service errors", async () => {
  for (const error of [
    new Error("private database details"),
    new APIError("INTERNAL_SERVER_ERROR", {
      message: "private database details",
    }),
  ]) {
    for (const failedLookup of ["session", "permission"]) {
      await assert.rejects(
        hasAdminSession({
          headers: new Headers(),
          getSession: async () => {
            if (failedLookup === "session") throw error;
            return { user: { id: "u1", role: "admin" } };
          },
          hasPermission: async () => {
            if (failedLookup === "permission") throw error;
            return { success: true };
          },
        }),
        { message: "Authentication service unavailable." },
      );
    }
  }
});

test("known authentication and permission denials still fail closed", async () => {
  for (const error of [
    new APIError("UNAUTHORIZED"),
    new APIError("FORBIDDEN"),
  ]) {
    assert.equal(
      await hasAdminSession({
        headers: new Headers(),
        getSession: async () => ({ user: { id: "u1", role: "admin" } }),
        hasPermission: async () => {
          throw error;
        },
      }),
      false,
    );
  }
  assert.equal(
    await hasAdminSession({
      headers: new Headers(),
      getSession: async () => {
        throw new APIError("UNAUTHORIZED");
      },
      hasPermission: async () =>
        assert.fail("invalid sessions must not check permissions"),
    }),
    false,
  );
});
