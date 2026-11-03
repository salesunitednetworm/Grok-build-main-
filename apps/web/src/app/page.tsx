"use client";

import Link from "next/link";
import { FormEvent, KeyboardEvent, useEffect, useId, useRef, useState } from "react";
import { applySuggestion, applyZipPlace, zip5 } from "@/lib/address";
import { api } from "@/lib/api";
import type { AddressSuggestion, EngineStatus, Home } from "@/lib/types";

const DEBOUNCE_MS = 350;

export default function HomePage() {
  const [homes, setHomes] = useState<Home[]>([]);
  const [status, setStatus] = useState<EngineStatus | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [name, setName] = useState("");
  const [city, setCity] = useState("");
  const [stateCode, setStateCode] = useState("");
  const [postal, setPostal] = useState("");
  const [placeNote, setPlaceNote] = useState<string | null>(null);
  const [suggestions, setSuggestions] = useState<AddressSuggestion[]>([]);
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(-1);
  const [looking, setLooking] = useState(false);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const seqRef = useRef(0);
  const listId = useId();

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
    return () => {
      if (debounceRef.current !== null) window.clearTimeout(debounceRef.current);
    };
  }, []);

  async function requestSuggestions(query: string) {
    const seq = ++seqRef.current;
    setLooking(true);
    try {
      const result = await api.addressSuggestions(query);
      if (seq !== seqRef.current) return;
      setSuggestions(result.items);
      setOpen(result.items.length > 0);
      setActive(result.items.length > 0 ? 0 : -1);
      if (result.items.length === 0 && query.trim().length >= 3) {
        setPlaceNote("No documented US match yet. Keep typing a house number and street.");
      }
    } catch {
      if (seq !== seqRef.current) return;
      setSuggestions([]);
      setOpen(false);
      setPlaceNote("Address suggestions are unavailable. City and state still fill from a known ZIP.");
    } finally {
      if (seq === seqRef.current) setLooking(false);
    }
  }

  function onStreetChange(value: string) {
    setName(value);
    if (debounceRef.current !== null) window.clearTimeout(debounceRef.current);
    if (value.trim().length < 3) {
      seqRef.current += 1;
      setSuggestions([]);
      setOpen(false);
      setActive(-1);
      setLooking(false);
      return;
    }
    debounceRef.current = window.setTimeout(() => {
      void requestSuggestions(value);
    }, DEBOUNCE_MS);
  }

  async function pick(item: AddressSuggestion) {
    seqRef.current += 1;
    if (debounceRef.current !== null) window.clearTimeout(debounceRef.current);
    setOpen(false);
    setSuggestions([]);
    setActive(-1);
    const next = applySuggestion(
      { street: name, city, state: stateCode, zip: postal },
      item,
    );
    setName(next.street);
    setCity(next.city);
    setStateCode(next.state);
    setPostal(next.zip);
    setPlaceNote(
      item.postal_code
        ? `Filled from ${item.source === "census" ? "US Census Geocoder" : "Photon / OpenStreetMap"}.`
        : "Street, city, and state filled. ZIP was not in the geocoder match.",
    );
    try {
      const filled = await api.addressLookup({
        address: item.label,
        street: item.street,
        city: item.city,
        state_code: item.state_code,
        postal_code: item.postal_code,
        source: item.source,
        id: item.id,
      });
      const standardized = applySuggestion(next, filled);
      setName(standardized.street);
      setCity(standardized.city);
      setStateCode(standardized.state);
      setPostal(standardized.zip);
      setPlaceNote(
        filled.postal_code
          ? `Filled from ${filled.source === "census" ? "US Census Geocoder" : "Photon / OpenStreetMap"}.`
          : "Street, city, and state filled. ZIP was not in the geocoder match.",
      );
    } catch {
      // Keep the Photon fields already written. Do not invent a ZIP.
    }
  }

  function onStreetKeyDown(event: KeyboardEvent<HTMLInputElement>) {
    if (!open || suggestions.length === 0) return;
    if (event.key === "ArrowDown") {
      event.preventDefault();
      setActive((index) => Math.min(suggestions.length - 1, index + 1));
    } else if (event.key === "ArrowUp") {
      event.preventDefault();
      setActive((index) => Math.max(0, index - 1));
    } else if (event.key === "Enter") {
      if (active >= 0 && suggestions[active]) {
        event.preventDefault();
        void pick(suggestions[active]);
      }
    } else if (event.key === "Escape") {
      event.preventDefault();
      setOpen(false);
    }
  }

  async function fillFromZip(raw: string) {
    const digits = zip5(raw);
    setPostal(digits);
    if (digits.length !== 5) {
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
      setPlaceNote(`${station.city}, ${station.state_code} from the OS-HPXML ZIP table.`);
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
          Type a US street to see real Photon / OpenStreetMap matches. Selecting one fills street,
          city, state, and ZIP when the geocoder has them. Census standardizes the match on select.
        </p>
        <form onSubmit={onCreate} className="grid" autoComplete="off">
          <label className="address-field">
            Street address
            <input
              name="address-line1"
              autoComplete="off"
              autoCorrect="off"
              spellCheck={false}
              inputMode="text"
              placeholder="Start typing a house number and street"
              value={name}
              required
              role="combobox"
              aria-autocomplete="list"
              aria-expanded={open}
              aria-controls={listId}
              aria-activedescendant={active >= 0 ? `${listId}-${active}` : undefined}
              onChange={(e) => onStreetChange(e.target.value)}
              onKeyDown={onStreetKeyDown}
              onBlur={() => window.setTimeout(() => setOpen(false), 180)}
              onFocus={() => {
                if (suggestions.length > 0) setOpen(true);
              }}
            />
            {looking && <span className="fine suggest-status">Looking up addresses…</span>}
            {open && suggestions.length > 0 && (
              <ul className="suggest-list" id={listId} role="listbox">
                {suggestions.map((item, index) => (
                  <li
                    key={item.id}
                    id={`${listId}-${index}`}
                    role="option"
                    aria-selected={index === active}
                    onPointerDown={(event) => {
                      event.preventDefault();
                      void pick(item);
                    }}
                  >
                    <strong>{item.street}</strong>
                    <span>
                      {[item.city, item.state_code, item.postal_code].filter(Boolean).join(" · ")}
                    </span>
                  </li>
                ))}
              </ul>
            )}
          </label>
          <label>
            ZIP
            <input
              name="postal-code"
              autoComplete="postal-code"
              inputMode="numeric"
              placeholder="ZIP"
              value={postal}
              onChange={(e) => void fillFromZip(e.target.value)}
            />
          </label>
          <label>
            City
            <input
              name="address-level2"
              autoComplete="address-level2"
              placeholder="City"
              value={city}
              onChange={(e) => setCity(e.target.value)}
            />
          </label>
          <label>
            State
            <input
              name="address-level1"
              autoComplete="address-level1"
              maxLength={2}
              placeholder="ST"
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
