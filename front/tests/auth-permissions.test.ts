import assert from "node:assert/strict";
import test from "node:test";
// Node's type stripping loads this TypeScript module directly.
// @ts-expect-error TypeScript does not allow this runtime extension by default.
import { adminRole, userRole } from "../lib/auth-permissions.ts";

const userManagementActions = [
  "create",
  "delete",
  "set-role",
  "set-password",
  "ban",
  "impersonate",
  "impersonate-admins",
] as const;

const sessionManagementActions = ["list", "revoke", "delete"] as const;

test("admin role grants application administration", () => {
  assert.equal(adminRole.authorize({ application: ["admin"] }).success, true);
});

test("user role cannot access application administration", () => {
  assert.equal(userRole.authorize({ application: ["admin"] }).success, false);
});

for (const [roleName, role] of [
  ["admin", adminRole],
  ["user", userRole],
] as const) {
  test(`${roleName} role denies Better Auth user management`, () => {
    for (const action of userManagementActions) {
      assert.equal(
        role.authorize({ user: [action] } as never).success,
        false,
        `${roleName} must not have user.${action}`,
      );
    }
  });

  test(`${roleName} role denies Better Auth session management`, () => {
    for (const action of sessionManagementActions) {
      assert.equal(
        role.authorize({ session: [action] } as never).success,
        false,
        `${roleName} must not have session.${action}`,
      );
    }
  });
}
