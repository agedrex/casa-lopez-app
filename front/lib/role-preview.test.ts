import assert from "node:assert/strict";
import { test } from "node:test";
import { withPreview } from "./role-preview";

const session = (role: string | null) => ({ user: { id: "u", role } });

function setEnv(env: Record<string, string>) {
  delete process.env.RAILWAY_ENVIRONMENT_NAME;
  delete process.env.ROLE_PREVIEW;
  Object.assign(process.env, env);
}

test("outside staging the cookie changes nothing, not even for an admin", () => {
  const environments: Record<string, string>[] = [
    {},
    { RAILWAY_ENVIRONMENT_NAME: "production" },
    { ROLE_PREVIEW: "true" },
  ];
  for (const env of environments) {
    setEnv(env);
    const result = withPreview(session("admin"), "gerente");
    assert.equal(result.user.role, "admin");
    assert.equal(result.previewAvailable, false);
  }
});

test("a real admin on staging can preview another role", () => {
  setEnv({ RAILWAY_ENVIRONMENT_NAME: "staging" });
  const result = withPreview(session("admin"), "gerente");
  assert.equal(result.user.role, "gerente");
  assert.equal(result.previewAvailable, true);
  assert.equal(withPreview(session("admin"), "bogus").user.role, "admin");
});

test("a non-admin cannot escalate with the cookie", () => {
  setEnv({ RAILWAY_ENVIRONMENT_NAME: "staging" });
  for (const role of ["gerente", "taller", "gerente,taller", null]) {
    const result = withPreview(session(role), "admin");
    assert.equal(result.user.role, role);
    assert.equal(result.previewAvailable, false);
  }
});

test("ROLE_PREVIEW=1 enables the preview locally for a real admin", () => {
  setEnv({ ROLE_PREVIEW: "1" });
  const result = withPreview(session("admin"), "taller");
  assert.equal(result.user.role, "taller");
  assert.equal(result.previewAvailable, true);
});
