# Database design — Home Energy Modeling Platform

PostgreSQL is the system of record. The canonical building description is JSON we own. HPXML is a generated document, not the database.

This schema is sized for the first vertical slice and for the next few milestones (utility bills, calibration evidence) without inventing those tables as if they already work.

## Principles

1. **Canonical model first.** `building_models.payload` is the editable source. HPXML is derived.
2. **Artifacts are immutable.** A new generate or run creates new rows. We do not overwrite XML after a job starts.
3. **Energy numbers are nullable.** `energy_results` exists only after a successful parse of provider output. Unavailable jobs have artifacts (HPXML) and **no** kWh row.
4. **Comparisons do not store percentages unless both sides simulated.** No default `0.20` savings column.
5. **Measured vs default** is recorded on the payload (`data_source`) so a later BPI-2400 constraint engine can refuse to “calibrate” blower-door or nameplate values.

## Entity relationship

```
homes 1───* building_models 1───* hpxml_documents
                │                      │
                │                      └──* simulation_jobs *───* simulation_artifacts
                │                                │
                │                                └──0..1 energy_results
                │
                └──* upgrade_scenarios 1───0..1 comparisons
                         │                      │
                         ├── baseline_model     ├── baseline_job
                         └── upgraded_model     └── upgrade_job

homes 1───1 utility_histories
homes 1───* calibration_runs
homes 1───* package_proposals
homes 1───* program_applications 1───* program_evaluations
```

## Tables

### `homes`

A dwelling we are modeling. Not a CRM deal.

| Column | Type | Notes |
| --- | --- | --- |
| `id` | UUID PK | |
| `name` | TEXT NOT NULL | Operator label |
| `address_line1` | TEXT | |
| `city` | TEXT | |
| `state_code` | CHAR(2) | HPXML `StateCode` |
| `postal_code` | TEXT | ZIP; maps to TMY3 via OS-HPXML `zipcode_weather_stations.csv` |
| `created_at` | TIMESTAMPTZ | |
| `updated_at` | TIMESTAMPTZ | |

### `building_models`

Versioned canonical snapshot.

| Column | Type | Notes |
| --- | --- | --- |
| `id` | UUID PK | |
| `home_id` | UUID FK homes | |
| `version` | INT NOT NULL | Per-home increment |
| `role` | TEXT NOT NULL | `baseline` \| `upgrade` |
| `status` | TEXT NOT NULL | `draft` \| `valid` \| `invalid` |
| `payload` | JSONB NOT NULL | Canonical building (below) |
| `validation_errors` | JSONB | List of `{code, field, message}` |
| `parent_model_id` | UUID NULL FK | Upgrade cloned from this baseline |
| `created_at` | TIMESTAMPTZ | |

Unique `(home_id, version)`.

### `hpxml_documents`

| Column | Type | Notes |
| --- | --- | --- |
| `id` | UUID PK | |
| `building_model_id` | UUID FK | |
| `schema_version` | TEXT NOT NULL | `5.0-rc1` for this pin |
| `namespace` | TEXT NOT NULL | `http://hpxmlonline.com/2025/12` |
| `xml_text` | TEXT NOT NULL | Instance document we authored |
| `generated_at` | TIMESTAMPTZ | |

### `simulation_jobs`

| Column | Type | Notes |
| --- | --- | --- |
| `id` | UUID PK | |
| `home_id` | UUID FK | |
| `building_model_id` | UUID FK | |
| `hpxml_document_id` | UUID FK | Input to the provider |
| `provider` | TEXT NOT NULL | `openstudio_hpxml` |
| `provider_version` | TEXT | `1.12.0` when known |
| `job_type` | TEXT NOT NULL | `baseline` \| `upgrade` |
| `scenario_id` | UUID NULL FK | Set for upgrade jobs |
| `status` | TEXT NOT NULL | `queued` \| `running` \| `succeeded` \| `failed` \| `unavailable` |
| `unavailable_reason` | TEXT | e.g. OpenStudio CLI not installed |
| `error_message` | TEXT | Provider/CLI errors; never a fake result |
| `queued_at` / `started_at` / `finished_at` | TIMESTAMPTZ | |
| `attempt_count` | INT DEFAULT 0 | |

Workers claim with `UPDATE … WHERE status = 'queued' RETURNING …` (PostgreSQL `FOR UPDATE SKIP LOCKED` in Compose).

### `simulation_artifacts`

| Column | Type | Notes |
| --- | --- | --- |
| `id` | UUID PK | |
| `job_id` | UUID FK | |
| `kind` | TEXT NOT NULL | `hpxml_input` \| `in_xml` \| `results_annual_json` \| `run_log` \| `eplusout_err` |
| `content_type` | TEXT | |
| `storage_path` | TEXT NOT NULL | Under `ARTIFACT_ROOT` |
| `byte_size` | INT | |
| `checksum_sha256` | TEXT | |
| `created_at` | TIMESTAMPTZ | |

### `energy_results`

