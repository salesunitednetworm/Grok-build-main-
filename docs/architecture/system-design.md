# System design — Home Energy Modeling Platform

This is the product architecture for the energy platform in [`salesunitednetworm/Grok-build-main-`](https://github.com/salesunitednetworm/Grok-build-main-). It is built from the existing research in `docs/research/`; it does not replace those notes.

**Working name:** Home Energy Modeling Platform (HEMS).  
**Repo role:** isolated energy product. Draft PRs [#1](https://github.com/salesunitednetworm/Grok-build-main-/pull/1) (workspace contract) and [#2](https://github.com/salesunitednetworm/Grok-build-main-/pull/2) (Sales United portal) stay on their own branches. This app does not occupy the repo root with a static site and does not add a GitHub Pages whole-repo deploy.

## What this product is

A contractor-facing application that:

1. Captures a home and a canonical building description.
2. Validates that description against our domain rules.
3. Generates HPXML for the pinned OpenStudio-HPXML EnergyPlus use case.
4. Runs a residential EnergyPlus simulation through a **provider adapter**.
5. Stores artifacts (HPXML, logs, annual results).
6. Displays **only** energy numbers that came from a real simulation parse.
7. Compares one upgrade scenario by re-running the same home with a single measure change.

It is **not** a land/lot sales portal, not PreSite Pro, and not a DOE-listed HOMES tool.

## Locked technical choices

| Layer | Choice | Why (from research) |
| --- | --- | --- |
| Web | Next.js + React + TypeScript | Product UI we own; not OS-HPXML (which has no GUI) |
| API | FastAPI (Python) | Owns domain model, HPXML authoring, job control |
| Data | PostgreSQL | Homes, models, jobs, artifacts, results |
| Work | Queue workers | Simulations are 3–10 s when the engine is present; must not block HTTP |
| Physics | **OpenStudio-HPXML v1.12.0** via **OpenStudio 3.11.0 CLI** | Official residential adapter; HPXML in, EnergyPlus out |
| Engine inside that CLI | **EnergyPlus 25.2.0** (bundled) | Do not substitute standalone EnergyPlus 26.2.0 |
| Transfer schema | **HPXML v5.0-rc1** (`http://hpxmlonline.com/2025/12`) | What OS-HPXML 1.12.0 expects |
| Domain | Canonical building model + provider adapters | We never treat HPXML or EnergyPlus IDF as the source of truth |

ResStock / OpenStudio-BuildStock is **not** the per-home adapter. Raw EnergyPlus IDF authoring is out. OpenStudio Application geometry is out.

## Regulatory posture (non-negotiable)

- **Do not claim DOE HOMES (IRA 50121) approval.** Wrapping OpenStudio-HPXML is not product approval. Approval is product-specific after the May 2024 DOE/NREL single-family procedure. See `docs/research/doe-verification-requirements.md`.
- **Do not claim BPI-2400 compliance.** BPI-2400 is a calibration and savings process we have not implemented. See `docs/research/hpxml-and-bpi-2400.md`.
- **Do not claim ACCA Manual J / S / D approval.** OpenStudio-HPXML design loads emulate block-load Manual J math. Until ACCA lists *this* product, every design-load figure is labeled **preliminary**. See `docs/research/hvac-acca-standards.md`.
- **Do not invent kWh or savings percentages.** If EnergyPlus did not run, the UI says simulation is unavailable and leaves energy fields empty.
- Trademarks: we run official OpenStudio / EnergyPlus / OpenStudio-HPXML binaries with required notices. We do not brand a modified fork as OpenStudio or EnergyPlus.

## Component map

```
┌─────────────────────────────────────────────┐
│  apps/web  — Next.js / React / TypeScript   │
│  Create Home → Building form → Validate     │
│  HPXML preview → Job status → Results       │
│  One upgrade comparison                     │
└─────────────────────┬───────────────────────┘
                      │ HTTPS JSON
┌─────────────────────▼───────────────────────┐
│  apps/api  — FastAPI                        │
│  Homes, building models, validation         │
│  HPXML authoring, job enqueue, reads        │
└───────┬─────────────────────────┬───────────┘
        │                         │
        ▼                         ▼
┌───────────────┐       ┌─────────────────────┐
│  PostgreSQL   │       │  Queue worker       │
│  homes        │       │  (SKIP LOCKED poll) │
│  models       │◄──────┤  ModelProvider.run  │
│  jobs         │       └──────────┬──────────┘
│  artifacts    │                  │
│  results      │                  ▼
└───────────────┘       ┌─────────────────────┐
                        │  OpenStudioHpxml    │
                        │  Provider adapter   │
                        │  generate → CLI →   │
                        │  parse artifacts    │
                        │  or UNAVAILABLE     │
                        └─────────────────────┘
```

PreSite Pro, Zoho, HighLevel, CompanyCam, AHRI, and Green Button **Connect My Data** are **ports only**. Domain code does not import those products. See `docs/research/integrations.md`.

## Vertical-slice flow

1. **Create Home** — name, address, ZIP, state.
2. **Enter Building Data** — canonical payload: geometry, enclosure (attic / foundation / rim joists), infiltration, HVAC (furnace or heat pump / mini-split), measured duct CFM25, DHW. Appliances/lighting use OS-HPXML software defaults until we collect them.
3. **Validate** — domain rules first (required fields, physical bounds). Provider-level XSD/Schematron when the OS-HPXML tree is present; errors map onto form fields.
4. **Generate HPXML** — our author (not `BuildResidentialHPXML`, which is a subset). Persist XML as an artifact.
5. **Map weather** — ZIP → official TMY3 from `zipcode_weather_stations.csv`. If that EPW is not shipped, use the nearest shipped TMY3 and label `nearest_shipped`.
6. **Run simulation** — worker claims a job. If `openstudio` + OS-HPXML 1.12.0 + weather are present, run:

   ```
   openstudio workflow/run_simulation.rb -x <file.xml> -o <run_dir> --output-format json
   ```

   If they are not present, mark the job **`unavailable`**. Do not write energy rows.
7. **Store artifacts** — input HPXML, `in.xml` / `results_annual.json` / `run.log` when produced, plus job metadata. Persist `run.log` warnings and `in.xml` `dataSource='software'` defaults on the energy row.
8. **Display energy results** — parsed Fuel Use and End Use from `results_annual.json` only. Design loads shown as **preliminary**. Software defaults and engine warnings sit next to the numbers.
9. **Compare upgrades** — copy the validated model, apply one measure (`attic_insulation`, `heat_pump`, or `duct_leakage`), generate a second HPXML, run a second job. Deltas exist only when **both** jobs have parsed EnergyPlus results.

## Simulation-unavailable path

This Cloud Agent host now has the pinned engine (`scripts/install-openstudio.sh`). Local machines and Compose may still omit it.

When the CLI, measure tree, or weather files are missing:

| Happens | Does not happen |
| --- | --- |
| HPXML is still generated and stored | No invented annual kWh |
| Job status = `unavailable` with a reason | No invented % savings |
| UI banner: engine not installed | No “demo results” toggle |
| Comparison shows the measure + XML, not energy | No BPI-2400 equivalent-energy math |

Turning the engine on later is configuration (`OPENSTUDIO_CLI`, `OPENSTUDIO_HPXML_DIR`), not a rewrite.

## Application layout (repo)

Energy code lives under `apps/`. Root stays free of `index.html` / `assets/` / `.github/workflows/deploy-pages.yml` so PR #2’s portal cannot be overwritten and `main` cannot be published as a static dump.

```
apps/web          Next.js UI
apps/api          FastAPI + worker entrypoint
docs/             Architecture and (later) copied research
docker-compose.yml
```

## Storage and tenancy (v1)

- **v1 is single-operator.** No contractor accounts, no UNITED2026-style client gate.
- Artifacts are files on a configured volume (`ARTIFACT_ROOT`), referenced from PostgreSQL.
- Production later: object storage, per-tenant isolation, auth. Not this slice.

## Integration ports (build later, shape now)

Domain code talks to ports. First photo implementation, when needed, is `PreSiteProFileAdapter` (object storage + JSON sidecars) — not CompanyCam endpoints and not a clone of `pre-site-pro`.

| Port | First adapter | Status |
| --- | --- | --- |
| `ModelProvider` | `OpenStudioHpxmlProvider` | **This slice** |
| `JobPhotoPort` | `PreSiteProFileAdapter` | Adapter stub later |
| `CrmPort` | none | Zoho / HighLevel when chosen |
| `UtilityUsagePort` | Green Button DMD file parse | After this slice |
| `EquipmentCatalogPort` | ENERGY STAR SODA | AHRI remains license-blocked |

## Local development

`docker compose up` starts PostgreSQL, API, worker, and web. The simulator worker is optional (`docker compose --profile simulator up --scale worker=0`) and is built from `nrel/openstudio:3.11.0` plus OpenStudio-HPXML 1.12.0. Without that profile or a host install, the API still serves the slice and jobs complete as `unavailable`.

On Ubuntu 24.04 x86_64, `scripts/install-openstudio.sh` places:

- CLI: `/usr/local/openstudio-3.11.0/bin/openstudio` (reports `3.11.0+241b8abb4d`)
- EnergyPlus: `/usr/local/openstudio-3.11.0/EnergyPlus/energyplus` (`25.2.0-cf7368216c`)
- Measures + weather: `/opt/OpenStudio-HPXML-1.12.0` (shipped TMY3s include Miami, Phoenix, Portland, Denver Intl, Colorado Springs; not every official ZIP station)

ZIP mapping uses `HPXMLtoOpenStudio/resources/data/zipcode_weather_stations.csv`. Official station is always stored; missing official EPWs fall back to the nearest shipped TMY3 and are labeled. Pins did not change.

Without Docker, the API accepts `DATABASE_URL` (PostgreSQL) or a local SQLite file for unit tests only. Production and Compose use PostgreSQL.

## Attribution we must keep

Redistribute and invoke official OpenStudio SDK, EnergyPlus, and OpenStudio-HPXML with their BSD-3-like notices. Product name is ours. Modified distributions must not use the OpenStudio or EnergyPlus marks.

## Out of scope for this architecture revision

- DOE/NREL software-verification submission
- BPI-2400 calibration (detailed or simplified)
- Utility-bill ingest and weather normalization
- ACCA-approved Manual J/S/D reports
- Multifamily / BuildingSync
- ResStock market sampling
- Sales United portal merge
- Cloning or editing `pre-site-pro` or `salesgrid-snapshot`
