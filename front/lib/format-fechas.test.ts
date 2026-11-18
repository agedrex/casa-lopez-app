import assert from "node:assert/strict";
import { test } from "node:test";
import {
  formatDate,
  formatDateTime,
  formatInstantDate,
  formatInstantTime,
} from "./format";

test("an UTC instant is shown in Buenos Aires time: 02:11Z of the 18th is 23:11 of the 17th", () => {
  assert.equal(formatDateTime("2026-11-18T02:11:00Z"), "17/11/2026 23:11");
  assert.equal(formatInstantDate("2026-11-18T02:11:00Z"), "17/11/2026");
  assert.equal(formatInstantTime("2026-11-18T02:11:00Z"), "23:11");
});

test("the offset written by the API is honoured: +00:00 and -03:00 give the same moment", () => {
  assert.equal(formatDateTime("2026-11-18T02:11:00+00:00"), "17/11/2026 23:11");
  assert.equal(
    formatDateTime("2026-11-17T23:11:00.123456-03:00"),
    "17/11/2026 23:11",
  );
});

test("an instant without offset is read as UTC (the server clock)", () => {
  assert.equal(formatDateTime("2026-11-18T02:11:00"), "17/11/2026 23:11");
});

test("the day changes at 03:00Z, not at midnight UTC", () => {
  assert.equal(formatInstantDate("2026-11-18T02:59:59Z"), "17/11/2026");
  assert.equal(formatInstantDate("2026-11-18T03:00:00Z"), "18/11/2026");
});

test("an instant at midnight Buenos Aires shows 00:xx, never 24:xx", () => {
  assert.equal(formatDateTime("2026-11-18T03:05:00Z"), "18/11/2026 00:05");
});

test("empty or unreadable values show a dash or the original text", () => {
  assert.equal(formatDateTime(null), "—");
  assert.equal(formatInstantDate(undefined), "—");
  assert.equal(formatInstantTime(""), "—");
  assert.equal(formatDateTime("no es una fecha"), "no es una fecha");
});

test("a plain date (no time) keeps its day: it is not an instant", () => {
  assert.equal(formatDate("2026-11-18"), "18/11/2026");
  assert.equal(formatInstantDate("2026-11-18"), "18/11/2026");
});
