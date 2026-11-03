import assert from "node:assert/strict";
import { test } from "node:test";
import { applyZipPlace, exampleByZip, zip5 } from "./address";

test("zip5 keeps the first five digits", () => {
  assert.equal(zip5("80202-1234"), "80202");
});

test("ZIP place fills city and state without inventing a street", () => {
  const next = applyZipPlace(
    { street: "12 Pine Street", city: "", state: "", zip: "80202" },
    { city: "Denver", state_code: "CO", zipcode: "80202" },
  );
  assert.equal(next.city, "Denver");
  assert.equal(next.state, "CO");
  assert.equal(next.street, "12 Pine Street");
});

test("example list is keyed by documented demo ZIPs", () => {
  assert.equal(exampleByZip("27601")?.city, "Raleigh");
});
