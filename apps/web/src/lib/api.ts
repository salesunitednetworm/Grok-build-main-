import type {
  BuildingModel,
  BuildingPayload,
  CalibrationRun,
  EngineStatus,
  Home,
  HpxmlDoc,
  Job,
  PackageProposal,
  ProgramEvaluation,
  ProgramPack,
  Scenario,
  UtilityHistory,
  WeatherStation,
} from "./types";

const prefix = "";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${prefix}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...(init?.headers || {}) },
    cache: "no-store",
  });
  const raw = await response.text();
  if (!response.ok) {
    let detail = response.statusText;
    try {
      const body = JSON.parse(raw);
      detail = body.detail || JSON.stringify(body);
    } catch {
      detail = raw || detail;
    }
    throw new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
  }
  return (raw ? JSON.parse(raw) : null) as T;
}

export const api = {
  status: () => request<EngineStatus>("/api/v1/status"),
  homes: () => request<Home[]>("/api/v1/homes"),
  createHome: (body: Partial<Home> & { name: string }) =>
    request<Home>("/api/v1/homes", { method: "POST", body: JSON.stringify(body) }),
  home: (id: string) => request<Home>(`/api/v1/homes/${id}`),
  model: (id: string) => request<BuildingModel>(`/api/v1/homes/${id}/model`),
  saveModel: (id: string, payload: BuildingPayload) =>
    request<BuildingModel>(`/api/v1/homes/${id}/model`, {
      method: "PUT",
      body: JSON.stringify({ payload }),
    }),
  validate: (id: string) => request<BuildingModel>(`/api/v1/homes/${id}/validate`, { method: "POST" }),
  generateHpxml: (id: string) => request<HpxmlDoc>(`/api/v1/homes/${id}/hpxml`, { method: "POST" }),
  getHpxml: (id: string) => request<HpxmlDoc>(`/api/v1/homes/${id}/hpxml`),
  simulate: (id: string) => request<Job>(`/api/v1/homes/${id}/simulate`, { method: "POST" }),
  jobs: (id: string) => request<Job[]>(`/api/v1/homes/${id}/jobs`),
  weather: (zip: string) => request<WeatherStation>(`/api/v1/weather/${zip}`),
  createScenario: (id: string, body: Record<string, unknown>) =>
    request<Scenario>(`/api/v1/homes/${id}/scenarios`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  scenarios: (id: string) => request<Scenario[]>(`/api/v1/homes/${id}/scenarios`),
  saveBills: (id: string, body: { as_of: string; periods: unknown[] }) =>
    request<UtilityHistory>(`/api/v1/homes/${id}/utility-history`, {
      method: "PUT",
      body: JSON.stringify(body),
    }),
  getBills: (id: string) => request<UtilityHistory>(`/api/v1/homes/${id}/utility-history`),
  calibrate: (id: string, apply: boolean) =>
    request<CalibrationRun>(`/api/v1/homes/${id}/calibration`, {
      method: "POST",
      body: JSON.stringify({ apply_permitted_adjustments: apply }),
    }),
  getCalibration: (id: string) => request<CalibrationRun>(`/api/v1/homes/${id}/calibration`),
  createPackages: (id: string) =>
    request<PackageProposal[]>(`/api/v1/homes/${id}/packages`, { method: "POST" }),
  packages: (id: string) => request<PackageProposal[]>(`/api/v1/homes/${id}/packages`),
  programPacks: () => request<ProgramPack[]>("/api/v1/programs"),
  evaluateProgram: (id: string, body: Record<string, unknown>) =>
    request<ProgramEvaluation>(`/api/v1/homes/${id}/program-evaluations`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  programEvaluations: (id: string) =>
    request<ProgramEvaluation[]>(`/api/v1/homes/${id}/program-evaluations`),
  projectBoard: () => request<{ columns: Record<string, any[]>; stages: string[] }>("/api/v1/projects/board"),
  createProject: (body: { home_id: string; name?: string }) =>
    request<any>("/api/v1/projects", { method: "POST", body: JSON.stringify(body) }),
  project: (id: string) => request<any>(`/api/v1/projects/${id}`),
  setStage: (id: string, stage: string) =>
    request<any>(`/api/v1/projects/${id}/stage`, { method: "POST", body: JSON.stringify({ stage }) }),
  confirmProject: (id: string, body: { kind: string; source: string; reference: string }) =>
    request<any>(`/api/v1/projects/${id}/confirmations`, { method: "POST", body: JSON.stringify(body) }),
  createProposal: (id: string, body: { title: string; measures: string[] }) =>
    request<any>(`/api/v1/projects/${id}/proposals`, { method: "POST", body: JSON.stringify(body) }),
  sendProposal: (proposalId: string, body: { signer_name: string; signer_email: string }) =>
    request<any>(`/api/v1/proposals/${proposalId}/send`, { method: "POST", body: JSON.stringify(body) }),
  createWorkOrder: (id: string, body: { title: string; scope: string; proposal_id?: string }) =>
    request<any>(`/api/v1/projects/${id}/work-orders`, { method: "POST", body: JSON.stringify(body) }),
  homeownerStatus: (id: string) => request<any>(`/api/v1/projects/${id}/homeowner`),
};
