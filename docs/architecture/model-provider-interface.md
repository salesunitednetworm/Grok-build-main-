# Model provider interface

The product owns a **canonical building model**. Simulation engines are replaceable adapters behind `ModelProvider`. The first and only production adapter in this revision is **OpenStudio-HPXML v1.12.0**.

This is not a license to call vendor engines (OptiMiser, Snugg, HomeBoost). Those would be separate adapters with commercial contracts. ResStock is not a per-home provider.

## Why an interface

- HPXML is a transfer language, not our database (`docs/research/hpxml-and-bpi-2400.md`).
- OpenStudio-HPXML is the residential EnergyPlus adapter, not the product (`docs/research/openstudio-hpxml.md`).
- Competitors hide engines; we publish the pin and the command we run (`docs/research/competitor-matrix.md`).
- PreSite Pro is a **photo** port, not a model provider. Do not route building physics through it.

## Protocol

```
ModelProvider
  id: str                         # "openstudio_hpxml"
  display_name: str
  engine_versions: EnginePin      # OS-HPXML / OpenStudio / EnergyPlus / HPXML schema

  generate_input(model: CanonicalBuilding) -> ProviderInput
      # HPXML v5.0-rc1 XML for this adapter

  validate_input(input: ProviderInput) -> ProviderValidation
      # XSD + EnergyPlus Schematron when the measure tree is on disk
      # otherwise structural checks we can run without OpenStudio

  is_available() -> Availability
      # CLI exists, OS-HPXML dir exists, weather policy satisfied

  run(job: SimulationJob, input: ProviderInput, workdir: Path) -> ProviderRun
      # succeeded | failed | unavailable
      # never invents annual energy

  parse_annual_results(results_annual_json: bytes) -> ParsedAnnual
      # Map documented keys only; missing keys stay None
```

`ProviderRun.energy` is populated only when `status == succeeded` and parse found documented keys. `unavailable` means “we did not simulate,” not “zero use.”

## Pinned engine (production)

| Component | Version | Role |
| --- | --- | --- |
| OpenStudio-HPXML | **v1.12.0** (2026-05-14) | Residential Measures + `run_simulation.rb` |
| OpenStudio CLI | **3.11.0** (`241b8abb4d`) | Invokes Measures; bundles EnergyPlus |
| EnergyPlus | **25.2.0** | Annual simulation |
| HPXML schema expected | **v5.0-rc1** | Namespace `http://hpxmlonline.com/2025/12` |

Do **not** float `latest`. Do **not** pair OS-HPXML 1.12.0 with EnergyPlus 26.2.0. v1.13.0 (HPXML 5.0 final) is a future pin, not this one.

Environment:

```
OPENSTUDIO_CLI=/usr/local/openstudio-3.11.0/bin/openstudio
OPENSTUDIO_HPXML_DIR=/opt/OpenStudio-HPXML-1.12.0
OPENSTUDIO_HPXML_VERSION=1.12.0
```

Documented command (cwd is `OPENSTUDIO_HPXML_DIR`; `-o` is the job workdir; OS-HPXML writes `<workdir>/run/results_annual.json`):

```
openstudio workflow/run_simulation.rb \
  -x path/to/building.xml \
  -o workdir \
  --output-format json
```

Address element order in HPXML v5.0-rc1 is `StateCode` then `ZipCode`. Reversing them fails XSD (`StateCode` unexpected after `ZipCode`).

Optional later: `--hourly fuels`, `--add-stochastic-schedules`, OSW JSON for Measure arguments. v1 does not skip validation unless we already ran Schematron ourselves.

## `OpenStudioHpxmlProvider`

### generate_input

We author HPXML ourselves (research: most product UIs do this; `BuildResidentialHPXML` does not cover every technology).

Required instance content for the EnergyPlus use case (from OS-HPXML docs + official `workflow/sample_files/base.xml`):

- `XMLTransactionHeaderInformation`, `SoftwareInfo` (our program name/version — not “OpenStudio”)
- `Building` / `Site` / `ProjectStatus`
- `BuildingSummary` (facility type, CFA, stories, bedrooms, volume)
- `ClimateandRiskZones` (IECC zone and/or weather station / ZIP)
- `Enclosure`: ACH50, attic (vented/unvented), foundation (basement / slab / crawl), rim joists, walls, ceiling/floor, windows, doors
- `Systems`: furnace + AC **or** `HeatPump` (air-to-air / mini-split with HSPF2 and SEER2); ducted `HVACDistribution` with CFM25 or omitted when ductless; DHW
- `Appliances`, `Lighting`, `MiscLoads` — defaults allowed, tagged `software` in our payload until collected

