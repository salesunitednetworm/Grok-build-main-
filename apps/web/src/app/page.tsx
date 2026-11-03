"use client";

import Link from "next/link";
import { FormEvent, useEffect, useState } from "react";
import { EXAMPLE_ADDRESSES, applyZipPlace, zip5 } from "@/lib/address";
import { api } from "@/lib/api";
import type { EngineStatus, Home } from "@/lib/types";

export default function HomePage() {
  const [homes, setHomes] = useState<Home[]>([]);
  const [status, setStatus] = useState<EngineStatus | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [name, setName] = useState("12 Pine Street");
  const [city, setCity] = useState("Denver");
  const [stateCode, setStateCode] = useState("CO");
  const [postal, setPostal] = useState("80202");
  const [placeNote, setPlaceNote] = useState<string | null>(null);

  async function load() {
    try {
      const [list, engine] = await Promise.all([api.homes(), api.status()]);
      setHomes(list);
      setStatus(engine);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load");
    }
  }

  useEffect(() => {
    void load();
  }, []);

  function applyExample(index: string) {
    const example = EXAMPLE_ADDRESSES[Number(index)];
    if (!example) return;
    setName(example.street);
    setCity(example.city);
    setStateCode(example.state);
    setPostal(example.zip);
    setPlaceNote("Example address filled. City and state also come from the OS-HPXML ZIP table when you change ZIP.");
  }

  async function fillFromZip(raw: string) {
    const digits = zip5(raw);
    setPostal(digits);
    if (digits.length !== 5) {
      setPlaceNote(null);
      return;
    }
    try {
      const station = await api.weather(digits);
      const next = applyZipPlace(
        { street: name, city, state: stateCode, zip: digits },
        station,
      );
      setCity(next.city);
      setStateCode(next.state);
      setPostal(next.zip);
      setPlaceNote(`${station.city}, ${station.state_code} from the OS-HPXML ZIP table. Not a street geocoder.`);
    } catch {
      setPlaceNote("ZIP is not in the OS-HPXML table. City and state were left as typed.");
    }
  }

  async function onCreate(event: FormEvent) {
    event.preventDefault();
    setError(null);
    try {
      const home = await api.createHome({
        name,
        city,
        state_code: stateCode,
        postal_code: postal,
        address_line1: name,
      });
      window.location.href = `/homes/${home.id}`;
    } catch (err) {
      setError(err instanceof Error ? err.message : "Create failed");
    }
  }

  return (
    <main>
      {status && (
        <div className="banner">
          <strong>{status.available ? "Simulation engine is installed." : "Simulation unavailable."}</strong>{" "}
          {status.reason || status.display_name} Energy use (kWh) is shown only after EnergyPlus
          writes results. {status.regulatory[0]}
        </div>
      )}

      <div className="card">
        <h1>Create a home</h1>
        <p className="fine">
          Building data → validate → HPXML → simulate → attic compare → bills → calibration scaffolding →
          packages. Calibration is preliminary / not certified.
        </p>
        <form onSubmit={onCreate} className="grid" autoComplete="on">
          <label>
            Example address
            <select defaultValue="" onChange={(e) => applyExample(e.target.value)}>
              <option value="">Tap to fill street, city, state, ZIP</option>
              {EXAMPLE_ADDRESSES.map((row, index) => (
                <option key={row.zip} value={String(index)}>
                  {row.street}, {row.city}, {row.state} {row.zip}
                </option>
              ))}
            </select>
          </label>
          <label>
            Street
            <input
              name="address-line1"
              autoComplete="address-line1"
              value={name}
              onChange={(e) => setName(e.target.value)}
              required
            />
          </label>
          <label>
            ZIP
            <input
              name="postal-code"
              autoComplete="postal-code"
              inputMode="numeric"
              value={postal}
              onChange={(e) => void fillFromZip(e.target.value)}
            />
          </label>
          <label>
            City
            <input name="address-level2" autoComplete="address-level2" value={city} onChange={(e) => setCity(e.target.value)} />
          </label>
          <label>
            State
            <input
              name="address-level1"
              autoComplete="address-level1"
              maxLength={2}
              value={stateCode}
              onChange={(e) => setStateCode(e.target.value.toUpperCase())}
            />
          </label>
          <div className="row">
            <button type="submit">Create home</button>
          </div>
        </form>
        {placeNote && <p className="fine">{placeNote}</p>}
        {error && <p className="errors">{error}</p>}
      </div>

      <div className="card">
        <h2>Homes</h2>
        {homes.length === 0 ? (
          <p className="fine">No homes yet.</p>
        ) : (
          <ul className="home-list">
            {homes.map((home) => (
              <li key={home.id}>
                <Link href={`/homes/${home.id}`}>{home.name}</Link>
                <div className="fine">
                  {[home.city, home.state_code, home.postal_code].filter(Boolean).join(" · ")}
                </div>
              </li>
            ))}
          </ul>
        )}
      </div>
    </main>
  );
}