Created **only** when `results_annual.json` (or equivalent) was parsed.

| Column | Type | Notes |
| --- | --- | --- |
| `id` | UUID PK | |
| `job_id` | UUID FK UNIQUE | One result set per successful job |
| `source` | TEXT NOT NULL | `openstudio_hpxml_energyplus` — never `estimated` |
| `total_mbtu` | DOUBLE PRECISION | Energy Use: Total |
| `electricity_mbtu` | DOUBLE PRECISION | Fuel Use: Electricity: Total |
| `electricity_kwh` | DOUBLE PRECISION | Derived: MBtu × 1e6 / 3412 |
| `natural_gas_mbtu` | DOUBLE PRECISION | |
| `natural_gas_therm` | DOUBLE PRECISION | Derived: MBtu × 10 |
| `fuel_oil_mbtu` / `propane_mbtu` | DOUBLE PRECISION | |
| `end_uses` | JSONB | Fuel × end-use MBtu map from the file |
| `heating_design_load_btuh` | DOUBLE PRECISION | **Preliminary** |
| `cooling_sensible_design_load_btuh` | DOUBLE PRECISION | **Preliminary** |
| `loads_qualification` | TEXT NOT NULL | Always `preliminary` in v1 |
| `raw_annual` | JSONB | Full parsed annual object |
| `run_log_warnings` | JSONB | Warning lines from provider `run.log` |
| `software_defaults` | JSONB | `in.xml` nodes with `dataSource='software'` |
| `created_at` | TIMESTAMPTZ | |

Conversion constants are stored in code, not guessed per row. If a key is missing from the provider file, the column stays NULL.

### `upgrade_scenarios`

| Column | Type | Notes |
| --- | --- | --- |
| `id` | UUID PK | |
| `home_id` | UUID FK | |
| `baseline_model_id` | UUID FK | |
| `upgraded_model_id` | UUID FK | |
| `name` | TEXT NOT NULL | |
| `measure_type` | TEXT NOT NULL | `attic_insulation` \| `heat_pump` \| `duct_leakage` |
| `measure_payload` | JSONB NOT NULL | e.g. `{ "ceiling_assembly_r": 49 }` or HSPF2/SEER2 or CFM25 |
| `created_at` | TIMESTAMPTZ | |

Each measure clones the baseline and changes only those fields, then re-runs EnergyPlus.

### `comparisons`

| Column | Type | Notes |
| --- | --- | --- |
| `id` | UUID PK | |
| `scenario_id` | UUID FK UNIQUE | |
| `baseline_job_id` | UUID FK | |
| `upgrade_job_id` | UUID FK | |
| `status` | TEXT NOT NULL | `pending` \| `complete` \| `unavailable` |
| `electricity_kwh_delta` | DOUBLE PRECISION NULL | upgrade − baseline; NULL if either side missing |
| `natural_gas_therm_delta` | DOUBLE PRECISION NULL | |
| `total_mbtu_delta` | DOUBLE PRECISION NULL | |
| `notes` | TEXT | Why deltas are NULL, if they are |

There is **no** `savings_percent` column in v1. BPI-2400 §4.3 equivalent-energy percent is a later, regulated calculation and must not be faked.

### `utility_histories`

One current bill set per home (replaced on save).

| Column | Type | Notes |
| --- | --- | --- |
| `id` | UUID PK | |
| `home_id` | UUID FK UNIQUE | |
| `as_of` | TEXT | ISO date used for the “recent read” gate |
| `periods` | JSONB | `{start_date, end_date, fuel, usage, unit, read_type, atypical}` |
| `quality` | JSONB | Gate result + gaps; never a compliance certificate |
| `created_at` | TIMESTAMPTZ | |

### `calibration_runs`

| Column | Type | Notes |
| --- | --- | --- |
| `id` | UUID PK | |
| `home_id` / `utility_history_id` | UUID FK | |
| `baseline_job_id` | UUID NULL | Job whose annual totals were compared |
| `adjusted_model_id` / `adjusted_job_id` | UUID NULL | Only if permitted adjustments were applied and re-run |
| `model_label` | TEXT | `uncalibrated` \| `calibrated` |
| `qualification` | TEXT | `none` \| `preliminary_not_certified` |
| `run_status` | TEXT | never `bpi_2400_calibrated` |
| `compliance_claim` | TEXT | always `not_bpi_2400_calibrated` |
| `residuals` / `proposed_adjustments` / `applied_adjustments` / `gaps` | JSONB | |
| `notes` | TEXT | |

### `package_proposals`

Seven attic / air-sealing / HPWH combinations. Each row points at a real upgrade job.

| Column | Type | Notes |
| --- | --- | --- |
| `measures` | JSONB | subset of `attic`, `air_sealing`, `hpwh` |
| `electricity_kwh_delta` etc. | DOUBLE PRECISION NULL | NULL unless both jobs parsed EnergyPlus output |
| `notes` | TEXT | states that no percentage was added |

### `program_applications`

