import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const schemaPath = new URL("../db/better-auth-public.sql", import.meta.url);
const sql = await readFile(schemaPath, "utf8");

function tableDefinition(name: string) {
  const match = sql.match(
    new RegExp(
      `CREATE TABLE(?: IF NOT EXISTS)?\\s+(?:"?public"?\\.)?"?${name}"?\\s*\\(([\\s\\S]*?)\\);`,
      "i",
    ),
  );
  assert.ok(match, `Expected a CREATE TABLE definition for ${name}`);
  return match[1];
}

test("Better Auth schema contains only its core public tables", () => {
  const tables = [
    ...sql.matchAll(
      /CREATE TABLE(?: IF NOT EXISTS)?\s+(?:("?public"?)\.)?"?([\w]+)"?/gi,
    ),
  ].map(([, schema, name]) => {
    assert.ok(
      !schema || schema.replaceAll('"', "").toLowerCase() === "public",
      "Better Auth tables must use the public schema",
    );
    return name.toLowerCase();
  });

  assert.deepEqual(tables.sort(), [
    "account",
    "session",
    "user",
    "verification",
  ]);
});

test("Admin plugin fields are present on the configured tables", () => {
  const user = tableDefinition("user");
  const session = tableDefinition("session");

  for (const field of ["role", "banned", "banReason", "banExpires"]) {
    assert.match(user, new RegExp(`"${field}"\\s`));
  }
  assert.match(session, /"impersonatedBy"\s/);
});

test("generated schema includes relationship and index DDL", () => {
  assert.ok(
    (sql.match(/\bREFERENCES\s+(?:"?public"?\.)?"?user"?\s*\(/gi) ?? [])
      .length >= 2,
  );
  assert.ok(
    (sql.match(/\bCREATE\s+(?:UNIQUE\s+)?INDEX\s+/gi) ?? []).length >= 2,
  );
  assert.match(sql, /\bUNIQUE\b/i);
});

function assertSafeSchema(source: string) {
  const statements = source
    .replace(/^\s*--.*$/gm, "")
    .split(";")
    .map((statement) => statement.trim())
    .filter(Boolean);

  assert.ok(statements.length >= 6);
  for (const statement of statements) {
    assert.doesNotMatch(statement, /\bcostos\b/i);
    assert.ok(
      /^CREATE\s+SCHEMA\s+IF\s+NOT\s+EXISTS\s+"public"$/i.test(statement) ||
        /^CREATE\s+TABLE\s+"public"\."(?:user|session|account|verification)"\s+\([\s\S]*\)$/i.test(
          statement,
        ) ||
        /^CREATE\s+(?:UNIQUE\s+)?INDEX\s+"[\w]+"\s+ON\s+"public"\."(?:user|session|account|verification)"\s+\([\w", ]+\)$/i.test(
          statement,
        ),
      `Unexpected or unsafe SQL statement: ${statement}`,
    );

    const qualifiedNames = statement.matchAll(
      /"?([A-Za-z_][\w$]*)"?\s*\.\s*"?[A-Za-z_][\w$]*"?/g,
    );
    for (const [, schema] of qualifiedNames) {
      assert.equal(
        schema.toLowerCase(),
        "public",
        `Unexpected schema: ${schema}`,
      );
    }

    const references = statement.matchAll(
      /\bREFERENCES\s+(?:"?([\w]+)"?\.)?"?([\w]+)"?/gi,
    );
    for (const [, schema, table] of references) {
      assert.equal(schema?.replaceAll('"', "").toLowerCase(), "public");
      assert.equal(table.replaceAll('"', "").toLowerCase(), "user");
    }
  }
}

test("generated SQL creates only public objects without destructive DDL", () => {
  assertSafeSchema(sql);
});

test("schema safety rejects other schemas, destructive DDL, and non-auth tables", () => {
  assert.throws(
    () =>
      assertSafeSchema(`${sql}\nCREATE TABLE "private"."user" ("id" text);`),
    /Unexpected or unsafe SQL statement/,
  );
  assert.throws(
    () =>
      assertSafeSchema(
        `${sql}\nCREATE TABLE "public"."user" ("id" text DEFAULT "private"."fn"());`,
      ),
    /Unexpected schema: private/,
  );
  assert.throws(
    () => assertSafeSchema(`${sql}\nDROP TABLE "public"."user";`),
    /Unexpected or unsafe SQL statement/,
  );
  assert.throws(
    () =>
      assertSafeSchema(`${sql}\nCREATE TABLE "public"."costos" ("id" text);`),
    /costos/,
  );
});
