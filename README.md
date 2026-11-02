# Home Energy Modeling Platform

Residential energy modeling in [`salesunitednetworm/Grok-build-main-`](https://github.com/salesunitednetworm/Grok-build-main-). Isolated from PreSite Pro, SalesGrid, and the unmerged Sales United portal (draft PRs #1 and #2).

This software is **not** DOE HOMES (IRA 50121) approved, **not** BPI-2400 qualified, and **not** ACCA Manual J / S / D software. EnergyPlus and Manual-style design loads are **preliminary**. The UI never invents kWh or savings percentages.

## Stack

| Layer | Pin |
| --- | --- |
| Web | Next.js + React + TypeScript (`apps/web`) |
| API + worker | FastAPI (`apps/api`) |
| Database | PostgreSQL 16 |
| Physics adapter | OpenStudio-HPXML **v1.12.0** via OpenStudio **3.11.0** CLI (EnergyPlus **25.2.0**, HPXML **v5.0-rc1**) |

See `docs/architecture/` and `docs/roadmap.md`.

## Local development (Docker)

```bash
docker compose up --build
```

- UI: http://localhost:3000
- API: http://localhost:8000/docs

Without the OpenStudio CLI, jobs complete as **`unavailable`**. HPXML is still generated and stored. No fake energy results.

On Ubuntu 24.04 x86_64, install the pinned engine (official tarball + OS-HPXML zip; TMY3 files inside the 1.12.0 `weather/` folder):

```bash
./scripts/install-openstudio.sh
export OPENSTUDIO_CLI=/usr/local/openstudio-3.11.0/bin/openstudio
export OPENSTUDIO_HPXML_DIR=/opt/OpenStudio-HPXML-1.12.0
```

Optional Compose profile builds `nrel/openstudio:3.11.0` plus OS-HPXML 1.12.0 as the worker (`--scale worker=0` avoids a second worker without the engine):

```bash
docker compose --profile simulator up --build --scale worker=0
```

## Local development (no Docker)

```bash
cd apps/api
python3 -m pip install -r requirements.txt
export DATABASE_URL=sqlite:///./data/hems.db
export ARTIFACT_ROOT=./data/artifacts
export WORKER_INLINE=true
python3 -m pytest
python3 -m uvicorn app.main:app --reload --port 8000

cd ../web
npm install
npm test
npm run dev
```

## Vertical slice

Create Home → Enter Building Data → Validate → Generate HPXML → Map ZIP to TMY3 → Run OpenStudio-HPXML/EnergyPlus → Store artifacts → Display energy results (plus software defaults and `run.log` warnings) → Compare attic, heat-pump, or duct-leakage upgrades.

Utility history, residual scaffolding, and attic / air-sealing / HPWH packages sit on the same path. Calibration is **preliminary / not certified** and is not a BPI-2400 claim. Packages and upgrade scenarios re-run EnergyPlus; they do not add percentages.

ZIP weather uses OS-HPXML `zipcode_weather_stations.csv`. Official station is always shown; if that EPW is not shipped, the nearest shipped TMY3 is used and labeled.

Verification harness: `apps/api/tests/verification/` (versioned artifacts; no ASHRAE 140 verdicts).

NC / GA HOMES/HEAR **program screens** are versioned JSON rule packs. They pin the pack version on each evaluation, use stored EnergyPlus totals only, and never claim DOE approval or portal submission.

## Attribution

OpenStudio, EnergyPlus, and OpenStudio-HPXML are used as unmodified engines under their BSD-3-like licenses. This product is not named OpenStudio or EnergyPlus. See `NOTICE`.
