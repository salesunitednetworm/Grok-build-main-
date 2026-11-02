# Energy model validation

Validation is layered. Passing a layer never implies DOE, BPI, ACCA, or RESNET approval of this product.

## Layers

```
1. Canonical domain rules     (always, in our API)
2. HPXML structural emit      (always, after generate)
3. HPXML XSD + EP Schematron  (when OpenStudio-HPXML tree is installed)
4. EnergyPlus / OS-HPXML run  (when CLI is installed)
5. BPI-2400 constraints       (not implemented; table not copied)
6. BPI-2400 calibration       (scaffolding only — preliminary / not certified)
7. DOE HOMES software tests   (not in this product; no invented ASHRAE 140 pass/fail)
```

A home can be **valid for HPXML generation** and still **unsimulated**. That is expected on hosts without OpenStudio.

## Layer 1 — Canonical domain rules

Run on every save and before generate. Failures set `building_models.status = invalid` and return field errors to the UI.

| Rule | Bound (v1) | Why |
| --- | --- | --- |
| Facility type | `single-family detached` only | BPI-2400 / HPXML SF scope; MF is BuildingSync later |
| Conditioned floor area | 100–20,000 ft² | Physical sanity, not a standard table copy |
| Stories | 1–4 | Slice scope |
| Ceiling height | 7–14 ft | |
| Bedrooms | 1–10 | Occupancy defaults depend on this |
| ACH50 | 0.1–30 | Blower-door range; 3.4 constraints come later |
| Assembly R (wall, ceiling) | 1–80 | |
| Window U | 0.1–1.2 | |
| Window SHGC | 0.1–0.9 | |
| AFUE | 0.60–0.99 | Floor will later follow BPI-2400 §3.4, not invented here as “compliant” |
| SEER2 | 8–40 | |
| DHW UEF | 0.45–4.0 | Storage and HPWH |
| Heating setpoint °F | 50–80 | |
| Cooling setpoint °F | 65–90 | Heating < cooling |
| State code | USPS 2-letter | |
| ZIP | 5 digits | Maps to TMY3 via OS-HPXML `zipcode_weather_stations.csv` |
| HSPF2 | 5–16 | Heat pump / mini-split heating efficiency |
| Duct CFM25 | 0–2000 supply and return | Measured leakage; marked `data_source=measured` on the duct-leakage measure |
| Attic type | `vented` \| `unvented` | First-class enclosure |
| Foundation type | conditioned/unconditioned basement, slab, vented/unvented crawl | First-class enclosure |
| Rim joist area / R | 0–5000 ft² / 1–80 | First-class enclosure |
| Window areas | ≥ 0; sum ≤ wall area × 0.95 | Geometry sanity |

We **do not copy** BPI-2400 Table 3.4 numeric limits into docs or code as if we own them. When the constraint engine is built, implement from the official PDF and cite the section, without republishing the table.

`data_source = measured` fields are accepted and **locked against calibration edits**. The scaffolding will not adjust measured ACH50 or labeled AFUE / SEER2 / UEF. Setpoints that are not `measured` are the only auto-applied permitted adjustments.

## Layer 2 — HPXML emit checks

After generation, before persist:

- Well-formed XML
- Root `HPXML` namespace `http://hpxmlonline.com/2025/12`
- `schemaVersion` `5.0` (v5.0-rc1 documents use this on the official 1.12.0 sample)
- `Address` child order is `StateCode` then `ZipCode` (XSD rejects the reverse)
- Present: SoftwareInfo, Building, BuildingSummary, Enclosure (infiltration + at least one wall, ceiling, window set), HVAC as either `HeatPump` **or** `HeatingSystem` + `CoolingSystem`, DHW
- IDs unique; HVAC `DistributionSystem` idrefs resolve when ducts exist (ductless mini-splits omit `HVACDistribution`)

These checks do **not** mean the file passed DOE’s HOMES minimum dataset (HPXML **v4** in the May 2024 procedure — a different, later export).

## Layer 3 — Official XSD / Schematron

When `OPENSTUDIO_HPXML_DIR` is set, validate with the files shipped in v1.12.0:

- `HPXMLtoOpenStudio/resources/hpxml_schema/HPXML.xsd`
- `HPXMLtoOpenStudio/resources/hpxml_schematron/EPvalidator.sch`

