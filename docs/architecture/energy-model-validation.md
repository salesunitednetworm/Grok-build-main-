# Energy model validation

Validation is layered. Passing a layer never implies DOE, BPI, ACCA, or RESNET approval of this product.

## Layers

```
1. Canonical domain rules     (always, in our API)
2. HPXML structural emit      (always, after generate)
3. HPXML XSD + EP Schematron  (when OpenStudio-HPXML tree is installed)
4. EnergyPlus / OS-HPXML run  (when CLI is installed)
5. BPI-2400 constraints       (not in this slice)
6. BPI-2400 calibration       (not in this slice)
7. DOE HOMES software tests   (not in this slice; product-level)
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
| ZIP | 5 digits | Weather later |
| Window areas | ≥ 0; sum ≤ wall area × 0.95 | Geometry sanity |

We **do not copy** BPI-2400 Table 3.4 numeric limits into docs or code as if we own them. When the constraint engine is built, implement from the official PDF and cite the section, without republishing the table.

`data_source = measured` fields are accepted in v1 but not yet locked against calibration edits (there is no calibrator).

## Layer 2 — HPXML emit checks

After generation, before persist:

- Well-formed XML
- Root `HPXML` namespace `http://hpxmlonline.com/2025/12`
- `schemaVersion` `5.0` (v5.0-rc1 documents use this on the official 1.12.0 sample)
- Present: SoftwareInfo, Building, BuildingSummary, Enclosure (infiltration + at least one wall, ceiling, window set), HVAC heating **and** cooling, DHW
- IDs unique; HVAC `DistributionSystem` idrefs resolve

These checks do **not** mean the file passed DOE’s HOMES minimum dataset (HPXML **v4** in the May 2024 procedure — a different, later export).

## Layer 3 — Official XSD / Schematron

When `OPENSTUDIO_HPXML_DIR` is set, validate with the files shipped in v1.12.0:

- `HPXMLtoOpenStudio/resources/hpxml_schema/HPXML.xsd`
- `HPXMLtoOpenStudio/resources/hpxml_schematron/EPvalidator.sch`

Translate Schematron/XSD messages into `{code, field, message}` for the form. Do not dump raw Ruby backtraces into the contractor UI.

This is the **EnergyPlus use case**, not the DOE HOMES Schematron (promised in May 2024; public posting unverified as of 2026-11-02).

## Layer 4 — Engine run

A `succeeded` job means EnergyPlus returned `results_annual.json` we could parse. Warnings in `run.log` are stored, not hidden.

A missing engine is **`unavailable`**, not `failed`. Failed is reserved for a present engine that rejected the file or crashed.

## What we display after a successful run

| Output | Label | Qualification |
| --- | --- | --- |
| Annual fuel use (kWh, therm, MBtu) | Energy use | “EnergyPlus 25.2.0 via OpenStudio-HPXML 1.12.0. Not calibrated to utility bills.” |
| End uses by fuel | End use | Same. Mutually exclusive as OS-HPXML defines. |
| HVAC design loads (Btu/h) | Design load | **Preliminary.** Not ACCA-approved Manual J. Not for permit submittal. |
| Upgrade deltas | Difference | Only if both jobs `succeeded`. Absolute kWh/therm/MBtu, **not** a BPI-2400 percent. |

## What we must never show as validated savings

- Percent savings computed from defaults or marketing (“typical 20%”)
- BPI-2400 equivalent-energy percent (`kWhe` formula) until implemented from the official PDF and tested
- “HOMES eligible” / “DOE approved” / “BPI-2400 calibrated”
- Manual J / Manual S / Manual D compliance badges
- Home Energy Score
- HERS index

## Layers 5–7 — later, required for a HOMES product

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
