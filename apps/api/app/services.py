from __future__ import annotations

from datetime import date, datetime, timezone
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.domain.bills import UtilityPeriod, assess_history
from app.domain.building import (
    apply_attic_insulation,
    apply_duct_leakage,
    apply_heat_pump,
    default_payload,
    validate_payload,
)
from app.domain.schema_check import validate_against_schematron, validate_against_xsd, xsd_available
from app.domain.weather import apply_weather
from app.domain.calibration import (
    apply_adjustments,
    assess_calibration,
)
from app.domain.comparison import compare_results
from app.domain.hpxml import inspect_hpxml
from app.domain.packages import apply_measures, enumerate_packages
from app.domain.results import ParsedAnnual
from app.models import (
    BuildingModel,
    CalibrationRun,
    Comparison,
    EnergyResult,
    Home,
    HpxmlDocument,
    PackageProposal,
    SimulationArtifact,
    SimulationJob,
    UpgradeScenario,
    UtilityHistory,
)
from app.providers.base import ProviderInput
from app.providers.openstudio_hpxml import OpenStudioHpxmlProvider
from app.storage import write_artifact

provider = OpenStudioHpxmlProvider()


def _now() -> datetime:
    return datetime.now(timezone.utc)


def latest_model(db: Session, home_id: str, role: str = "baseline") -> BuildingModel | None:
    return db.scalars(
        select(BuildingModel)
        .where(BuildingModel.home_id == home_id, BuildingModel.role == role)
        .order_by(BuildingModel.version.desc())
    ).first()


def next_version(db: Session, home_id: str) -> int:
    current = db.scalars(
        select(BuildingModel).where(BuildingModel.home_id == home_id).order_by(BuildingModel.version.desc())
    ).first()
    return 1 if current is None else current.version + 1


def ensure_draft_model(db: Session, home: Home) -> BuildingModel:
    existing = latest_model(db, home.id, "baseline")
    if existing:
        return existing
    payload = default_payload()
    if home.state_code:
        payload["site"]["state_code"] = home.state_code.upper()
    if home.postal_code:
        payload["site"]["postal_code"] = home.postal_code[:5]
    apply_weather(payload)
    model = BuildingModel(
        home_id=home.id,
        version=1,
        role="baseline",
        status="draft",
        payload=payload,
    )
    db.add(model)
    db.commit()
    db.refresh(model)
    return model


