# Changelog

## 0.1.0 — 2026-11-02

- Add architecture and roadmap under `docs/` (system design, database, model provider interface, energy model validation).
- Add FastAPI service with canonical building model, domain validation, HPXML v5.0-rc1 authoring, OpenStudio-HPXML provider adapter, artifact storage, and a PostgreSQL-backed job queue.
- Jobs finish `unavailable` (no kWh) when OpenStudio 3.11.0 / OpenStudio-HPXML 1.12.0 are not installed. No mock savings percentages.
- Add one upgrade scenario: attic / ceiling insulation, with deltas only after two parsed EnergyPlus results.
- Add Next.js UI for the Create Home → Validate → HPXML → Simulate → Results → Compare flow.
- Add Docker Compose for PostgreSQL, API, worker, and web.
- Tests: 21 API/domain tests; UI format helpers refuse to display invented zeros.
