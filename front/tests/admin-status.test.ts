import assert from "node:assert/strict";
import test from "node:test";
// @ts-expect-error Node's type stripping resolves this TypeScript extension at runtime.
import { fetchAdminStatus } from "../lib/admin-status.ts";

const adminPayload = {
  authenticated: true,
  user_id: "backend-user-7",
  role: "admin",
};

test("admin status forwards only the cookie with uncached, non-redirecting options", async () => {
  let requestUrl: URL | undefined;
  let requestOptions: RequestInit | undefined;
  const result = await fetchAdminStatus({
    backendUrl: "https://backend.example.test/",
    cookie: "session=browser-cookie",
    expectedUserId: adminPayload.user_id,
    fetchImpl: async (input, init) => {
      requestUrl = new URL(input);
      requestOptions = init;
      return Response.json(adminPayload);
    },
  });

  assert.deepEqual(result, adminPayload);
  assert.equal(
    requestUrl?.href,
    "https://backend.example.test/api/admin/status",
  );
  assert.equal(requestOptions?.method, "GET");
  assert.equal(requestOptions?.cache, "no-store");
  assert.equal(requestOptions?.redirect, "manual");
  assert.deepEqual(requestOptions?.headers, {
    cookie: "session=browser-cookie",
  });
  assert.equal(requestOptions?.signal instanceof AbortSignal, true);
});

test("admin status rejects backend 401, 403, and other non-200 responses", async () => {
  for (const status of [301, 302, 401, 403, 503]) {
    const result = await fetchAdminStatus({
      backendUrl: "https://backend.example.test",
      cookie: "session=browser-cookie",
      expectedUserId: "backend-user-7",
      fetchImpl: async () => new Response(null, { status }),
    });
    assert.equal(result, null);
  }
});

test("admin status rejects malformed, non-admin, and invalid JSON responses", async () => {
  const responses = [
    Response.json({ authenticated: true, user_id: "user-7" }),
    Response.json({ authenticated: true, user_id: "user-7", role: "user" }),
    new Response("not-json", { status: 200 }),
  ];

  for (const response of responses) {
    assert.equal(
      await fetchAdminStatus({
        backendUrl: "https://backend.example.test",
        cookie: "session=browser-cookie",
        expectedUserId: "user-7",
        fetchImpl: async () => response,
      }),
      null,
    );
  }
});

test("admin status fails closed for missing configuration, cookie, network, and timeout", async () => {
  let fetchCalls = 0;
  const fetchImpl = async () => {
    fetchCalls += 1;
    throw new Error("unavailable");
  };

  assert.equal(
    await fetchAdminStatus({
      backendUrl: undefined,
      cookie: "x",
      expectedUserId: "user-7",
      fetchImpl,
    }),
    null,
  );
  assert.equal(
    await fetchAdminStatus({
      backendUrl: "relative/path",
      cookie: "x",
      expectedUserId: "user-7",
      fetchImpl,
    }),
    null,
  );
  assert.equal(
    await fetchAdminStatus({
      backendUrl: "https://backend.example.test",
      cookie: null,
      expectedUserId: "user-7",
      fetchImpl,
    }),
    null,
  );
  assert.equal(fetchCalls, 0);

  assert.equal(
    await fetchAdminStatus({
      backendUrl: "https://backend.example.test",
      cookie: "session=browser-cookie",
      expectedUserId: "user-7",
      fetchImpl,
    }),
    null,
  );

  assert.equal(
    await fetchAdminStatus({
      backendUrl: "https://backend.example.test",
      cookie: "session=browser-cookie",
      expectedUserId: "user-7",
      fetchImpl: async () => {
        throw new DOMException("Timed out", "TimeoutError");
      },
    }),
    null,
  );
});

test("admin status refuses plain HTTP for public hosts", async () => {
  let fetchCalls = 0;
  const fetchImpl = async () => {
    fetchCalls += 1;
    return Response.json(adminPayload);
  };

  for (const backendUrl of ["http://backend.example.test", "http://8.8.8.8"]) {
    assert.equal(
      await fetchAdminStatus({
        backendUrl,
        cookie: "session=browser-cookie",
        expectedUserId: adminPayload.user_id,
        fetchImpl,
      }),
      null,
    );
  }
  assert.equal(fetchCalls, 0);
});

test("admin status accepts private HTTP service hosts", async () => {
  for (const backendUrl of [
    "http://localhost:8000",
    "http://127.0.0.1:8000",
    "http://10.10.0.5:8000",
    "http://backend.internal:8000",
    "http://backend.railway.internal:8000",
  ]) {
    const result = await fetchAdminStatus({
      backendUrl,
      cookie: "session=browser-cookie",
      expectedUserId: adminPayload.user_id,
      fetchImpl: async () => Response.json(adminPayload),
    });
    assert.deepEqual(result, adminPayload);
  }
});

test("admin status rejects an identity that differs from the Better Auth user", async () => {
  const result = await fetchAdminStatus({
    backendUrl: "https://backend.example.test",
    cookie: "session=browser-cookie",
    expectedUserId: "better-auth-user-7",
    fetchImpl: async () => Response.json(adminPayload),
  });

  assert.equal(result, null);
});
