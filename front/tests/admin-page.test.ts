import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { createRequire } from "node:module";
import { resolve } from "node:path";
import test from "node:test";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { JsxEmit, ModuleKind, ScriptTarget, transpileModule } from "typescript";
// @ts-expect-error Node's type stripping resolves this TypeScript extension at runtime.
import { getAdminSession } from "../lib/admin-auth.ts";

type PageMocks = {
  session: { user?: { id?: string; email?: string; role?: string } } | null;
  sessionError?: Error;
  permissionSuccess: boolean;
  permissionCalls?: number;
  adminStatus: { authenticated: true } | null;
  adminStatusCalls?: number;
  redirectPath?: string;
};

const require = createRequire(import.meta.url);
const pagePath = resolve("app/admin/page.tsx");
const source = readFileSync(pagePath, "utf8");
const compiledPage = transpileModule(source, {
  compilerOptions: {
    jsx: JsxEmit.ReactJSX,
    module: ModuleKind.CommonJS,
    target: ScriptTarget.ES2022,
  },
}).outputText;

function loadPage(mocks: PageMocks) {
  const module = { exports: {} as { default?: () => Promise<unknown> } };
  const pageRequire = (specifier: string) => {
    if (specifier === "next/headers") {
      return {
        headers: async () => new Headers({ cookie: "session=controlled" }),
      };
    }
    if (specifier === "next/navigation") {
      return {
        redirect: (path: string) => {
          mocks.redirectPath = path;
          throw new Error("NEXT_REDIRECT");
        },
      };
    }
    if (specifier === "next/server")
      return { connection: async () => undefined };
    if (specifier === "@/app/admin/logout-button") {
      return {
        LogoutButton: () =>
          createElement("button", { type: "button" }, "Sign out"),
      };
    }
    if (specifier === "@/lib/admin-auth") {
      return {
        requireAdminSession: (headers: Headers) =>
          getAdminSession({
            headers,
            getSession: async () => {
              if (mocks.sessionError) throw mocks.sessionError;
              return mocks.session;
            },
            hasPermission: async () => {
              mocks.permissionCalls = (mocks.permissionCalls ?? 0) + 1;
              return { success: mocks.permissionSuccess };
            },
          }),
      };
    }
    if (specifier === "@/lib/admin-status") {
      return {
        fetchAdminStatus: async () => {
          mocks.adminStatusCalls = (mocks.adminStatusCalls ?? 0) + 1;
          return mocks.adminStatus;
        },
      };
    }
    return require(specifier);
  };

  new Function("require", "module", "exports", compiledPage)(
    pageRequire,
    module,
    module.exports,
  );
  const page = module.exports.default;
  if (!page) throw new Error("Admin page module did not export a page.");
  return page;
}

async function renderPage(mocks: PageMocks) {
  const page = loadPage(mocks);
  const element = await page();
  return renderToStaticMarkup(
    element as Parameters<typeof renderToStaticMarkup>[0],
  );
}

test("admin page redirects when the auth helper finds no valid session", async () => {
  const mocks: PageMocks = {
    session: null,
    permissionSuccess: true,
    adminStatus: null,
  };
  await assert.rejects(renderPage(mocks), { message: "NEXT_REDIRECT" });
  assert.equal(mocks.redirectPath, "/login?next=%2Fadmin");
  assert.equal(mocks.permissionCalls ?? 0, 0);
  assert.equal(mocks.adminStatusCalls ?? 0, 0);
});

test("admin page shows the unavailable screen when auth service fails", async () => {
  const mocks: PageMocks = {
    session: { user: { id: "admin-7", role: "admin" } },
    sessionError: new Error("private auth service details"),
    permissionSuccess: true,
    adminStatus: null,
  };
  const html = await renderPage(mocks);

  assert.match(html, /aria-labelledby="admin-unavailable-title"/);
  assert.doesNotMatch(html, /aria-labelledby="admin-title"/);
  assert.doesNotMatch(html, /admin@example\.test/);
  assert.equal(mocks.permissionCalls ?? 0, 0);
  assert.equal(mocks.adminStatusCalls ?? 0, 0);
});

test("admin page renders admin content for an authenticated administrator", async () => {
  const html = await renderPage({
    session: {
      user: { id: "admin-7", email: "admin@example.test", role: "admin" },
    },
    permissionSuccess: true,
    adminStatus: { authenticated: true },
  });

  assert.match(html, /admin-title/);
  assert.match(html, /admin@example\.test/);
  assert.match(html, /Verificación administrativa: activa/);
});

test("admin page redirects when an authenticated non-admin is denied", async () => {
  const mocks: PageMocks = {
    session: {
      user: { id: "user-7", email: "user@example.test", role: "user" },
    },
    permissionSuccess: true,
    adminStatus: null,
  };

  await assert.rejects(renderPage(mocks), { message: "NEXT_REDIRECT" });
  assert.equal(mocks.redirectPath, "/login?next=%2Fadmin");
  assert.equal(mocks.permissionCalls ?? 0, 0);
  assert.equal(mocks.adminStatusCalls ?? 0, 0);
});
