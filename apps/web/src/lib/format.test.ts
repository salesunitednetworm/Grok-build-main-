import assert from "node:assert/strict";
import { test } from "node:test";
import { formatDelta, formatEnergy, neverInvented } from "./format.ts";

test("missing energy is labeled not simulated, never zero", () => {
  assert.equal(formatEnergy(null, "kWh"), "Not simulated");
  assert.equal(formatEnergy(undefined, "kWh"), "Not simulated");
  assert.notEqual(formatEnergy(null, "kWh"), "0 kWh");
  assert.equal(neverInvented(null), true);
});

test("real energy is formatted with units", () => {
  assert.match(formatEnergy(1234.56, "kWh"), /1,234\.6 kWh/);
});

test("missing comparison delta is not a percentage", () => {
  assert.equal(formatDelta(null, "kWh"), "Not available");
  assert.doesNotMatch(formatDelta(null, "kWh"), /%/);
});

test("pending deltas are labeled running, never zero", () => {
  assert.equal(formatDelta(null, "kWh", "pending"), "Running…");
  assert.notEqual(formatDelta(null, "kWh", "pending"), "0 kWh");
});