Capacities are omitted so the adapter can autosize. Autosized values appear on provider `in.xml` with `dataSource='software'` and are parsed into `energy_results.software_defaults`.

### validate_input

1. **Always:** well-formed XML, correct namespace, `schemaVersion` 5.0, required EnergyPlus-use-case elements we emit.
2. **When `OPENSTUDIO_HPXML_DIR` is present:** XSD `HPXMLtoOpenStudio/resources/hpxml_schema/HPXML.xsd` and Schematron `EPvalidator.sch`. That Schematron is the EnergyPlus use case, **not** the DOE HOMES minimum-dataset Schematron (still unverified as a public file).

### is_available / run

| Check | If missing |
| --- | --- |
| `OPENSTUDIO_CLI` executable | `unavailable` — “OpenStudio 3.11.0 CLI not installed” |
| `OPENSTUDIO_HPXML_DIR/workflow/run_simulation.rb` | `unavailable` — “OpenStudio-HPXML v1.12.0 tree not installed” |
| Weather (EPW after ZIP→TMY3 mapping) | `unavailable` or provider `failed` from `run.log` — do not invent climate. Official station is always reported; nearest shipped TMY3 is labeled when the official EPW is not in `weather/`. |

On success, collect at least:

| Artifact | Kind we store |
| --- | --- |
| Input XML we wrote | `hpxml_input` |
| `in.xml` | `in_xml` |
| `results_annual.json` | `results_annual_json` |
| `run.log` | `run_log` |

Warning lines from `run.log` are stored on the energy row. `results_design_load_details.*` may be stored later. Values from it stay **preliminary**.

### parse_annual_results

Map only keys documented in [OS-HPXML v1.12.0 workflow outputs](https://openstudio-hpxml.readthedocs.io/en/v1.12.0/workflow_outputs.html):

- `Energy Use: Total (MBtu)` / `Net (MBtu)`
- `Fuel Use: {Electricity, Natural Gas, Fuel Oil, Propane, …}: Total (MBtu)`
- `End Use: {Fuel}: {End use} (MBtu)` — mutually exclusive
- `HVAC Design Load: Heating: Total (Btu/h)`
- `HVAC Design Load: Cooling Sensible: Total (Btu/h)`

Accept flat keys or section-nested JSON. Unknown keys remain in `raw_annual`. **Tests use a fixture shaped like this file. Tests must not write those fixture numbers onto a home as if EnergyPlus ran.**

Electricity display: `kWh = MBtu × 1,000,000 / 3,412`.  
Natural gas display: `therm = MBtu × 10`.

## Unavailable contract (this environment)

If the CLI, 1.12.0 tree, or weather file is missing, the adapter **must** still:

- Generate and persist HPXML
- Enqueue and finish jobs as `unavailable`
- Store the input XML artifact
- Leave `energy_results` empty
- Refuse comparison deltas

On a host with the pinned CLI (Ubuntu 24.04 tarball at `/usr/local/openstudio-3.11.0` plus `/opt/OpenStudio-HPXML-1.12.0`), the same interface persists parsed EnergyPlus kWh. Docker Compose `--profile simulator` is the container equivalent. Do not invent kWh when the engine is absent.

## Future providers (not implemented)

| Adapter | When | Notes |
| --- | --- | --- |
| OS-HPXML-Calibration | After bill ingest | Authors say incomplete vs BPI-2400 |
| Home Energy Score API | Only with DOE API terms | Annex E example, not a mandate |
| OptiMiser / Snugg | Never without a contract | Commercial engine |
| ResStock | Market analysis only | Extra license clause; not field data |
| Raw EnergyPlus 26.2.0 | No | Version skew; no HPXML |

## Naming and legal

- Provider `display_name` may say “OpenStudio-HPXML v1.12.0 (EnergyPlus 25.2.0)” as an **unmodified** engine attribution.
- Product chrome says “Home Energy Modeling Platform.”
- UI copy: “Powered by EnergyPlus version 25.2.0” is the documented unmodified attribution form. Do not put EnergyPlus or OpenStudio in the product name.
- Modified forks cannot use those marks.

## PreSite Pro boundary

`JobPhotoPort` is a different interface (`createJobSite`, `addPhoto`, sidecar `presitepro.photo/v1`). Photos may later attach to a `home_id`. They never implement `ModelProvider`. This repo does not clone PreSite Pro.
