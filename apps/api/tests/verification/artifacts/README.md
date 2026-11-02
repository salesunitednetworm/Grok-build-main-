# Verification harness artifacts

Versioned JSON written by `apps/api/tests/verification/`.

| File | What it is |
| --- | --- |
| `hpxml-schema-v0.2.0.json` | Emit checks + XSD (when the OS-HPXML 1.12.0 tree is present) |
| `baseline-post-v0.2.0.json` | ECM-only consistency for attic / air-sealing / HPWH packages |
| `fuel-totals-v0.2.0.json` | Fuel-specific parse of committed fixtures (no invented kWh) |
| `os-hpxml-samples-v0.2.0.json` | Official `base.xml` / HPWH sample schema checks and, when the engine is installed, a live EnergyPlus parse |

No file in this folder is an ASHRAE 140 or BPI-2400 pass/fail certificate. ASHRAE 140 and Guideline 14 are paid standards; this product does not invent those verdicts.
