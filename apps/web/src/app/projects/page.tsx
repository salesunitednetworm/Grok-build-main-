"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { Home } from "@/lib/types";

type Card = {
  id: string;
  name: string;
  home_name: string | null;
  stage: string;
  homeowner_next: string;
  claims_reservation: boolean;
  claims_payment: boolean;
};

export default function BoardPage() {
  const [columns, setColumns] = useState<Record<string, Card[]>>({});
  const [stages, setStages] = useState<string[]>([]);
  const [homes, setHomes] = useState<Home[]>([]);
  const [homeId, setHomeId] = useState("");
  const [error, setError] = useState<string | null>(null);

  async function load() {
    try {
      const [board, list] = await Promise.all([api.projectBoard(), api.homes()]);
      setColumns(board.columns);
      setStages(board.stages);
      setHomes(list);
      if (!homeId && list[0]) setHomeId(list[0].id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Load failed");
    }
  }

  useEffect(() => {
    void load();
  }, []);

  async function create() {
    if (!homeId) return;
    setError(null);
    try {
      await api.createProject({ home_id: homeId });
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Create failed");
    }
  }

  return (
    <main>
      <div className="card">
        <h1>Contractor job board</h1>
        <p className="fine">
          Stages persist on each project. Submission, reservation, approval, and payment stay unused
          unless an external confirmation is recorded. This board is not a CRM and not a rebate portal.
        </p>
        <div className="row">
          <select value={homeId} onChange={(e) => setHomeId(e.target.value)}>
            {homes.map((home) => (
              <option key={home.id} value={home.id}>
                {home.name}
              </option>
            ))}
          </select>
          <button type="button" onClick={() => void create()}>
            Open job
          </button>
        </div>
        {error && <p className="errors">{error}</p>}
      </div>
      <div className="board">
        {stages.map((stage) => (
          <section key={stage} className="board-col">
            <h3>{stage.replaceAll("_", " ")}</h3>
            {(columns[stage] || []).map((card) => (
              <Link key={card.id} href={`/projects/${card.id}`} className="board-card">
                <strong>{card.name}</strong>
                <span className="fine">{card.home_name}</span>
                <span className="fine">{card.homeowner_next}</span>
              </Link>
            ))}
          </section>
        ))}
      </div>
    </main>
  );
}