One current application payload per home + rule pack. Does not mutate `building_models`.

| Column | Type | Notes |
| --- | --- | --- |
| `pack_id` | TEXT | e.g. `nc-homes-v2.0-2026-02` |
| `payload` | JSONB | User-declared AMI band, measures, docs flags |

### `program_evaluations`

Immutable. A rule-pack change creates a **new** row; old rows keep `pack_version` and set `rule_pack_changed` on read.

| Column | Type | Notes |
| --- | --- | --- |
| `pack_id` / `pack_version` | TEXT | Pinned at evaluate time |
| `overall_status` | TEXT | `ineligible` \| `incomplete` \| `screen_passed_not_submittable` |
| `compliance_claim` | TEXT | always `not_doe_approved_not_submitted` |
| `portal_status` / `reservation_status` / `payment_status` | TEXT | always `not_submitted` / `not_reserved` / `not_paid` |
| `savings_percent` | DOUBLE PRECISION NULL | Site-energy from stored EnergyPlus totals only; NULL if no pair |
| `result` | JSONB | Full checks, sources, unverified list |

## Canonical `payload` (v1)

JSONB, validated by Pydantic before write.

```json
{
  "schema": "hems.building/v1",
  "site": {
    "state_code": "CO",
    "postal_code": "80202",
    "azimuth_front": 180,
    "iecc_zone": "5B",
    "weather_station": "USA_CO_Denver.Intl.AP.725650_TMY3",
    "official_weather_station": "USA_CO_Boulder-Broomfield-Jefferson.County.AP.724699_TMY3",
    "weather_source": "nearest_shipped",
    "weather_epw_available": true
  },
  "construction": {
    "facility_type": "single-family detached",
    "conditioned_floor_area_ft2": 2700,
    "stories": 2,
    "stories_above_grade": 1,
    "ceiling_height_ft": 8,
    "bedrooms": 3,
    "bathrooms": 2,
    "year_built": 2006
  },
  "enclosure": {
    "ach50": 3.0,
    "wall_area_ft2": 1200,
    "wall_assembly_r": 22.7,
    "ceiling_area_ft2": 1350,
    "ceiling_assembly_r": 39.6,
    "roof_area_ft2": 1509.3,
    "attic_type": "unvented",
    "foundation_type": "conditioned_basement",
    "rim_joist_area_ft2": 115.6,
    "rim_joist_assembly_r": 13.9,
    "window_u": 0.35,
    "window_shgc": 0.44,
    "window_area_by_azimuth": { "0": 108, "90": 72, "180": 108, "270": 72 },
    "door_area_ft2": 40,
    "door_r": 4.4
  },
  "systems": {
    "heating_type": "furnace",
    "heating_fuel": "natural gas",
    "heating_efficiency_afue": 0.92,
    "heating_efficiency_hspf2": 7.0,
    "cooling_type": "central air conditioner",
    "cooling_efficiency_seer2": 13.4,
    "dhw_type": "storage water heater",
    "dhw_fuel": "electricity",
    "dhw_uef": 0.94,
    "heating_setpoint_f": 68,
    "cooling_setpoint_f": 78,
    "ductless": false,
    "duct_leakage_supply_cfm25": 81,
    "duct_leakage_return_cfm25": 27
  },
  "data_source": {
    "ach50": "user",
    "heating_efficiency_afue": "user",
    "cooling_efficiency_seer2": "user",
    "rim_joist_area_ft2": "user",
    "duct_leakage_supply_cfm25": "user",
    "appliances": "software",
    "lighting": "software"
  }
}
```

`data_source` values: `user` | `default` | `measured` | `software`. Payload `software` marks appliances/lighting we do not collect yet. After a successful run, provider `in.xml` nodes with `dataSource='software'` are stored on `energy_results.software_defaults` and shown in the UI. Duct-leakage measures mark CFM25 as `measured`.

## Indexes

- `homes (postal_code)`
- `building_models (home_id, version DESC)`
- `simulation_jobs (status, queued_at)` — worker poll
- `simulation_jobs (home_id, job_type)`
- `simulation_artifacts (job_id, kind)`

## What is intentionally absent

| Future table | Why not now |
| --- | --- |
| Green Button Connect My Data | Port only; Download My Data parser is later |
| BPI-2400 acceptance / G14 CVRMSE | Scaffolding is not acceptance; G14 is paid |
| `doe_test_runs` | HOMES verification is a later program milestone |
| `tenants` / `users` | Single-operator v1 |
| `crm_external_refs` | Ports only |
| AHRI ratings cache | License-blocked |

## Environments

| Env | Engine | Notes |
| --- | --- | --- |
| pytest | SQLite in-memory **or** PostgreSQL if `DATABASE_URL` set | Same models; JSON not JSONB-specific |
| `docker compose` | PostgreSQL 16 | Required local-dev path |
| Production (later) | PostgreSQL | Artifacts on object storage |

Do not put energy result fixtures into the homes database as if they were simulated for that address.