Translate Schematron/XSD messages into `{code, field, message}` for the form (`app/domain/field_errors.py` keyword map onto `site.*` / `enclosure.*` / `systems.*`). Do not dump raw Ruby backtraces into the contractor UI.

XSD runs via `xmllint` when the tree is present. Schematron runs via `openstudio -e` `OpenStudio::XMLValidator` on `EPvalidator.sch` when the CLI is present (skipped in unit tests that clear `OPENSTUDIO_CLI`).

This is the **EnergyPlus use case**, not the DOE HOMES Schematron (promised in May 2024; public posting unverified as of 2026-11-02).

## Layer 4 — Engine run

A `succeeded` job means EnergyPlus returned `results_annual.json` we could parse. Warnings in `run.log` are stored on `energy_results.run_log_warnings`, not hidden. `in.xml` nodes with `dataSource='software'` are stored on `energy_results.software_defaults` and shown in the UI.

A missing engine is **`unavailable`**, not `failed`. Failed is reserved for a present engine that rejected the file or crashed.

## ZIP → TMY3 weather

`app/domain/weather.py` reads the official OS-HPXML 1.12.0 `zipcode_weather_stations.csv` (fixture CSV if the tree is absent). The official station is always stored on `site.official_weather_station`.

| Condition | `weather_source` | What EnergyPlus uses |
| --- | --- | --- |
| Official EPW is in `weather/` | `official_mapped` | That station |
| Official EPW is missing | `nearest_shipped` | Nearest shipped TMY3 by haversine on station lat/lon; labeled |
| Operator overrode the station | `user` | The user station; official still recorded |
| No mapping / no EPW | — | Job stays `unavailable`; no invented climate |

Examples on this pin: 33101 official + shipped Miami `722020`; 80202 official is Broomfield `724699` (not shipped) → Denver Intl `725650` labeled `nearest_shipped`. Downloading a missing official TMY3 is still a later gap.

## First-class single-family audit fields (started)

Canonical payload + HPXML emit now include:

- Attic `vented` / `unvented`
- Foundation `conditioned_basement` \| `unconditioned_basement` \| `slab_on_grade` \| `vented_crawlspace` \| `unvented_crawlspace`
- Rim joist area and assembly R (omitted on slab-on-grade)
- Heat pump / mini-split with HSPF2 and SEER2 (`HeatPump`, not furnace + AC). Capacities omitted so OS-HPXML software-defaults them
- Ductless mini-split (no `HVACDistribution`)
- Measured duct leakage CFM25 (supply and return)

Crawl / unconditioned basement emit `Floor1` over the foundation plus `Floor2` as the attic floor so the official geometry pattern is preserved. Heat-pump and duct-leakage scenarios re-run EnergyPlus. Dual-fuel, collected appliances/lighting, and occupancy opt-in remain later.

## What we display after a successful run

| Output | Label | Qualification |
| --- | --- | --- |
| Annual fuel use (kWh, therm, MBtu) | Energy use | “EnergyPlus 25.2.0 via OpenStudio-HPXML 1.12.0. Not calibrated to utility bills.” |
| End uses by fuel | End use | Same. Mutually exclusive as OS-HPXML defines. |
| HVAC design loads (Btu/h) | Design load | **Preliminary.** Not ACCA-approved Manual J. Not for permit submittal. |
| Upgrade deltas | Difference | Only if both jobs `succeeded`. Absolute kWh/therm/MBtu, **not** a BPI-2400 percent. |
| `dataSource='software'` defaults | Software default | From provider `in.xml`. Not a user-entered value. |
| `run.log` warning lines | Engine warning | Stored next to results; not hidden. |

## What we must never show as validated savings

- Percent savings computed from defaults or marketing (“typical 20%”)
- BPI-2400 equivalent-energy percent (`kWhe` formula) until implemented from the official PDF and tested
- “HOMES eligible” / “DOE approved” / “BPI-2400 calibrated”
- Manual J / Manual S / Manual D compliance badges
- Home Energy Score
- HERS index

## Layer 5 — BPI-2400 §3.4 constraints

**Not implemented.** The official table is copyrighted. We do not copy it into code or UI as if we own it. Domain ranges in Layer 1 are physical sanity bounds, not a claim that §3.4 is enforced.

## Layer 6 — Calibration scaffolding (preliminary / not certified)

