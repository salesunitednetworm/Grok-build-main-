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

Without the OpenStudio CLI mounted, jobs complete as **`unavailable`**. HPXML is still generated and stored. No fake energy results.

To run real simulations, install OpenStudio 3.11.0 and OpenStudio-HPXML 1.12.0 on the host and pass:

```bash
OPENSTUDIO_CLI=/usr/local/openstudio-3.11.0/bin/openstudio \
OPENSTUDIO_HPXML_DIR=/opt/OpenStudio-HPXML-1.12.0 \
docker compose up --build
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

Create Home → Enter Building Data → Validate → Generate HPXML → Run OpenStudio-HPXML/EnergyPlus → Store artifacts → Display energy results → Compare one attic-insulation upgrade.

## Attribution

OpenStudio, EnergyPlus, and OpenStudio-HPXML are used as unmodified engines under their BSD-3-like licenses. This product is not named OpenStudio or EnergyPlus. See `NOTICE`.
