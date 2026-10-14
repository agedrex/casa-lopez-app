import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const schemaPath = new URL("../db/better-auth-public.sql", import.meta.url);
const sql = await readFile(schemaPath, "utf8");

function tableDefinition(name: string) {
  const match = sql.match(
    new RegExp(
      `CREATE TABLE(?: IF NOT EXISTS)?\\s+(?:"?public"?\\.)?"?${name}"?\\s*\\(([\\s\\S]*?)\\n\\);`,
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

test("generated SQL creates only public objects without destructive DDL", () => {
  assert.doesNotMatch(sql, /\b(?:CREATE|DROP)\s+SCHEMA\b/i);
  assert.doesNotMatch(
    sql,
    /\b(?:DROP|TRUNCATE|DELETE\s+FROM|ALTER\s+TABLE|GRANT|REVOKE)\b/i,
  );

  const qualifiedNames = sql.matchAll(
    /\b(?:CREATE\s+(?:UNIQUE\s+)?INDEX(?: IF NOT EXISTS)?|CREATE\s+TABLE(?: IF NOT EXISTS)?|REFERENCES|ON)\s+(?:("?([\w]+)"?)\.)?"?([\w]+)"?/gi,
  );
  for (const [, , schema] of qualifiedNames) {
    assert.ok(
      !schema || schema.replaceAll('"', "").toLowerCase() === "public",
      `Unexpected schema: ${schema}`,
    );
  }

  const statements = sql
    .replace(/^\s*--.*$/gm, "")
    .split(";")
    .map((statement) => statement.trim())
    .filter(Boolean);
  assert.ok(statements.length >= 6);
  for (const statement of statements) {
    assert.match(statement, /^CREATE\s+(?:TABLE|(?:UNIQUE\s+)?INDEX)\b/i);
  }
});