Utility history is accepted and annualized. Residuals are **simulated annual fuel − annualized bills**. Models are labeled **`uncalibrated`** or **`calibrated`**. A `calibrated` label is always qualified **`preliminary_not_certified`**. The stored compliance claim is always `not_bpi_2400_calibrated`. There is no `bpi_2400_calibrated` status.

Implemented from the research notes (not a paste of the standard):

- Heating/cooling fuels: span ≥330 days and a read within the past year. Up to two atypical periods may be dropped.
- Permitted adjustments: heating/cooling setpoints when `data_source ≠ measured`. One-step ±1 °F heuristic only.
- Forbidden: measured leakage, labeled / nameplate AFUE, SEER2, UEF, and any field not on that permitted list.

Explicit gaps (returned on every run):

| Gap | Why |
| --- | --- |
| ASHRAE Guideline 14 CVRMSE / change-point regression | G14 is paid; we do not invent pass/fail |
| 183-day + HDD/CDD coverage path | Documented alternate; not implemented |
| Estimated-read roll-up | Counted, not rolled into the next actual |
| Delivered-fuel §3.3.1 path | Oil / LP / pellets not calibrated |
| Actual-weather bill-period simulation and TMY weather-normalization | Not implemented |
| §3.4 constraint table | Copyrighted; not copied |
| Equivalent-energy kWhe (4.3.1.i) | PDF typesetting of the fossil term was degraded; do not invent a percent |
| Systematic / GA search (§3.2.1) | Not implemented |
| OS-HPXML-Calibration helper bands (5% / 500 kWh / 5 MBtu) | Informational labels only |

This layer is **process scaffolding**, not software approval.

## Verification harness (`apps/api/tests/verification/`)

Reproducible checks with versioned JSON under `tests/verification/artifacts/`:

- HPXML emit + official 1.12.0 XSD (`xmllint`) when the tree is installed
- Baseline/post identity except ECM fields
- Fuel-specific totals from committed EnergyPlus fixtures (and live `base.xml` when the CLI is present)
- Official OS-HPXML samples `base.xml` and `base-dhw-tank-heat-pump.xml`

The harness records `ashrae_140_verdict: null`. It does **not** invent ASHRAE 140 Class II / RESNET HVAC / DSE pass/fail.

## Package optimizer

Attic R-49, air sealing to ACH50 1.5, and HPWH (type `heat pump water heater`, UEF 3.5) are combined into seven packages. Each package clones the payload, changes only those ECM fields, and **re-runs EnergyPlus**. Deltas are absolute kWh / therm / MBtu from two parsed jobs. No added percentage.

## Layers 7 — later, required for a HOMES product

From `docs/research/doe-verification-requirements.md` and `docs/research/hpxml-and-bpi-2400.md`, a modeled 50121 tool still needs:

1. BPI-2400 §3.4 input constraints in the UI (editability, warnings, overrides).
2. Detailed and simplified calibration (or documented companion methods) and DOE’s review questions all answered yes.
3. End-use reporting by fuel for heating, cooling, water heating, lighting, other appliances — **OS-HPXML already emits these**; we must keep them visible.
4. Pre/post models identical except ECMs — **v1 comparison already follows this structurally**.
5. Equivalent-energy savings with a state fossil-fuel factor.
6. HPXML **v4** export of calibrated pre, proposed upgrades, measures, calibration details, utility data — **different from** our v5.0-rc1 engine input.
7. ASHRAE 140 Class II Tier 1, RESNET HVAC, and DSE tests on DOE forms (paid ASHRAE 140 / Guideline 14).
8. Submission to `homes.rebates.software@nrel.gov` for **this** product.

Until that package exists, validation copy is: **“Model is internally consistent and (when the engine runs) simulated with EnergyPlus. This software is not on the DOE or BPI HOMES modeled-pathway lists.”**

## Upgrade comparison rules (v1)

1. Clone payload; change only `measure_payload` fields.
2. Re-validate and re-generate HPXML.
3. Two jobs, same provider pin.
4. If either job is `unavailable` or `failed`, comparison `status = unavailable` and all deltas NULL.
5. If both `succeeded`, store absolute deltas (upgrade − baseline). Negative means the upgrade used less.

That is a **scenario difference**, not a qualified savings prediction.

## Legal / copyright limits on validation text

- Do not paste BPI-2400 or ACCA tables into the UI.
- Link to official PDFs for procedures.
- HPXML schema license is **unverified**; we emit instance documents, we do not republish a forked schema under our name.
