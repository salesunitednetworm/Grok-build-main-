import assert from "node:assert/strict";
import { test } from "node:test";
import { applySuggestion, applyZipPlace, geocoderLabel, zip5 } from "./address";

test("zip5 keeps the first five digits", () => {
  assert.equal(zip5("80202-1234"), "80202");
});

test("ZIP place fills city and state without inventing a street", () => {
  const next = applyZipPlace(
    { street: "100 N Tryon St", city: "", state: "", zip: "28202" },
    { city: "Charlotte", state_code: "NC", zipcode: "28202" },
  );
  assert.equal(next.city, "Charlotte");
  assert.equal(next.state, "NC");
  assert.equal(next.street, "100 N Tryon St");
});

test("suggestion fill does not invent a missing ZIP", () => {
  const next = applySuggestion(
    { street: "", city: "", state: "", zip: "" },
    { street: "100 N Tryon St", city: "Charlotte", state_code: "NC", postal_code: null },
  );
  assert.equal(next.street, "100 N Tryon St");
  assert.equal(next.city, "Charlotte");
  assert.equal(next.state, "NC");
  assert.equal(next.zip, "");
});

test("geocoder labels stay factual", () => {
  assert.equal(geocoderLabel("esri"), "Esri World Geocoding Service");
  assert.doesNotMatch(geocoderLabel("esri"), /DOE|approved|HOMES/i);
});
