"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { FormEvent, useEffect, useState } from "react";
import { api } from "@/lib/api";

type Project = {
  id: string;
  name: string;
  stage: string;
  stages: string[];
  homeowner: { what_to_do_next: string; contractor_next: string; claims_payment: boolean };
  confirmations: Record<string, { reference?: string } | null>;
  checklist: { id: string; code: string; label: string; completed: boolean }[];
  proposals: {
    id: string;
    title: string;
    status: string;
    envelope_status: string | null;
    program_evaluation_pack_version: string | null;
  }[];
  work_orders: {
    id: string;
    title: string;
    status: string;
    program_evaluation_pack_version: string | null;
  }[];
  building_model_id: string | null;
  program_evaluation_id: string | null;
  program_evaluation_pack_version: string | null;
  crm_ref: { status: string; note: string } | null;
};

export default function ProjectPage() {
  const { id } = useParams<{ id: string }>();
  const [project, setProject] = useState<Project | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function load() {
    try {
      setProject(await api.project(id));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Load failed");
    }
  }

  useEffect(() => {
    void load();
  }, [id]);

  async function move(event: FormEvent) {
    event.preventDefault();
    const data = new FormData(event.target as HTMLFormElement);
    setError(null);
    try {
      setProject(await api.setStage(id, String(data.get("stage"))));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Stage change failed");
    }
  }

  async function confirm(event: FormEvent) {
    event.preventDefault();
    const data = new FormData(event.target as HTMLFormElement);
    setError(null);
    try {
      setProject(
        await api.confirmProject(id, {
          kind: String(data.get("kind")),
          source: String(data.get("source")),
          reference: String(data.get("reference")),
        }),
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : "Confirmation failed");
    }
  }

  async function addProposal(event: FormEvent) {
    event.preventDefault();
    const data = new FormData(event.target as HTMLFormElement);
    setError(null);
    try {
      await api.createProposal(id, {
        title: String(data.get("title")),
        measures: String(data.get("measures") || "")
          .split(",")
          .map((part) => part.trim())
          .filter(Boolean),
      });
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Proposal failed");
    }
  }

  async function send(proposalId: string) {
    setError(null);
    try {
      await api.sendProposal(proposalId, { signer_name: "Homeowner", signer_email: "owner@example.com" });
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Send failed");
    }
  }

  async function addWorkOrder(event: FormEvent) {
    event.preventDefault();
    const data = new FormData(event.target as HTMLFormElement);
    setError(null);
    try {
      await api.createWorkOrder(id, {
        title: String(data.get("title")),
        scope: String(data.get("scope")),
        proposal_id: String(data.get("proposal_id") || "") || undefined,
      });
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Work order failed");
    }
  }

  if (!project) return <p className="fine">{error || "Loading…"}</p>;

  return (
    <main>
      <div className="card">
        <h1>{project.name}</h1>
        <p>
          Stage: <span className={`status ${project.stage}`}>{project.stage.replaceAll("_", " ")}</span>
        </p>
        <p className="fine">Homeowner next: {project.homeowner.what_to_do_next}</p>
        <p className="fine">Contractor next: {project.homeowner.contractor_next}</p>
        <p className="fine">
          Model {project.building_model_id || "none"} · evaluation {project.program_evaluation_id || "none"} v
          {project.program_evaluation_pack_version || "—"}
        </p>
        <p className="fine">
          CRM: {project.crm_ref?.status} — {project.crm_ref?.note}
        </p>
        <p className="fine">
          <Link href={`/projects/${project.id}/homeowner`}>Homeowner status page</Link>
        </p>
        <form onSubmit={move} className="row">
          <select name="stage" defaultValue={project.stage} key={project.stage}>
            {project.stages.map((stage) => (
              <option key={stage} value={stage}>
                {stage.replaceAll("_", " ")}
              </option>
            ))}
          </select>
          <button type="submit">Set stage</button>
        </form>
        {error && <p className="errors">{error}</p>}
      </div>
      <div className="card">
        <h2>External confirmations</h2>
        <p className="fine">
          Submission, reservation, approval, and payment stay unset until an operator records a source and
          reference from outside this app.
        </p>
        <p className="fine">
          {Object.entries(project.confirmations)
            .map(([key, value]) => `${key}:${value?.reference || "unset"}`)
            .join(" · ")}
        </p>
        <form onSubmit={confirm} className="row">
          <select name="kind">
            <option value="program_submission">program submission</option>
            <option value="approval">approval</option>
            <option value="reservation">reservation</option>
            <option value="final_submission">final submission</option>
            <option value="payment">payment</option>
          </select>
          <input name="source" placeholder="External source" required />
          <input name="reference" placeholder="Reference id" required />
          <button type="submit">Record confirmation</button>
        </form>
      </div>
      <div className="card">
        <h2>Photo checklist</h2>
        <ul>
          {project.checklist.map((item) => (
            <li key={item.id}>
              {item.completed ? "done" : "open"} — {item.label}
            </li>
          ))}
        </ul>
        <p className="fine">Upload via `/photos` writes a PreSite Pro file sidecar. No vendor success.</p>
      </div>
      <div className="card">
        <h2>Proposal / work order</h2>
        <ul>
          {project.proposals.map((record) => (
            <li key={record.id}>
              {record.title} — {record.status} / {record.envelope_status || "no envelope"} (pack{" "}
              {record.program_evaluation_pack_version || "none"})
              <button type="button" className="secondary" onClick={() => void send(record.id)}>
                Send via file e-sign
              </button>
            </li>
          ))}
        </ul>
        <form onSubmit={addProposal} className="row">
          <input name="title" placeholder="Proposal title" required />
          <input name="measures" placeholder="measures, comma separated" />
          <button type="submit">Create proposal</button>
        </form>
        <ul>
          {project.work_orders.map((order) => (
            <li key={order.id}>
              {order.title} — {order.status} (pack {order.program_evaluation_pack_version || "none"})
            </li>
          ))}
        </ul>
        <form onSubmit={addWorkOrder} className="row">
          <input name="title" placeholder="Work order title" required />
          <input name="scope" placeholder="Scope (not a rebate)" required />
          <input name="proposal_id" placeholder="Proposal id (optional)" />
          <button type="submit">Create work order</button>
        </form>
      </div>
    </main>
  );
}
