"use client";

import { useParams } from "next/navigation";
import { FormEvent, useEffect, useState } from "react";
import { api } from "@/lib/api";
import { formatDelta, formatEnergy } from "@/lib/format";
import type {
  BuildingModel,
  BuildingPayload,
  CalibrationRun,
  EngineStatus,
  Home,
  HpxmlDoc,
  Job,
  PackageProposal,
  ProgramEvaluation,
  ProgramPack,
  Scenario,
  UtilityHistory,
  WeatherStation,
} from "@/lib/types";

const STEPS = ["Building", "Validate", "HPXML", "Simulate", "Results", "Upgrade", "Bills", "Calibrate", "Packages", "Programs"] as const;

function setPath(payload: BuildingPayload, path: string, value: string | number) {
  const clone = structuredClone(payload);
  const parts = path.split(".");
  let cursor: Record<string, unknown> = clone as unknown as Record<string, unknown>;
  for (const part of parts.slice(0, -1)) {
    cursor = cursor[part] as Record<string, unknown>;
  }
  const last = parts[parts.length - 1];
  cursor[last] = typeof value === "number" || path.includes("azimuth") || path.includes("window") ? Number(value) : value;
  if (path.startsWith("enclosure.window_area_by_azimuth.")) {
    const az = path.split(".").pop() as string;
    clone.enclosure.window_area_by_azimuth[az] = Number(value);
  }
  return clone;
}

