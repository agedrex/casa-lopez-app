import assert from "node:assert/strict";
import test from "node:test";
import { APIError } from "better-auth/api";
// @ts-expect-error Node's type stripping resolves this TypeScript extension at runtime.
import { createInternalSessionHandler } from "../lib/auth-session.ts";

test("internal session endpoint rejects a missing or incorrect secret", async () => {
  let calls = 0;
  const handle = createInternalSessionHandler({
    secret: () => "server-only-secret",
    getSession: async () => {
      calls += 1;
      return null;
    },
  });

  for (const authorization of [null, "Bearer wrong-secret"]) {
    const response = await handle(
      new Request("https://example.test/api/internal/auth/session", {
        method: "POST",
        headers: authorization ? { authorization } : {},
      }),
    );
    assert.equal(response.status, 401);
    assert.equal(response.headers.get("cache-control"), "private, no-store");
  }

  assert.equal(calls, 0);
});

test("valid internal request forwards only the browser cookie and returns minimal identity", async () => {
  let receivedHeaders: Headers | undefined;
  const handle = createInternalSessionHandler({
    secret: () => "server-only-secret",
    getSession: async (headers) => {
      receivedHeaders = headers;
      return {
        user: { id: "user-7", role: "admin", email: "private@example.test" },
        session: { id: "session-secret", token: "never-return-this" },
      };
    },
  });

  const response = await handle(
    new Request("https://example.test/api/internal/auth/session", {
      method: "POST",
      headers: {
        authorization: "Bearer server-only-secret",
        cookie: "better-auth.session_token=browser-cookie",
        "x-untrusted-role": "admin",
        "x-untrusted-id": "forged-user",
      },
    }),
  );

  assert.equal(response.status, 200);
  assert.equal(response.headers.get("cache-control"), "private, no-store");
  assert.deepEqual(await response.json(), { user_id: "user-7", role: "admin" });
  assert.equal(
    receivedHeaders?.get("cookie"),
    "better-auth.session_token=browser-cookie",
  );
  assert.equal(receivedHeaders?.has("x-untrusted-role"), false);
  assert.equal(receivedHeaders?.has("authorization"), false);
});

test("missing, invalid, and expired sessions return 401", async () => {
  for (const session of [null, { user: null }, { user: {} }]) {
    const handle = createInternalSessionHandler({
      secret: () => "server-only-secret",
      getSession: async () => session,
    });
    const response = await handle(
      new Request("https://example.test/api/internal/auth/session", {
        method: "POST",
        headers: {
          authorization: "Bearer server-only-secret",
          cookie: "expired=value",
        },
      }),
    );
    assert.equal(response.status, 401);
    assert.equal(response.headers.get("cache-control"), "private, no-store");
  }
});

test("session verification errors preserve 401 and sanitize service failures as 503", async () => {
  for (const [error, status] of [
    [new APIError("UNAUTHORIZED"), 401],
    [
      new APIError("INTERNAL_SERVER_ERROR", {
        message: "private database details",
      }),
      503,
    ],
    [new Error("private database details"), 503],
  ] as const) {
    const handle = createInternalSessionHandler({
      secret: () => "server-only-secret",
      getSession: async () => {
        throw error;
      },
    });
    const response = await handle(
      new Request("https://example.test/api/internal/auth/session", {
        method: "POST",
        headers: {
          authorization: "Bearer server-only-secret",
          cookie: "session=browser-cookie",
        },
      }),
    );
    assert.equal(response.status, status);
    assert.deepEqual(await response.json(), {
      error:
        status === 401 ? "unauthorized" : "authentication_service_unavailable",
    });
    assert.equal(response.headers.get("cache-control"), "private, no-store");
  }
});
