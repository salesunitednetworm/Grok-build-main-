"use client";

import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";

type View = {
  home_name: string | null;
  stage: string;
  what_to_do_next: string;
  claims_portal_submission: boolean;
  claims_approval: boolean;
  claims_reservation: boolean;
  claims_payment: boolean;
};

export default function HomeownerStatusPage() {
  const { id } = useParams<{ id: string }>();
  const [view, setView] = useState<View | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .homeownerStatus(id)
      .then(setView)
      .catch((err) => setError(err instanceof Error ? err.message : "Load failed"));
  }, [id]);

  if (!view) return <p className="fine">{error || "Loading…"}</p>;

  return (
    <main>
      <div className="card">
        <h1>Job status</h1>
        <p className="fine">{view.home_name}</p>
        <p>
          Stage: <span className={`status ${view.stage}`}>{view.stage.replaceAll("_", " ")}</span>
        </p>
        <h2>What to do next</h2>
        <p>{view.what_to_do_next}</p>
        <p className="fine">
          This page does not file a rebate. Portal / reservation / approval / payment claims stay false unless
          an external confirmation was recorded: submission {String(view.claims_portal_submission)}, approval{" "}
          {String(view.claims_approval)}, reservation {String(view.claims_reservation)}, payment{" "}
          {String(view.claims_payment)}.
        </p>
      </div>
    </main>
  );
}
