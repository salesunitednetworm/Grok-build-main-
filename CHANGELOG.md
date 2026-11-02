# Changelog

## 0.3.0 — 2026-11-02

- ZIP → TMY3 from official OS-HPXML `zipcode_weather_stations.csv`. Official station is always stored. Missing official EPWs use the nearest shipped TMY3 and are labeled `nearest_shipped` (80202 official is Broomfield; shipped fallback is Denver Intl). 33101 maps to Miami TMY3.
- Parse `in.xml` `dataSource='software'` defaults and `run.log` warnings onto `energy_results`; show both in the UI.
- Translate XSD (`xmllint`) and Schematron (`OpenStudio::XMLValidator` when the CLI is present) onto form fields.
- First-class audit fields: vented/unvented attic; conditioned/unconditioned basement, slab, vented/unvented crawl; rim joists; heat pump and mini-split (HSPF2/SEER2); ductless; measured duct CFM25.
- Scenarios `heat_pump` and `duct_leakage` generate real HPXML and re-run EnergyPlus. No invented kWh. Still not DOE / BPI / ACCA.

## 0.2.0 — 2026-11-02

- BPI-2400 *scaffolding*: utility history, 330-day quality gate, residuals vs simulated annual fuels, permitted setpoint adjustments only. Models labeled `uncalibrated` or `calibrated` with `preliminary_not_certified`. Never `bpi_2400_calibrated`.
- Documented gaps on every calibration run (no G14 CVRMSE, no 183-day HDD/CDD path, no delivered-fuel path, no kWhe %, no §3.4 table copy).
- Verification harness under `apps/api/tests/verification/` with versioned artifacts: HPXML emit + XSD, baseline/post ECM-only, fuel totals, official OS-HPXML samples. No invented ASHRAE 140 pass/fail.
- First package optimizer: attic R-49, air sealing ACH50 1.5, HPWH UEF 3.5 — all seven combinations re-run EnergyPlus. Absolute deltas only.
- HPXML `WaterHeaterType` may be `heat pump water heater`.
- UI steps for bills, calibration labels, and packages.

## 0.1.1 — 2026-11-02

- Install OpenStudio 3.11.0 (`241b8abb4d`) and OpenStudio-HPXML v1.12.0 on Ubuntu 24.04; EnergyPlus reports `25.2.0-cf7368216c`.
- Fix HPXML `Address` element order (`StateCode` before `ZipCode`) so the EnergyPlus use-case XSD accepts our file.
- Provider picks artifacts from OS-HPXML's `<output>/run/` directory and runs with cwd at the 1.12.0 tree.
- Live baseline + attic R-49 upgrade persist parsed EnergyPlus kWh/therm (no invented values).
- Add `scripts/install-openstudio.sh` and Compose `--profile simulator` (`Dockerfile.simulator` on `nrel/openstudio:3.11.0`).
- Pins unchanged: 1.12.0 / 3.11.0 / 25.2.0 / HPXML v5.0-rc1.

## 0.1.0 — 2026-11-02

- Add architecture and roadmap under `docs/` (system design, database, model provider interface, energy model validation).
- Add FastAPI service with canonical building model, domain validation, HPXML v5.0-rc1 authoring, OpenStudio-HPXML provider adapter, artifact storage, and a PostgreSQL-backed job queue.
- Jobs finish `unavailable` (no kWh) when OpenStudio 3.11.0 / OpenStudio-HPXML 1.12.0 are not installed. No mock savings percentages.
- Add one upgrade scenario: attic / ceiling insulation, with deltas only after two parsed EnergyPlus results.
- Add Next.js UI for the Create Home → Validate → HPXML → Simulate → Results → Compare flow.
- Add Docker Compose for PostgreSQL, API, worker, and web.
- Tests: 21 API/domain tests; UI format helpers refuse to display invented zeros.