def save_model(db: Session, home: Home, payload: dict, role: str = "baseline", parent_id: str | None = None) -> BuildingModel:
    apply_weather(payload)
    building, errors = validate_payload(payload)
    status = "valid" if building else "invalid"
    record = BuildingModel(
        home_id=home.id,
        version=next_version(db, home.id),
        role=role,
        status=status,
        payload=payload if building is None else building.model_dump(by_alias=True),
        validation_errors=errors or None,
        parent_model_id=parent_id,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


def validate_model(db: Session, model: BuildingModel) -> BuildingModel:
    building, errors = validate_payload(model.payload)
    model.status = "valid" if building else "invalid"
    model.validation_errors = errors or None
    if building:
        model.payload = building.model_dump(by_alias=True)
    db.commit()
    db.refresh(model)
    return model


def generate_hpxml_document(db: Session, model: BuildingModel) -> HpxmlDocument:
    model = validate_model(db, model)
    if model.status != "valid":
        raise ValueError("building model is invalid")
    building, _ = validate_payload(model.payload)
    assert building is not None
    generated = provider.generate_input(building)
    emit_errors = inspect_hpxml(generated.xml_text)
    if emit_errors:
        raise ValueError(f"HPXML emit checks failed: {emit_errors}")
    doc = HpxmlDocument(
        building_model_id=model.id,
        schema_version=generated.schema_version,
        namespace=generated.namespace,
        xml_text=generated.xml_text,
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)
    return doc


def latest_hpxml(db: Session, model_id: str) -> HpxmlDocument | None:
    return db.scalars(
        select(HpxmlDocument)
        .where(HpxmlDocument.building_model_id == model_id)
        .order_by(HpxmlDocument.generated_at.desc())
    ).first()


def enqueue_job(
    db: Session,
    home: Home,
    model: BuildingModel,
    job_type: str,
    scenario_id: str | None = None,
) -> SimulationJob:
    doc = latest_hpxml(db, model.id) or generate_hpxml_document(db, model)
    job = SimulationJob(
        home_id=home.id,
        building_model_id=model.id,
        hpxml_document_id=doc.id,
        provider=provider.id,
        provider_version=provider.engine_versions["openstudio_hpxml"],
        job_type=job_type,
        scenario_id=scenario_id,
        status="queued",
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    if settings.worker_inline:
        process_job(db, job.id)
        db.refresh(job)
    return job


def _store_run_artifacts(db: Session, job: SimulationJob, artifacts: dict[str, Path]) -> None:
    suffixes = {
        "hpxml_input": ".xml",
        "in_xml": ".xml",
        "results_annual_json": ".json",
        "run_log": ".log",
    }
    types = {
        "hpxml_input": "application/xml",
        "in_xml": "application/xml",
        "results_annual_json": "application/json",
        "run_log": "text/plain",
    }
    for kind, path in artifacts.items():
        stored, size, digest = write_artifact(job.id, kind, path, suffixes.get(kind, ""))
        db.add(
            SimulationArtifact(
                job_id=job.id,
                kind=kind,
                content_type=types.get(kind, "application/octet-stream"),
                storage_path=stored,
                byte_size=size,
                checksum_sha256=digest,
            )
        )


def _persist_energy(db: Session, job: SimulationJob, energy: ParsedAnnual) -> None:
    db.add(
        EnergyResult(
            job_id=job.id,
            source=energy.source,
            total_mbtu=energy.total_mbtu,
            electricity_mbtu=energy.electricity_mbtu,
            electricity_kwh=energy.electricity_kwh,
            natural_gas_mbtu=energy.natural_gas_mbtu,
            natural_gas_therm=energy.natural_gas_therm,
            fuel_oil_mbtu=energy.fuel_oil_mbtu,
            propane_mbtu=energy.propane_mbtu,
            end_uses=energy.end_uses,
            heating_design_load_btuh=energy.heating_design_load_btuh,
            cooling_sensible_design_load_btuh=energy.cooling_sensible_design_load_btuh,
            loads_qualification=energy.loads_qualification,
            raw_annual=energy.raw_annual,
            run_log_warnings=energy.run_log_warnings or None,
            software_defaults=energy.software_defaults or None,
        )
    )


def schema_errors_for(xml_text: str) -> list[dict[str, str]]:
    errors: list[dict[str, str]] = []
    if xsd_available():
        errors.extend(validate_against_xsd(xml_text))
    errors.extend(validate_against_schematron(xml_text))
    return errors


def _refresh_comparison(db: Session, scenario_id: str) -> None:
    comparison = db.scalars(select(Comparison).where(Comparison.scenario_id == scenario_id)).first()
    if comparison is None:
        return
    baseline = db.get(SimulationJob, comparison.baseline_job_id)
    upgrade = db.get(SimulationJob, comparison.upgrade_job_id)
    if baseline is None or upgrade is None:
        return
    if baseline.status in {"queued", "running"} or upgrade.status in {"queued", "running"}:
        return
    base_energy = baseline.energy_result
    up_energy = upgrade.energy_result
    parsed_base = (
        ParsedAnnual(
            source=base_energy.source,
            total_mbtu=base_energy.total_mbtu,
            electricity_kwh=base_energy.electricity_kwh,
            natural_gas_therm=base_energy.natural_gas_therm,
        )
        if base_energy
        else None
    )
    parsed_up = (
        ParsedAnnual(
            source=up_energy.source,
            total_mbtu=up_energy.total_mbtu,
            electricity_kwh=up_energy.electricity_kwh,
            natural_gas_therm=up_energy.natural_gas_therm,
        )
        if up_energy
        else None
    )
    deltas = compare_results(parsed_base, parsed_up)
    comparison.status = deltas.status
    comparison.electricity_kwh_delta = deltas.electricity_kwh_delta
    comparison.natural_gas_therm_delta = deltas.natural_gas_therm_delta
    comparison.total_mbtu_delta = deltas.total_mbtu_delta
    comparison.notes = deltas.notes
    db.commit()


def process_job(db: Session, job_id: str) -> SimulationJob:
    job = db.get(SimulationJob, job_id)
    if job is None:
        raise ValueError("job not found")
    job.status = "running"
    job.started_at = _now()
    job.attempt_count += 1
    db.commit()

    doc = db.get(HpxmlDocument, job.hpxml_document_id)
    assert doc is not None
    workdir = Path(settings.artifact_root) / job.id / "work"
    run = provider.run(
        ProviderInput(xml_text=doc.xml_text, schema_version=doc.schema_version, namespace=doc.namespace),
        workdir,
    )
    _store_run_artifacts(db, job, run.artifacts)
    job.status = run.status
    job.unavailable_reason = run.unavailable_reason
    job.error_message = run.error_message
    job.finished_at = _now()
    if run.status == "succeeded" and run.energy is not None:
        _persist_energy(db, job, run.energy)
    db.commit()
    if job.scenario_id:
        _refresh_comparison(db, job.scenario_id)
    _refresh_packages_for_job(db, job.id)
    db.refresh(job)
    return job


def claim_next_job(db: Session) -> SimulationJob | None:
    job = db.scalars(select(SimulationJob).where(SimulationJob.status == "queued").order_by(SimulationJob.queued_at)).first()
    return job


def create_scenario(
    db: Session,
    home: Home,
    name: str,
    measure_type: str = "attic_insulation",
    ceiling_assembly_r: float = 49.0,
    heating_efficiency_hspf2: float = 8.5,
    cooling_efficiency_seer2: float = 16.0,
    ductless: bool = False,
    duct_leakage_supply_cfm25: float = 40.0,
    duct_leakage_return_cfm25: float = 15.0,
) -> UpgradeScenario:
    baseline = latest_model(db, home.id, "baseline")
    if baseline is None:
        raise ValueError("save and validate a baseline model first")
    baseline = validate_model(db, baseline)
    if baseline.status != "valid":
        raise ValueError("baseline model is invalid")
    if measure_type == "attic_insulation":
        upgraded_payload = apply_attic_insulation(baseline.payload, ceiling_assembly_r)
        measure_payload = {"ceiling_assembly_r": ceiling_assembly_r}
    elif measure_type == "heat_pump":
        upgraded_payload = apply_heat_pump(
            baseline.payload,
            hspf2=heating_efficiency_hspf2,
            seer2=cooling_efficiency_seer2,
            ductless=ductless,
        )
        measure_payload = {
            "heating_type": "mini-split" if ductless else "heat pump",
            "heating_efficiency_hspf2": heating_efficiency_hspf2,
            "cooling_efficiency_seer2": cooling_efficiency_seer2,
            "ductless": ductless,
        }
    elif measure_type == "duct_leakage":
        upgraded_payload = apply_duct_leakage(
            baseline.payload, duct_leakage_supply_cfm25, duct_leakage_return_cfm25
        )
        measure_payload = {
            "duct_leakage_supply_cfm25": duct_leakage_supply_cfm25,
            "duct_leakage_return_cfm25": duct_leakage_return_cfm25,
        }
    else:
        raise ValueError("supported measures: attic_insulation, heat_pump, duct_leakage")
    upgraded = save_model(db, home, upgraded_payload, role="upgrade", parent_id=baseline.id)
    if upgraded.status != "valid":
        raise ValueError("upgrade model is invalid")
    generate_hpxml_document(db, baseline)
    generate_hpxml_document(db, upgraded)
    scenario = UpgradeScenario(
        home_id=home.id,
        baseline_model_id=baseline.id,
        upgraded_model_id=upgraded.id,
        name=name,
        measure_type=measure_type,
        measure_payload=measure_payload,
    )
    db.add(scenario)
    db.commit()
    db.refresh(scenario)
    baseline_job = enqueue_job(db, home, baseline, "baseline", scenario.id)
    upgrade_job = enqueue_job(db, home, upgraded, "upgrade", scenario.id)
    comparison = Comparison(
        scenario_id=scenario.id,
        baseline_job_id=baseline_job.id,
        upgrade_job_id=upgrade_job.id,
        status="pending",
        notes="Waiting for EnergyPlus results on both jobs. No savings percentage is assumed.",
    )
    db.add(comparison)
    db.commit()
    if baseline_job.status not in {"queued", "running"} and upgrade_job.status not in {"queued", "running"}:
        _refresh_comparison(db, scenario.id)
    db.refresh(scenario)
    return scenario


def _energy_to_parsed(row: EnergyResult | None) -> ParsedAnnual | None:
    if row is None:
        return None
    return ParsedAnnual(
        source=row.source,
        total_mbtu=row.total_mbtu,
        electricity_kwh=row.electricity_kwh,
        natural_gas_therm=row.natural_gas_therm,
    )


def _periods_from_payload(raw: list[dict]) -> list[UtilityPeriod]:
    return [UtilityPeriod.model_validate(item) for item in raw]


def save_utility_history(db: Session, home: Home, periods: list[dict], as_of=None) -> UtilityHistory:
    parsed = _periods_from_payload(periods)
    quality = assess_history(parsed, as_of=as_of)
    existing = db.scalars(select(UtilityHistory).where(UtilityHistory.home_id == home.id)).first()
    payload = [item.model_dump(mode="json") for item in parsed]
    quality_dump = quality.model_dump(mode="json")
    if existing:
        existing.as_of = quality.as_of.isoformat()
        existing.periods = payload
        existing.quality = quality_dump
        db.commit()
        db.refresh(existing)
        return existing
    record = UtilityHistory(
        home_id=home.id,
        as_of=quality.as_of.isoformat(),
        periods=payload,
        quality=quality_dump,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


def latest_utility_history(db: Session, home_id: str) -> UtilityHistory | None:
    return db.scalars(select(UtilityHistory).where(UtilityHistory.home_id == home_id)).first()


def latest_succeeded_baseline_job(db: Session, home_id: str) -> SimulationJob | None:
    return db.scalars(
        select(SimulationJob)
        .where(
            SimulationJob.home_id == home_id,
            SimulationJob.job_type == "baseline",
            SimulationJob.status == "succeeded",
        )
        .order_by(SimulationJob.finished_at.desc())
    ).first()


def latest_calibration(db: Session, home_id: str) -> CalibrationRun | None:
    return db.scalars(
        select(CalibrationRun).where(CalibrationRun.home_id == home_id).order_by(CalibrationRun.created_at.desc())
    ).first()


def run_calibration(db: Session, home: Home, apply: bool) -> CalibrationRun:
    history = latest_utility_history(db, home.id)
    if history is None:
        raise ValueError("save utility history before calibration")
    baseline = latest_model(db, home.id, "baseline")
    if baseline is None:
        raise ValueError("save and validate a baseline model first")
    periods = _periods_from_payload(history.periods)
    quality = assess_history(periods, as_of=date.fromisoformat(history.as_of))
    job = latest_succeeded_baseline_job(db, home.id)
    if job is None:
        job = db.scalars(
            select(SimulationJob)
            .where(SimulationJob.home_id == home.id, SimulationJob.job_type == "baseline")
            .order_by(SimulationJob.queued_at.desc())
        ).first()
    energy = job.energy_result if job is not None else None
    parsed = _energy_to_parsed(energy)
    draft = assess_calibration(quality, parsed, baseline.payload, apply=False)
    applied = []
    adjusted_model = None
    adjusted_job = None
    adjusted_energy = None
    if apply and quality.any_fuel_qualifies and parsed is not None and draft.proposed_adjustments:
        permitted = [item for item in draft.proposed_adjustments if item.permitted]
        if permitted:
            new_payload, applied = apply_adjustments(baseline.payload, permitted)
            adjusted_model = save_model(
                db, home, new_payload, role="preliminary_calibration", parent_id=baseline.id
            )
            if adjusted_model.status != "valid":
                raise ValueError("adjusted model is invalid")
            generate_hpxml_document(db, adjusted_model)
            adjusted_job = enqueue_job(db, home, adjusted_model, "preliminary_calibration")
            adjusted_energy = _energy_to_parsed(adjusted_job.energy_result)
    assessment = assess_calibration(
        quality,
        parsed,
        baseline.payload,
        apply=apply,
        adjusted_energy=adjusted_energy,
        applied=applied,
    )
    record = CalibrationRun(
        home_id=home.id,
        utility_history_id=history.id,
        baseline_job_id=job.id if job else None,
        adjusted_model_id=adjusted_model.id if adjusted_model else None,
        adjusted_job_id=adjusted_job.id if adjusted_job else None,
        model_label=assessment.model_label,
        qualification=assessment.qualification,
        run_status=assessment.run_status,
        compliance_claim=assessment.compliance_claim,
        residuals=[item.model_dump(mode="json") for item in assessment.residuals],
        proposed_adjustments=[item.model_dump(mode="json") for item in assessment.proposed_adjustments],
        applied_adjustments=[item.model_dump(mode="json") for item in assessment.applied_adjustments],
        gaps=assessment.gaps,
        notes=assessment.notes,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


def _refresh_package(db: Session, proposal: PackageProposal) -> None:
    baseline = db.get(SimulationJob, proposal.baseline_job_id)
    upgrade = db.get(SimulationJob, proposal.upgrade_job_id)
    if baseline is None or upgrade is None:
        return
    if baseline.status in {"queued", "running"} or upgrade.status in {"queued", "running"}:
        return
    deltas = compare_results(_energy_to_parsed(baseline.energy_result), _energy_to_parsed(upgrade.energy_result))
    proposal.status = deltas.status
    proposal.electricity_kwh_delta = deltas.electricity_kwh_delta
    proposal.natural_gas_therm_delta = deltas.natural_gas_therm_delta
    proposal.total_mbtu_delta = deltas.total_mbtu_delta
    proposal.notes = (
        f"Package {proposal.name}: {deltas.notes} Combined measures were applied to the cloned payload "
        "and EnergyPlus was re-run. No percentage was added to the baseline."
    )
    db.commit()


def _refresh_packages_for_job(db: Session, job_id: str) -> None:
    rows = db.scalars(
        select(PackageProposal).where(
            (PackageProposal.baseline_job_id == job_id) | (PackageProposal.upgrade_job_id == job_id)
        )
    )
    for proposal in rows:
        _refresh_package(db, proposal)


def latest_packages(db: Session, home_id: str) -> list[PackageProposal]:
    return list(
        db.scalars(select(PackageProposal).where(PackageProposal.home_id == home_id).order_by(PackageProposal.created_at.desc()))
    )


def create_packages(db: Session, home: Home) -> list[PackageProposal]:
    baseline = latest_model(db, home.id, "baseline")
    if baseline is None:
        raise ValueError("save and validate a baseline model first")
    baseline = validate_model(db, baseline)
    if baseline.status != "valid":
        raise ValueError("baseline model is invalid")
    generate_hpxml_document(db, baseline)
    baseline_job = latest_succeeded_baseline_job(db, home.id)
    if baseline_job is None:
        baseline_job = enqueue_job(db, home, baseline, "baseline")
    created: list[PackageProposal] = []
    for spec in enumerate_packages():
        upgraded_payload = apply_measures(baseline.payload, spec.measures)
        upgraded = save_model(db, home, upgraded_payload, role="package", parent_id=baseline.id)
        if upgraded.status != "valid":
            raise ValueError(f"package {spec.name} produced an invalid model")
        generate_hpxml_document(db, upgraded)
        upgrade_job = enqueue_job(db, home, upgraded, "package", None)
        proposal = PackageProposal(
            home_id=home.id,
            name=spec.name,
            measures=list(spec.measures),
            measure_payload=spec.measure_payload,
            baseline_model_id=baseline.id,
            upgraded_model_id=upgraded.id,
            baseline_job_id=baseline_job.id,
            upgrade_job_id=upgrade_job.id,
            status="pending",
            notes=spec.notes,
        )
        db.add(proposal)
        db.commit()
        db.refresh(proposal)
        _refresh_package(db, proposal)
        db.refresh(proposal)
        created.append(proposal)
    return created
