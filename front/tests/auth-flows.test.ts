import assert from "node:assert/strict";
import test from "node:test";
import {
  getSafeRedirectPath,
  submitLogin,
  submitLogout,
  // @ts-expect-error Node's type stripping resolves this TypeScript extension at runtime.
} from "../lib/auth-client.ts";

test("login return path only accepts the canonical admin route", () => {
  assert.equal(getSafeRedirectPath("/admin"), "/admin");
  assert.equal(getSafeRedirectPath(undefined), "/admin");
  assert.equal(getSafeRedirectPath("https://attacker.example"), "/admin");
  assert.equal(getSafeRedirectPath("//attacker.example"), "/admin");
  assert.equal(getSafeRedirectPath("/\\attacker.example"), "/admin");
  assert.equal(getSafeRedirectPath("/admin\n//attacker.example"), "/admin");
  assert.equal(getSafeRedirectPath("/admin\r//attacker.example"), "/admin");
  assert.equal(getSafeRedirectPath("/%2f%2fattacker.example"), "/admin");
  assert.equal(getSafeRedirectPath("/admin%2f..%2fattacker"), "/admin");
});

test("login submits email credentials and reports success", async () => {
  let received: unknown;
  const result = await submitLogin(
    {
      email: async (input) => {
        received = input;
        return {};
      },
    },
    { email: "person@example.test", password: "secret", callbackURL: "/admin" },
  );

  assert.deepEqual(received, {
    email: "person@example.test",
    password: "secret",
    callbackURL: "/admin",
  });
  assert.deepEqual(result, { ok: true });
});

test("login reports rejected credentials and network errors", async () => {
  const credentials = await submitLogin(
    { email: async () => ({ error: new Error("invalid credentials") }) },
    { email: "person@example.test", password: "wrong", callbackURL: "/admin" },
  );
  const network = await submitLogin(
    {
      email: async () => {
        throw new Error("network unavailable");
      },
    },
    { email: "person@example.test", password: "secret", callbackURL: "/admin" },
  );

  assert.deepEqual(credentials, { ok: false, reason: "credentials" });
  assert.deepEqual(network, { ok: false, reason: "network" });
});

test("logout reports successful and failed sign-out requests", async () => {
  assert.equal(await submitLogout(async () => ({})), true);
  assert.equal(
    await submitLogout(async () => ({ error: new Error("rejected") })),
    false,
  );
  assert.equal(
    await submitLogout(async () => {
      throw new Error("network unavailable");
    }),
    false,
  );
});
