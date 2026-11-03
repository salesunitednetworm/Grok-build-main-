# Roadmap — Home Energy Modeling Platform

Built from existing research (2026-11-02). Dates are not estimates; order is dependency order.

This product is **not** DOE HOMES approved, **not** BPI-2400 qualified, and **not** ACCA Manual J software. Those are later gates, not launch labels.

## Now — vertical slice (this milestone)

Ship in `Grok-build-main-` on a **new branch from `main`**, leaving draft PRs #1 and #2 untouched.

- Create Home → building data → validate → HPXML v5.0-rc1 → queue → OpenStudio-HPXML/EnergyPlus **or** labeled `unavailable` → store artifacts → show parsed energy **or** an empty unavailable state → one attic-insulation comparison
- Canonical model + `OpenStudioHpxmlProvider`
- PostgreSQL schema, FastAPI, Next.js, Docker Compose
- Tests for validation, HPXML emit, result parse, comparison-null-without-simulation, API
- No mock kWh, no mock % savings, no Pages deploy at repo root

## Now also — engine install (done on Ubuntu 24.04)

Pins **unchanged**: OpenStudio **3.11.0** (`241b8abb4d`), OpenStudio-HPXML **v1.12.0**, EnergyPlus **25.2.0**, HPXML **v5.0-rc1**.

- Host install: `scripts/install-openstudio.sh` (official NatLabRockies tarball + zip). Weather for Denver TMY3 ships in the 1.12.0 `weather/` folder; do not use EnergyPlus 26.2.0.
- Optional Compose `--profile simulator` builds `nrel/openstudio:3.11.0` + OS-HPXML 1.12.0 (`--scale worker=0` to replace the lite worker).
- Live default home + attic R-49 runs persist parsed annual kWh/therm. Still not DOE/BPI/ACCA approved.

## Now also — calibration scaffolding, verification harness, first optimizer (this milestone)

Still **not** BPI-2400 qualified. Still **not** an ASHRAE 140 certificate.

- Accept utility history; annualize; 330-day quality gate. Residuals = simulated annual fuel − bills.
- Apply only documented permitted adjustments (unmeasured setpoints). Never touch measured ACH50 or labeled AFUE/SEER2/UEF.
- Label models `uncalibrated` vs `calibrated` with `qualification = preliminary_not_certified`. Compliance claim is always `not_bpi_2400_calibrated`.
- Cite gaps on every run: no G14 CVRMSE, no 183-day HDD/CDD path, no delivered-fuel path, no kWhe %, no §3.4 table copy.
- Reproducible harness under `apps/api/tests/verification/` (HPXML emit + XSD, baseline/post ECM-only, fuel totals, official OS-HPXML `base.xml` / HPWH samples). Versioned artifacts. `ashrae_140_verdict` stays null.
- First optimizer: attic R-49 + air sealing ACH50 1.5 + HPWH UEF 3.5, all seven combinations, each **re-runs EnergyPlus**. Absolute deltas only.

## Now also — weather UX, validation translation, first-class audit fields (this milestone)

- ZIP → TMY3 via official OS-HPXML `zipcode_weather_stations.csv`. Official station is always stored. If that EPW is not in the 1.12.0 `weather/` folder, the nearest shipped TMY3 is used and labeled (`nearest_shipped`). Example: 33101 → Miami TMY3 (official); 80202 official is Broomfield, shipped fallback is Denver Intl.
- `in.xml` `dataSource='software'` defaults are parsed and shown next to results. Payload `data_source` includes `software` for appliances/lighting.
- XSD (xmllint) and Schematron (OpenStudio XMLValidator when the CLI is present) errors are mapped onto form fields (`{code, field, message}`).
- `run.log` warning lines are stored on `energy_results.run_log_warnings`.
- First-class fields: vented/unvented attic; conditioned/unconditioned basement; slab; vented/unvented crawl; rim joist area/R; heat pump and mini-split (HSPF2/SEER2); ductless; measured duct CFM25. Heat-pump and duct-leakage scenarios re-run EnergyPlus.

Still **not** DOE / BPI / ACCA approved.

## Now also — NC / GA HOMES/HEAR program screens (this milestone)

Stacked on the energy-platform slice. Still **not** DOE-approved. Still **not** a portal.

- Versioned rule packs for NC HOMES, NC HEAR, GA HER, and current GA HEAR (wiring/panel with HER only), each citing retrieved published sources and listing unverified items.
- Evaluations pin the pack version. Rule changes flag existing rows; they are not silently rewritten.
- Screens use stored EnergyPlus totals when a succeeded pair exists. Missing results stay `not_evaluable`. No invented kWh or BPI-2400 kWhe %.
- Never claims Neighborly / Energy Saver NC / PNNL submission, reservation, approval, or payment. Never edits the building model to force qualification.

## Now also — contractor OS slice (this milestone)

First job operating-system slice, **not** a CRM. Stacked on the NC/GA compliance branch.