export default function HomeDetailPage() {
  const params = useParams<{ id: string }>();
  const id = params.id;
  const [step, setStep] = useState<(typeof STEPS)[number]>("Building");
  const [home, setHome] = useState<Home | null>(null);
  const [model, setModel] = useState<BuildingModel | null>(null);
  const [hpxml, setHpxml] = useState<HpxmlDoc | null>(null);
  const [job, setJob] = useState<Job | null>(null);
  const [scenario, setScenario] = useState<Scenario | null>(null);
  const [status, setStatus] = useState<EngineStatus | null>(null);
  const [ceilingR, setCeilingR] = useState(49);
  const [weather, setWeather] = useState<WeatherStation | null>(null);
  const [billsText, setBillsText] = useState("[]");
  const [history, setHistory] = useState<UtilityHistory | null>(null);
  const [calibration, setCalibration] = useState<CalibrationRun | null>(null);
  const [packages, setPackages] = useState<PackageProposal[]>([]);
  const [packs, setPacks] = useState<ProgramPack[]>([]);
  const [packId, setPackId] = useState("nc-homes-v2.0-2026-02");
  const [amiBand, setAmiBand] = useState("below_80");
  const [programMeasures, setProgramMeasures] = useState("attic_insulation");
  const [evaluations, setEvaluations] = useState<ProgramEvaluation[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    void (async () => {
      try {
        const [h, m, engine] = await Promise.all([api.home(id), api.model(id), api.status()]);
        setHome(h);
        setModel(m);
        setStatus(engine);
        try {
          setHpxml(await api.getHpxml(id));
        } catch {
          setHpxml(null);
        }
        const jobs = await api.jobs(id);
        if (jobs[0]) setJob(jobs[0]);
        const scenarios = await api.scenarios(id);
        if (scenarios[0]) setScenario(scenarios[0]);
        try {
          const bills = await api.getBills(id);
          setHistory(bills);
          setBillsText(JSON.stringify(bills.periods, null, 2));
        } catch {
          setHistory(null);
        }
        try {
          setCalibration(await api.getCalibration(id));
        } catch {
          setCalibration(null);
        }
        try {
          setPackages(await api.packages(id));
        } catch {
          setPackages([]);
        }
        try {
          setPacks(await api.programPacks());
        } catch {
          setPacks([]);
        }
        try {
          setEvaluations(await api.programEvaluations(id));
        } catch {
          setEvaluations([]);
        }
      } catch (err) {
        setError(err instanceof Error ? err.message : "Load failed");
      }
    })();
  }, [id]);

  const payload = model?.payload;

  async function save(event?: FormEvent) {
    event?.preventDefault();
    if (!payload) return;
    setBusy(true);
    setError(null);
    try {
      setModel(await api.saveModel(id, payload));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Save failed");
    } finally {
      setBusy(false);
    }
  }

  function field(path: string, value: string | number | boolean) {
    if (!payload) return;
    if (path === "systems.ductless") {
      const next = structuredClone(payload);
      next.systems.ductless = Boolean(value);
      setModel({ ...model!, payload: next });
      return;
    }
    setModel({ ...model!, payload: setPath(payload, path, value) });
  }

  async function validate() {
    setBusy(true);
    setError(null);
    try {
      if (payload) setModel(await api.saveModel(id, payload));
      const next = await api.validate(id);
      setModel(next);
      setStep("Validate");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Validate failed");
    } finally {
      setBusy(false);
    }
  }

  async function generate() {
    setBusy(true);
    setError(null);
    try {
      setHpxml(await api.generateHpxml(id));
      setStep("HPXML");
    } catch (err) {
      setError(err instanceof Error ? err.message : "HPXML failed");
    } finally {
      setBusy(false);
    }
  }

  async function simulate() {
    setBusy(true);
    setError(null);
    try {
      const next = await api.simulate(id);
      setJob(next);
      setStep(next.energy_result ? "Results" : "Simulate");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Simulate failed");
    } finally {
      setBusy(false);
    }
  }

  async function saveBills() {
    setBusy(true);
    setError(null);
    try {
      const periods = JSON.parse(billsText);
      setHistory(await api.saveBills(id, { as_of: "2026-01-15", periods }));
      setStep("Bills");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Bills failed");
    } finally {
      setBusy(false);
    }
  }

  async function calibrate(apply: boolean) {
    setBusy(true);
    setError(null);
    try {
      setCalibration(await api.calibrate(id, apply));
      setStep("Calibrate");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Calibration failed");
    } finally {
      setBusy(false);
    }
  }

  async function proposePackages() {
    setBusy(true);
    setError(null);
    try {
      setPackages(await api.createPackages(id));
      setStep("Packages");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Packages failed");
    } finally {
      setBusy(false);
    }
  }

  async function lookupWeather() {
    if (!payload) return;
    setBusy(true);
    setError(null);
    try {
      const station = await api.weather(payload.site.postal_code);
      setWeather(station);
      const next = structuredClone(payload);
      next.site.iecc_zone = station.iecc_zone;
      next.site.weather_station = station.used_station;
      next.site.state_code = station.state_code;
      next.site.official_weather_station = station.official_station;
      next.site.weather_source = station.weather_source;
      setModel({ ...model!, payload: next });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Weather lookup failed");
    } finally {
      setBusy(false);
    }
  }

  async function runMeasure(measure: "heat_pump" | "duct_leakage") {
    setBusy(true);
    setError(null);
    try {
      const next = await api.createScenario(
        id,
        measure === "heat_pump"
          ? {
              name: "Air-source heat pump HSPF2 8.5 / SEER2 16",
              measure_type: "heat_pump",
              heating_efficiency_hspf2: 8.5,
              cooling_efficiency_seer2: 16,
              ductless: false,
            }
          : {
              name: "Measured duct leakage 40/15 CFM25",
              measure_type: "duct_leakage",
              duct_leakage_supply_cfm25: 40,
              duct_leakage_return_cfm25: 15,
            },
      );
      setScenario(next);
      setStep("Upgrade");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Scenario failed");
    } finally {
      setBusy(false);
    }
  }

  async function runProgramScreen() {
    setBusy(true);
    setError(null);
    try {
      const next = await api.evaluateProgram(id, {
        pack_id: packId,
        ami_band: amiBand,
        measures: programMeasures.split(",").map((item) => item.trim()).filter(Boolean),
        existing_home: true,
        bills_twelve_months_all_fuels: true,
        georgia_resident: packId.startsWith("ga-"),
        scenario_id: scenario?.id,
      });
      setEvaluations((current) => [next, ...current]);
      setStep("Programs");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Program screen failed");
    } finally {
      setBusy(false);
    }
  }

  async function compare() {
    setBusy(true);
    setError(null);
    try {
      const next = await api.createScenario(id, {
        name: `Attic insulation to R-${ceilingR}`,
        measure_type: "attic_insulation",
        ceiling_assembly_r: ceilingR,
      });
      setScenario(next);
      setStep("Upgrade");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Scenario failed");
    } finally {
      setBusy(false);
    }
  }

  if (!home || !payload) {
    return <p className="fine">{error || "Loading…"}</p>;
  }

  return (
    <main>
      {status && (
        <div className="banner">
          <strong>{status.available ? "Engine ready." : "Simulation unavailable."}</strong>{" "}
          {status.reason || "EnergyPlus numbers appear only after a successful run."} Design loads,
          if present, are <strong>preliminary</strong> and not ACCA Manual J.
        </div>
      )}

      <h1>{home.name}</h1>
      <p className="fine">
        {home.city} {home.state_code} {home.postal_code} · model v{model?.version} ·{" "}
        <span className={`status ${model?.status}`}>{model?.status}</span>
      </p>

      <ul className="steps">
        {STEPS.map((item) => (
          <li key={item}>
            <button className={item === step ? "active" : ""} type="button" onClick={() => setStep(item)}>
              {item}
            </button>
          </li>
        ))}
      </ul>

      {error && <p className="errors">{error}</p>}

      {step === "Building" && (
        <form className="card" onSubmit={save}>
          <h2>Building data</h2>
          <p className="fine">
            Canonical model. Appliances and lighting are OS-HPXML <code>dataSource=software</code> defaults until
            collected. Current sources:{" "}
            {Object.entries(payload.data_source)
              .map(([key, value]) => `${key}=${value}`)
              .join(", ") || "none"}
            .
          </p>
          <h3>Site</h3>
          <div className="grid">
            <label>
              State
              <input value={payload.site.state_code} onChange={(e) => field("site.state_code", e.target.value)} />
            </label>
            <label>
              ZIP
              <input value={payload.site.postal_code} onChange={(e) => field("site.postal_code", e.target.value)} />
            </label>
            <label>
              IECC zone
              <input value={payload.site.iecc_zone} onChange={(e) => field("site.iecc_zone", e.target.value)} />
            </label>
            <label>
              Weather station
              <input value={payload.site.weather_station} onChange={(e) => field("site.weather_station", e.target.value)} />
            </label>
          </div>
          <div className="row" style={{ marginTop: 8 }}>
            <button type="button" className="secondary" disabled={busy} onClick={() => void lookupWeather()}>
              Map ZIP to TMY3
            </button>
          </div>
          {weather && (
            <p className="fine">
              Official station: {weather.official_station_name} ({weather.official_station}). Using{" "}
              {weather.used_station} ({weather.weather_source}). {weather.notes} EPW available:{" "}
              {String(weather.epw_available)}.
            </p>
          )}
          <h3>Construction</h3>
          <div className="grid">
            <label>
              Conditioned floor area (ft²)
              <input type="number" value={payload.construction.conditioned_floor_area_ft2} onChange={(e) => field("construction.conditioned_floor_area_ft2", Number(e.target.value))} />
            </label>
            <label>
              Stories
              <input type="number" step="0.5" value={payload.construction.stories} onChange={(e) => field("construction.stories", Number(e.target.value))} />
            </label>
            <label>
              Ceiling height (ft)
              <input type="number" step="0.1" value={payload.construction.ceiling_height_ft} onChange={(e) => field("construction.ceiling_height_ft", Number(e.target.value))} />
            </label>
            <label>
              Bedrooms
              <input type="number" value={payload.construction.bedrooms} onChange={(e) => field("construction.bedrooms", Number(e.target.value))} />
            </label>
            <label>
              Year built
              <input type="number" value={payload.construction.year_built} onChange={(e) => field("construction.year_built", Number(e.target.value))} />
            </label>
          </div>
          <h3>Enclosure</h3>
          <div className="grid">
            <label>
              ACH50
              <input type="number" step="0.1" value={payload.enclosure.ach50} onChange={(e) => field("enclosure.ach50", Number(e.target.value))} />
            </label>
            <label>
              Wall area (ft²)
              <input type="number" value={payload.enclosure.wall_area_ft2} onChange={(e) => field("enclosure.wall_area_ft2", Number(e.target.value))} />
            </label>
            <label>
              Wall assembly R
              <input type="number" step="0.1" value={payload.enclosure.wall_assembly_r} onChange={(e) => field("enclosure.wall_assembly_r", Number(e.target.value))} />
            </label>
            <label>
              Ceiling area (ft²)
              <input type="number" value={payload.enclosure.ceiling_area_ft2} onChange={(e) => field("enclosure.ceiling_area_ft2", Number(e.target.value))} />
            </label>
            <label>
              Ceiling assembly R
              <input type="number" step="0.1" value={payload.enclosure.ceiling_assembly_r} onChange={(e) => field("enclosure.ceiling_assembly_r", Number(e.target.value))} />
            </label>
            <label>
              Attic
              <select value={payload.enclosure.attic_type || "unvented"} onChange={(e) => field("enclosure.attic_type", e.target.value)}>
                <option value="unvented">Unvented</option>
                <option value="vented">Vented</option>
              </select>
            </label>
            <label>
              Foundation
              <select value={payload.enclosure.foundation_type} onChange={(e) => field("enclosure.foundation_type", e.target.value)}>
                <option value="conditioned_basement">Conditioned basement</option>
                <option value="unconditioned_basement">Unconditioned basement</option>
                <option value="slab_on_grade">Slab on grade</option>
                <option value="vented_crawlspace">Vented crawlspace</option>
                <option value="unvented_crawlspace">Unvented crawlspace</option>
              </select>
            </label>
            <label>
              Rim joist area (ft²)
              <input type="number" step="0.1" value={payload.enclosure.rim_joist_area_ft2 ?? 115.6} onChange={(e) => field("enclosure.rim_joist_area_ft2", Number(e.target.value))} />
            </label>
            <label>
              Rim joist R
              <input type="number" step="0.1" value={payload.enclosure.rim_joist_assembly_r ?? 13.9} onChange={(e) => field("enclosure.rim_joist_assembly_r", Number(e.target.value))} />
            </label>
            <label>
              Window U
              <input type="number" step="0.01" value={payload.enclosure.window_u} onChange={(e) => field("enclosure.window_u", Number(e.target.value))} />
            </label>
            <label>
              Window SHGC
              <input type="number" step="0.01" value={payload.enclosure.window_shgc} onChange={(e) => field("enclosure.window_shgc", Number(e.target.value))} />
            </label>
          </div>
          <h3>Systems</h3>
          <div className="grid">
            <label>
              Heating type
              <select value={payload.systems.heating_type} onChange={(e) => field("systems.heating_type", e.target.value)}>
                <option value="furnace">Furnace</option>
                <option value="heat pump">Heat pump</option>
                <option value="mini-split">Mini-split</option>
              </select>
            </label>
            <label>
              Heating AFUE
              <input type="number" step="0.01" value={payload.systems.heating_efficiency_afue} onChange={(e) => field("systems.heating_efficiency_afue", Number(e.target.value))} />
            </label>
            <label>
              Heating HSPF2
              <input type="number" step="0.1" value={payload.systems.heating_efficiency_hspf2 ?? 7} onChange={(e) => field("systems.heating_efficiency_hspf2", Number(e.target.value))} />
            </label>
            <label>
              Cooling SEER2
              <input type="number" step="0.1" value={payload.systems.cooling_efficiency_seer2} onChange={(e) => field("systems.cooling_efficiency_seer2", Number(e.target.value))} />
            </label>
            <label>
              Supply duct CFM25
              <input type="number" step="0.1" value={payload.systems.duct_leakage_supply_cfm25 ?? 81} onChange={(e) => field("systems.duct_leakage_supply_cfm25", Number(e.target.value))} />
            </label>
            <label>
              Return duct CFM25
              <input type="number" step="0.1" value={payload.systems.duct_leakage_return_cfm25 ?? 27} onChange={(e) => field("systems.duct_leakage_return_cfm25", Number(e.target.value))} />
            </label>
            <label>
              Ductless
              <select value={payload.systems.ductless ? "yes" : "no"} onChange={(e) => field("systems.ductless", e.target.value === "yes")}>
                <option value="no">No</option>
                <option value="yes">Yes</option>
              </select>
            </label>
            <label>
              DHW UEF
              <input type="number" step="0.01" value={payload.systems.dhw_uef} onChange={(e) => field("systems.dhw_uef", Number(e.target.value))} />
            </label>
            <label>
              Heat setpoint °F
              <input type="number" value={payload.systems.heating_setpoint_f} onChange={(e) => field("systems.heating_setpoint_f", Number(e.target.value))} />
            </label>
            <label>
              Cool setpoint °F
              <input type="number" value={payload.systems.cooling_setpoint_f} onChange={(e) => field("systems.cooling_setpoint_f", Number(e.target.value))} />
            </label>
          </div>
          <div className="row" style={{ marginTop: 16 }}>
            <button type="submit" disabled={busy}>
              Save draft
            </button>
            <button type="button" className="secondary" disabled={busy} onClick={() => void validate()}>
              Validate
            </button>
          </div>
        </form>
      )}

      {step === "Validate" && (
        <div className="card">
          <h2>Validation</h2>
          <p>
            Status: <span className={`status ${model?.status}`}>{model?.status}</span>
          </p>
          {model?.validation_errors?.length ? (
            <ul className="errors">
              {model.validation_errors.map((item) => (
                <li key={item.field}>
                  {item.field}: {item.message}
                </li>
              ))}
            </ul>
          ) : (
            <p>Domain rules passed. This is not DOE, BPI-2400, or ACCA approval.</p>
          )}
          <div className="row">
            <button type="button" disabled={busy || model?.status !== "valid"} onClick={() => void generate()}>
              Generate HPXML
            </button>
          </div>
        </div>
      )}

      {step === "HPXML" && (
        <div className="card">
          <h2>HPXML v5.0-rc1</h2>
          {hpxml ? (
            <>
              <p className="fine">
                {hpxml.namespace} · schema {hpxml.schema_version} · authored by this product, not BuildResidentialHPXML
              </p>
              {hpxml.validation_errors && hpxml.validation_errors.length > 0 && (
                <ul className="errors">
                  {hpxml.validation_errors.map((item) => (
                    <li key={`${item.field}-${item.message}`}>
                      {item.field}: {item.message}
                    </li>
                  ))}
                </ul>
              )}
              <pre className="xml">{hpxml.xml_text}</pre>
            </>
          ) : (
            <p className="fine">Not generated yet.</p>
          )}
          <div className="row">
            <button type="button" disabled={busy} onClick={() => void generate()}>
              Generate / refresh
            </button>
            <button type="button" className="secondary" disabled={busy || !hpxml} onClick={() => void simulate()}>
              Run simulation
            </button>
          </div>
        </div>
      )}

      {step === "Simulate" && (
        <div className="card">
          <h2>Simulation job</h2>
          {job ? (
            <>
              <p>
                Status: <span className={`status ${job.status}`}>{job.status}</span>
              </p>
              {job.unavailable_reason && <p className="banner">{job.unavailable_reason}</p>}
              {job.error_message && <p className="errors">{job.error_message}</p>}
              <p className="fine">
                Artifacts: {job.artifacts.map((item) => `${item.kind} (${item.byte_size} B)`).join(", ") || "none"}
              </p>
            </>
          ) : (
            <p className="fine">No job yet. Generate HPXML first, then run.</p>
          )}
          <div className="row">
            <button type="button" disabled={busy} onClick={() => void simulate()}>
              Queue OpenStudio-HPXML
            </button>
            <button type="button" className="secondary" onClick={() => setStep("Results")}>
              View results
            </button>
          </div>
        </div>
      )}

      {step === "Results" && (
        <div className="card">
          <h2>Energy results</h2>
          {!job?.energy_result ? (
            <p>
              No EnergyPlus annual results are stored. This screen will not invent kWh.{" "}
              {job?.unavailable_reason || "Run the simulation on a host with OpenStudio 3.11.0."}
            </p>
          ) : (
            <div className="grid">
              <div className="metric">
                Electricity
                <b>{formatEnergy(job.energy_result.electricity_kwh, "kWh")}</b>
              </div>
              <div className="metric">
                Natural gas
                <b>{formatEnergy(job.energy_result.natural_gas_therm, "therm")}</b>
              </div>
              <div className="metric">
                Total
                <b>{formatEnergy(job.energy_result.total_mbtu, "MBtu")}</b>
              </div>
              <div className="metric">
                Heating design load (preliminary)
                <b>{formatEnergy(job.energy_result.heating_design_load_btuh, "Btu/h")}</b>
              </div>
              <div className="metric">
                Cooling sensible load (preliminary)
                <b>{formatEnergy(job.energy_result.cooling_sensible_design_load_btuh, "Btu/h")}</b>
              </div>
            </div>
          )}
          <p className="fine" style={{ marginTop: 16 }}>
            Source would be {job?.energy_result?.source || "none"}. Loads qualification:{" "}
            {job?.energy_result?.loads_qualification || "n/a"}.
          </p>
          {job?.energy_result?.run_log_warnings && job.energy_result.run_log_warnings.length > 0 && (
            <div style={{ marginTop: 16 }}>
              <h3>run.log warnings</h3>
              <ul className="fine">
                {job.energy_result.run_log_warnings.map((line) => (
                  <li key={line}>{line}</li>
                ))}
              </ul>
            </div>
          )}
          {job?.energy_result?.software_defaults && job.energy_result.software_defaults.length > 0 && (
            <div style={{ marginTop: 16 }}>
              <h3>Software defaults (in.xml dataSource=software)</h3>
              <ul className="fine">
                {job.energy_result.software_defaults.slice(0, 40).map((item, index) => (
                  <li key={`${item.element}-${index}`}>
                    {item.element}
                    {item.value ? `: ${item.value}` : ""}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}

      {step === "Upgrade" && (
        <div className="card">
          <h2>Compare a measure</h2>
          <p className="fine">
            Clones the validated model and changes only the selected ECM fields. Pre/post are otherwise identical.
            Deltas appear only if both EnergyPlus jobs succeed. Heat-pump and duct-leakage cases re-run the real
            model — no added percentages.
          </p>
          <label style={{ maxWidth: 240 }}>
            Upgrade ceiling R
            <input type="number" step="0.1" value={ceilingR} onChange={(e) => setCeilingR(Number(e.target.value))} />
          </label>
          <div className="row" style={{ marginTop: 12 }}>
            <button type="button" disabled={busy} onClick={() => void compare()}>
              Attic R upgrade
            </button>
            <button type="button" className="secondary" disabled={busy} onClick={() => void runMeasure("heat_pump")}>
              Heat pump (re-run EnergyPlus)
            </button>
            <button type="button" className="secondary" disabled={busy} onClick={() => void runMeasure("duct_leakage")}>
              Duct leakage 40/15 CFM25
            </button>
          </div>
          {scenario && (
            <div style={{ marginTop: 20 }}>
              <p>
                Comparison: <span className={`status ${scenario.comparison?.status}`}>{scenario.comparison?.status}</span>
              </p>
              <div className="grid">
                <div className="metric">
                  Electricity delta
                  <b>{formatDelta(scenario.comparison?.electricity_kwh_delta, "kWh")}</b>
                </div>
                <div className="metric">
                  Gas delta
                  <b>{formatDelta(scenario.comparison?.natural_gas_therm_delta, "therm")}</b>
                </div>
                <div className="metric">
                  Total delta
                  <b>{formatDelta(scenario.comparison?.total_mbtu_delta, "MBtu")}</b>
                </div>
              </div>
              <p className="fine">{scenario.comparison?.notes}</p>
              <p className="fine">
                Baseline job {scenario.baseline_job?.status}; upgrade job {scenario.upgrade_job?.status}. No savings
                percentage is calculated in this slice.
              </p>
            </div>
          )}
        </div>
      )}

      {step === "Bills" && (
        <div className="card">
          <h2>Utility history</h2>
          <p className="fine">
            Paste monthly periods as JSON. This is billed use, not EnergyPlus output. Quality gate implements the
            documented 330-day span only. The 183-day HDD/CDD path is a cited gap.
          </p>
          <textarea value={billsText} onChange={(e) => setBillsText(e.target.value)} rows={14} className="xml" />
          <div className="row" style={{ marginTop: 12 }}>
            <button type="button" disabled={busy} onClick={() => void saveBills()}>
              Save utility history
            </button>
          </div>
          {history && (
            <p className="fine" style={{ marginTop: 12 }}>
              Gate: {history.quality.label}. Qualifies: {String(history.quality.any_fuel_qualifies)}. Not BPI-2400
              certified.
            </p>
          )}
        </div>
      )}

      {step === "Calibrate" && (
        <div className="card">
          <h2>Calibration scaffolding</h2>
          <p className="fine">
            Residuals are annual EnergyPlus totals minus annualized bills. Only documented permitted adjustments
            (setpoints that are not measured) may be applied. Labels are uncalibrated vs calibrated (preliminary / not
            certified). This is not a BPI-2400 compliance claim.
          </p>
          <div className="row">
            <button type="button" disabled={busy} onClick={() => void calibrate(false)}>
              Compute residuals
            </button>
            <button type="button" className="secondary" disabled={busy} onClick={() => void calibrate(true)}>
              Apply permitted adjustments and re-run
            </button>
          </div>
          {calibration && (
            <div style={{ marginTop: 16 }}>
              <p>
                Model: <span className={`status ${calibration.model_label}`}>{calibration.model_label}</span> ·{" "}
                {calibration.qualification} · {calibration.compliance_claim}
              </p>
              <p className="fine">{calibration.notes}</p>
              <p className="fine">Gaps: {calibration.gaps.length} documented (including G14 / 183-day / kWhe).</p>
            </div>
          )}
        </div>
      )}

      {step === "Packages" && (
        <div className="card">
          <h2>Package optimizer</h2>
          <p className="fine">
            Attic R-49, air sealing to ACH50 1.5, and HPWH UEF 3.5 — every combination re-runs EnergyPlus. No added
            percentage.
          </p>
          <div className="row">
            <button type="button" disabled={busy} onClick={() => void proposePackages()}>
              Propose packages and re-run the model
            </button>
          </div>
          {packages.map((row) => (
            <div key={row.id} style={{ marginTop: 16 }}>
              <p>
                {row.name}: <span className={`status ${row.status}`}>{row.status}</span>
              </p>
              <div className="grid">
                <div className="metric">
                  Electricity delta
                  <b>{formatDelta(row.electricity_kwh_delta, "kWh")}</b>
                </div>
                <div className="metric">
                  Gas delta
                  <b>{formatDelta(row.natural_gas_therm_delta, "therm")}</b>
                </div>
                <div className="metric">
                  Total delta
                  <b>{formatDelta(row.total_mbtu_delta, "MBtu")}</b>
                </div>
              </div>
              <p className="fine">{row.notes}</p>
            </div>
          ))}
        </div>
      )}

      {step === "Programs" && (
        <div className="card">
          <h2>NC / GA program screen</h2>
          <p className="fine">
            Versioned rule packs from published NC DEQ / Energy Saver NC and GEFA documents. This product is{" "}
            <strong>not DOE-approved</strong>. The screen does not submit, reserve, approve, or pay. HOMES
            percentages, when shown, are preliminary site-energy from stored EnergyPlus totals — not BPI-2400
            equivalent-energy.
          </p>
          <div className="grid">
            <label>
              Rule pack
              <select value={packId} onChange={(e) => setPackId(e.target.value)}>
                {packs.map((pack) => (
                  <option key={pack.pack_id} value={pack.pack_id}>
                    {pack.state_code} {pack.public_name} ({pack.pack_version})
                  </option>
                ))}
              </select>
            </label>
            <label>
              AMI band (user-declared)
              <select value={amiBand} onChange={(e) => setAmiBand(e.target.value)}>
                <option value="below_80">below 80% AMI</option>
                <option value="80_to_150">80–150% AMI</option>
                <option value="above_150">above 150% AMI</option>
              </select>
            </label>
            <label>
              Measures (comma-separated)
              <input value={programMeasures} onChange={(e) => setProgramMeasures(e.target.value)} />
            </label>
          </div>
          <div className="row" style={{ marginTop: 12 }}>
            <button type="button" disabled={busy} onClick={() => void runProgramScreen()}>
              Evaluate against pinned pack
            </button>
          </div>
          {evaluations.map((row) => (
            <div key={row.id} style={{ marginTop: 16 }}>
              <p>
                {row.public_name}: <span className={`status ${row.overall_status}`}>{row.overall_status}</span>
              </p>
              <p className="fine">
                Pack {row.pack_id} v{row.pack_version}
                {row.rule_pack_changed ? ` · current pack is now ${row.current_pack_version} (not applied to this row)` : ""}{" "}
                · {row.compliance_claim} · portal {row.portal_status} · reservation {row.reservation_status} · payment{" "}
                {row.payment_status}
              </p>
              <div className="grid">
                <div className="metric">
                  Site-energy screen
                  <b>
                    {row.savings_percent == null ? "not evaluated" : `${row.savings_percent.toFixed(1)}%`}
                  </b>
                </div>
                <div className="metric">
                  Documented cap (not awarded)
                  <b>{row.rebate_cap_usd == null ? "—" : `$${row.rebate_cap_usd}`}</b>
                </div>
              </div>
              <p className="fine">{row.notes}</p>
              <ul className="fine">
                {row.checks.map((check) => (
                  <li key={check.code}>
                    {check.status}: {check.message}
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>
      )}
    </main>
  );
}
