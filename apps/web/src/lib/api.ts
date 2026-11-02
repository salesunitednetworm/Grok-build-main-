import type {
  BuildingModel,
  BuildingPayload,
  EngineStatus,
  Home,
  HpxmlDoc,
  Job,
  Scenario,
} from "./types";

const prefix = "";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${prefix}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...(init?.headers || {}) },
    cache: "no-store",
  });
  if (!response.ok) {
    let detail = response.statusText;
    try {
      const body = await response.json();
      detail = body.detail || JSON.stringify(body);
    } catch {
      detail = await response.text();
    }
    throw new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
  }
  return response.json() as Promise<T>;
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
  createScenario: (id: string, ceiling_assembly_r: number) =>
    request<Scenario>(`/api/v1/homes/${id}/scenarios`, {
      method: "POST",
      body: JSON.stringify({
        name: `Attic insulation to R-${ceiling_assembly_r}`,
        measure_type: "attic_insulation",
        ceiling_assembly_r,
      }),
    }),
  scenarios: (id: string) => request<Scenario[]>(`/api/v1/homes/${id}/scenarios`),
};