- Sixteen persisted stages: Lead → Intake → Audit → Modeling → Package Optimization → Proposal → Signature → Program Submission → Approval → Reservation → Scheduling → Installation → QA → Inspection → Final Submission → Payment.
- Gated stages (`program_submission`, `approval`, `reservation`, `final_submission`, `payment`) require a recorded external confirmation (`source` + `reference`). Those fields start unset. The product never claims a portal submission, reservation, approval, or payment on its own.
- Contractor job board + homeowner “what to do next” page. Copy never invents kWh or rebate awards.
- Ports first: `JobPhotoPort` (`PreSiteProFileAdapter` disk + `presitepro.photo/v1` sidecars — not a `pre-site-pro` clone), `CrmPort` (file adapter, `pending_vendor`), `ESignPort` (file adapter, `pending_vendor` until a completed PDF is ingested). No fake vendor success.
- Photo checklist plus proposal and work-order records that pin `building_model_id` and a compliance `program_evaluation` version when one exists.

## Then — remaining single-family audit model

- Dual-fuel heat pumps as a first-class measure
- Appliances and lighting as collected fields, not only software defaults
- Stochastic occupancy as an explicit opt-in
- Download missing official TMY3 EPWs instead of nearest-shipped fallback

## Then — remaining BPI-2400 process (still not “approved”)

Scaffolding above is not this list:

- Green Button **Download My Data** parser (`UtilityUsagePort`)
- 183-day + HDD/CDD path; estimated-read roll-up; delivered-fuel §3.3.1
- ASHRAE Guideline 14 regression / CVRMSE (requires the paid standard)
- §3.4 constraint engine + override warnings (implement from the official PDF; do not paste the table)
- Operational vs asset model variants
- Equivalent-energy reporting from the official equation (read the PDF; do not invent kWhe %)
- Systematic / GA search; evaluate OpenStudio-HPXML-Calibration as a helper, not a complete implementation

Connect My Data stays per-utility onboarding. AHRI in-app ratings stay blocked until a Data Subscription.

## Then — DOE HOMES modeled-pathway package (optional business decision)

Only if we want **this** product on a 50121 list:

1. Purchase/read ASHRAE 140-2017 and Guideline 14; run Class II Tier 1 + RESNET HVAC + DSE with the specified TMY3 files.
2. HPXML **v4** program export (separate from engine v5.0-rc1 input).
3. NREL sample-home calibration using our documented method.
4. Submit to `homes.rebates.software@nrel.gov` and wait for a determination **for this product**.
5. Until the letter exists, marketing stays silent on HOMES approval.

HEAR (50122) is a different path (measures, not BPI-2400 modeled savings). Multifamily is BuildingSync / other DOE guidance.

## Contractor operations (after this slice)

File adapters shipped. Production vendors still later (`docs/research/integrations.md`):

| Port | First concrete adapter | Status |
| --- | --- | --- |
| `CrmPort` | File JSON (`pending_vendor`) | Zoho v8 **or** HighLevel v3 later |
| `JobPhotoPort` | `PreSiteProFileAdapter` | CompanyCam optional later |
| `ESignPort` | File JSON (`pending_vendor`) | Dropbox Sign or Acrobat Sign later |
| `MessagingPort` | none | Twilio or HighLevel; TCPA consent ledger required |
| `SchedulingPort` | none | After this slice |
| `EquipmentCatalogPort` | none | ENERGY STAR SODA; link out to AHRI certificates |

Do not scrape AHRI, NEEP bulk lists, MAEDbS, or utility portals.

## Explicit non-goals

| Item | Reason |
| --- | --- |
| Merge Sales United portal into energy app root | Different product; Pages workflow would publish the repo as static HTML |
| Clone `pre-site-pro` or `salesgrid-snapshot` | Isolated to this repo; photo port only |
| ResStock as the home model | Stock priors ≠ field data; extra license clause |
| EnergyPlus 26.2.0 | Wrong binary vs OpenStudio 3.11.0 |
| White-label Snugg / OptiMiser / HomeBoost | Commercial engines; approval is not transferable |
| Fake demo savings to “look complete” | Regulatory and product-trust blocker |
| Claim ACCA or DOE listing by using OS-HPXML | Listing is product-specific |

## Success for the current milestone

- Architecture files exist in the store and in the repo `docs/` tree
- A PR from a **new** `main` branch contains a runnable slice + tests + changelog
- A reviewer can create a home, see valid HPXML, and see either real EnergyPlus numbers or a clear unavailable state — never a made-up kWh
- Utility history, residual scaffolding, and package re-runs are on the same PR #3 branch, labeled preliminary / not certified
- ZIP maps to an official TMY3 (fallback labeled when the official EPW is not shipped); software defaults and `run.log` warnings appear next to results; XSD/Schematron errors map onto form fields
- Heat-pump (HSPF2/SEER2) and measured duct-leakage (CFM25) scenarios re-run EnergyPlus and persist parsed kWh — still not DOE / BPI / ACCA
- NC/GA program screens exist as versioned packs on a stacked PR; they do not submit rebates and do not claim DOE approval
- Contractor job stages persist; gated rebate/payment stages stay unused without an external confirmation; photo/CRM/e-sign ports use file adapters only
