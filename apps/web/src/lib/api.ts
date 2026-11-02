import type {
  BuildingModel,
  BuildingPayload,
  CalibrationRun,
  EngineStatus,
  Home,
  HpxmlDoc,
  Job,
  PackageProposal,
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
};
