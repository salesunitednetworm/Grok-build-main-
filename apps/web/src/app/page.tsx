"use client";

import Link from "next/link";
import { FormEvent, useEffect, useState } from "react";
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
          Start the modeling slice: building data → validate → HPXML → simulate → one attic upgrade.
        </p>
        <form onSubmit={onCreate} className="grid">
          <label>
            Name
            <input value={name} onChange={(e) => setName(e.target.value)} required />
          </label>
          <label>
            City
            <input value={city} onChange={(e) => setCity(e.target.value)} />
          </label>
          <label>
            State
            <input value={stateCode} maxLength={2} onChange={(e) => setStateCode(e.target.value.toUpperCase())} />
          </label>
          <label>
            ZIP
            <input value={postal} onChange={(e) => setPostal(e.target.value)} />
          </label>
          <div className="row">
            <button type="submit">Create home</button>
          </div>
        </form>
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
