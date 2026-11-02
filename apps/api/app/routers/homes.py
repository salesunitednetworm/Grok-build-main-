from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import PlainTextResponse, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.domain.building import default_payload
from app.domain.weather import lookup_zip
from app.models import (
    BuildingModel,
    CalibrationRun,
    Comparison,
    EnergyResult,
    Home,
    PackageProposal,
    SimulationArtifact,
    SimulationJob,
    UpgradeScenario,
)
from app.providers import default_provider
from app.schemas import (
    BuildingModelIn,
    BuildingModelOut,
    CalibrationOut,
    CalibrationRequest,
    ComparisonOut,
    EngineStatus,
    HomeCreate,
    HomeOut,
    HpxmlOut,
    JobOut,
    PackageOut,
    ScenarioCreate,
    ScenarioOut,
    UtilityHistoryIn,
    UtilityHistoryOut,
    WeatherOut,
)
from app import services
from app.storage import read_artifact

router = APIRouter(prefix="/api/v1")


def _home(db: Session, home_id: str) -> Home:
    home = db.get(Home, home_id)
    if home is None:
        raise HTTPException(404, "home not found")
    return home


def job_out(db: Session, job: SimulationJob) -> JobOut:
    artifacts = db.scalars(select(SimulationArtifact).where(SimulationArtifact.job_id == job.id)).all()
    energy = db.scalars(select(EnergyResult).where(EnergyResult.job_id == job.id)).first()
    return JobOut(
        id=job.id,
        home_id=job.home_id,
        building_model_id=job.building_model_id,
        hpxml_document_id=job.hpxml_document_id,
        provider=job.provider,
        provider_version=job.provider_version,
        job_type=job.job_type,
        scenario_id=job.scenario_id,
        status=job.status,
        unavailable_reason=job.unavailable_reason,
        error_message=job.error_message,
        queued_at=job.queued_at,
        started_at=job.started_at,
        finished_at=job.finished_at,
        artifacts=[
            {
                "id": item.id,
                "kind": item.kind,
                "content_type": item.content_type,
                "byte_size": item.byte_size,
                "checksum_sha256": item.checksum_sha256,
            }
            for item in artifacts
        ],
        energy_result=energy,
    )


def scenario_out(db: Session, scenario: UpgradeScenario) -> ScenarioOut:
    comparison = db.scalars(select(Comparison).where(Comparison.scenario_id == scenario.id)).first()
    baseline_job = None
    upgrade_job = None
    if comparison:
        baseline_job = db.get(SimulationJob, comparison.baseline_job_id)
        upgrade_job = db.get(SimulationJob, comparison.upgrade_job_id)
    return ScenarioOut(
        id=scenario.id,
        home_id=scenario.home_id,
        baseline_model_id=scenario.baseline_model_id,
        upgraded_model_id=scenario.upgraded_model_id,
        name=scenario.name,
        measure_type=scenario.measure_type,
        measure_payload=scenario.measure_payload,
        created_at=scenario.created_at,
        comparison=ComparisonOut.model_validate(comparison) if comparison else None,
        baseline_job=job_out(db, baseline_job) if baseline_job else None,
        upgrade_job=job_out(db, upgrade_job) if upgrade_job else None,
    )


@router.get("/status", response_model=EngineStatus)
def engine_status() -> EngineStatus:
    availability = default_provider.is_available()
    return EngineStatus(
        provider=default_provider.id,
        display_name=default_provider.display_name,
        versions=default_provider.engine_versions,
        available=availability.available,
        reason=availability.reason,
        regulatory=[
            "This software is not DOE HOMES (IRA 50121) approved.",
            "EnergyPlus / Manual-style design loads are preliminary and not ACCA-approved.",
            "Results are not BPI-2400 calibrated savings.",
            "Calibration scaffolding is preliminary / not certified.",
        ],
    )


@router.get("/defaults")
def defaults() -> dict:
    return default_payload()


@router.get("/weather/{zipcode}", response_model=WeatherOut)
def weather_for_zip(zipcode: str) -> WeatherOut:
    station = lookup_zip(zipcode)
    if station is None:
        raise HTTPException(404, "ZIP is not in the OS-HPXML zipcode_weather_stations.csv table")
    return WeatherOut(
        zipcode=station.zipcode,
        city=station.city,
        state_code=station.state_code,
        iecc_zone=station.iecc_zone,
        official_station=station.official_station,
        official_station_name=station.official_station_name,
        used_station=station.used_station,
        weather_source=station.weather_source,
        epw_available=station.epw_available,
        notes=station.notes,
    )


@router.get("/homes", response_model=list[HomeOut])
def list_homes(db: Session = Depends(get_db)) -> list[Home]:
    return list(db.scalars(select(Home).order_by(Home.created_at.desc())))


@router.post("/homes", response_model=HomeOut)
def create_home(body: HomeCreate, db: Session = Depends(get_db)) -> Home:
    home = Home(**body.model_dump())
    db.add(home)
    db.commit()
    db.refresh(home)
    services.ensure_draft_model(db, home)
    return home


@router.get("/homes/{home_id}", response_model=HomeOut)
def get_home(home_id: str, db: Session = Depends(get_db)) -> Home:
    return _home(db, home_id)


@router.get("/homes/{home_id}/model", response_model=BuildingModelOut)
def get_model(home_id: str, db: Session = Depends(get_db)) -> BuildingModel:
    home = _home(db, home_id)
    model = services.ensure_draft_model(db, home)
    return model


@router.put("/homes/{home_id}/model", response_model=BuildingModelOut)
def put_model(home_id: str, body: BuildingModelIn, db: Session = Depends(get_db)) -> BuildingModel:
    home = _home(db, home_id)
    return services.save_model(db, home, body.payload, role="baseline")


@router.post("/homes/{home_id}/validate", response_model=BuildingModelOut)
def validate_home(home_id: str, db: Session = Depends(get_db)) -> BuildingModel:
    home = _home(db, home_id)
    model = services.latest_model(db, home.id)
    if model is None:
        raise HTTPException(400, "no building model")
    return services.validate_model(db, model)


@router.post("/homes/{home_id}/hpxml", response_model=HpxmlOut)
def create_hpxml(home_id: str, db: Session = Depends(get_db)) -> HpxmlOut:
    home = _home(db, home_id)
    model = services.latest_model(db, home.id)
    if model is None:
        raise HTTPException(400, "no building model")
    try:
        doc = services.generate_hpxml_document(db, model)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    return HpxmlOut(
        id=doc.id,
        building_model_id=doc.building_model_id,
        schema_version=doc.schema_version,
        namespace=doc.namespace,
        xml_text=doc.xml_text,
        generated_at=doc.generated_at,
        validation_errors=services.schema_errors_for(doc.xml_text),
    )


@router.get("/homes/{home_id}/hpxml", response_model=HpxmlOut)
def get_hpxml(home_id: str, db: Session = Depends(get_db)) -> HpxmlOut:
    home = _home(db, home_id)
    model = services.latest_model(db, home.id)
    if model is None:
        raise HTTPException(404, "no building model")
    doc = services.latest_hpxml(db, model.id)
    if doc is None:
        raise HTTPException(404, "HPXML has not been generated")
    return HpxmlOut(
        id=doc.id,
        building_model_id=doc.building_model_id,
        schema_version=doc.schema_version,
        namespace=doc.namespace,
        xml_text=doc.xml_text,
        generated_at=doc.generated_at,
    )


@router.post("/homes/{home_id}/simulate", response_model=JobOut)
def simulate(home_id: str, db: Session = Depends(get_db)) -> JobOut:
    home = _home(db, home_id)
    model = services.latest_model(db, home.id)
    if model is None:
        raise HTTPException(400, "no building model")
    try:
        job = services.enqueue_job(db, home, model, "baseline")
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    return job_out(db, job)


@router.get("/homes/{home_id}/jobs", response_model=list[JobOut])
def list_jobs(home_id: str, db: Session = Depends(get_db)) -> list[JobOut]:
    _home(db, home_id)
    jobs = db.scalars(select(SimulationJob).where(SimulationJob.home_id == home_id).order_by(SimulationJob.queued_at.desc()))
    return [job_out(db, job) for job in jobs]


@router.get("/jobs/{job_id}", response_model=JobOut)
def get_job(job_id: str, db: Session = Depends(get_db)) -> JobOut:
    job = db.get(SimulationJob, job_id)
    if job is None:
        raise HTTPException(404, "job not found")
    return job_out(db, job)


@router.get("/jobs/{job_id}/artifacts/{kind}")
def get_artifact(job_id: str, kind: str, db: Session = Depends(get_db)) -> Response:
    artifact = db.scalars(
        select(SimulationArtifact).where(SimulationArtifact.job_id == job_id, SimulationArtifact.kind == kind)
    ).first()
    if artifact is None:
        raise HTTPException(404, "artifact not found")
    data = read_artifact(artifact.storage_path)
    return Response(content=data, media_type=artifact.content_type)


@router.post("/homes/{home_id}/scenarios", response_model=ScenarioOut)
def create_scenario(home_id: str, body: ScenarioCreate, db: Session = Depends(get_db)) -> ScenarioOut:
    home = _home(db, home_id)
    if body.measure_type not in {"attic_insulation", "heat_pump", "duct_leakage"}:
        raise HTTPException(400, "supported measures: attic_insulation, heat_pump, duct_leakage")
    try:
        scenario = services.create_scenario(
            db,
            home,
            body.name,
            measure_type=body.measure_type,
            ceiling_assembly_r=body.ceiling_assembly_r,
            heating_efficiency_hspf2=body.heating_efficiency_hspf2,
            cooling_efficiency_seer2=body.cooling_efficiency_seer2,
            ductless=body.ductless,
            duct_leakage_supply_cfm25=body.duct_leakage_supply_cfm25,
            duct_leakage_return_cfm25=body.duct_leakage_return_cfm25,
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    return scenario_out(db, scenario)


@router.get("/homes/{home_id}/scenarios", response_model=list[ScenarioOut])
def list_scenarios(home_id: str, db: Session = Depends(get_db)) -> list[ScenarioOut]:
    _home(db, home_id)
    rows = db.scalars(select(UpgradeScenario).where(UpgradeScenario.home_id == home_id).order_by(UpgradeScenario.created_at.desc()))
    return [scenario_out(db, row) for row in rows]


@router.get("/scenarios/{scenario_id}", response_model=ScenarioOut)
def get_scenario(scenario_id: str, db: Session = Depends(get_db)) -> ScenarioOut:
    scenario = db.get(UpgradeScenario, scenario_id)
    if scenario is None:
        raise HTTPException(404, "scenario not found")
    return scenario_out(db, scenario)


def _calibration_out(db: Session, row: CalibrationRun) -> CalibrationOut:
    adjusted = db.get(SimulationJob, row.adjusted_job_id) if row.adjusted_job_id else None
    return CalibrationOut(
        id=row.id,
        home_id=row.home_id,
        utility_history_id=row.utility_history_id,
        baseline_job_id=row.baseline_job_id,
        adjusted_model_id=row.adjusted_model_id,
        adjusted_job_id=row.adjusted_job_id,
        model_label=row.model_label,
        qualification=row.qualification,
        run_status=row.run_status,
        compliance_claim=row.compliance_claim,
        residuals=row.residuals,
        proposed_adjustments=row.proposed_adjustments,
        applied_adjustments=row.applied_adjustments,
        gaps=row.gaps,
        notes=row.notes,
        created_at=row.created_at,
        adjusted_job=job_out(db, adjusted) if adjusted else None,
    )


def _package_out(db: Session, row: PackageProposal) -> PackageOut:
    baseline_job = db.get(SimulationJob, row.baseline_job_id)
    upgrade_job = db.get(SimulationJob, row.upgrade_job_id)
    return PackageOut(
        id=row.id,
        home_id=row.home_id,
        name=row.name,
        measures=row.measures,
        measure_payload=row.measure_payload,
        baseline_model_id=row.baseline_model_id,
        upgraded_model_id=row.upgraded_model_id,
        baseline_job_id=row.baseline_job_id,
        upgrade_job_id=row.upgrade_job_id,
        status=row.status,
        electricity_kwh_delta=row.electricity_kwh_delta,
        natural_gas_therm_delta=row.natural_gas_therm_delta,
        total_mbtu_delta=row.total_mbtu_delta,
        notes=row.notes,
        created_at=row.created_at,
        baseline_job=job_out(db, baseline_job) if baseline_job else None,
        upgrade_job=job_out(db, upgrade_job) if upgrade_job else None,
    )


@router.put("/homes/{home_id}/utility-history", response_model=UtilityHistoryOut)
def put_utility_history(home_id: str, body: UtilityHistoryIn, db: Session = Depends(get_db)) -> UtilityHistoryOut:
    home = _home(db, home_id)
    try:
        record = services.save_utility_history(
            db, home, [item.model_dump() for item in body.periods], as_of=body.as_of
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    return UtilityHistoryOut(
        id=record.id,
        home_id=record.home_id,
        as_of=record.as_of,
        periods=record.periods,
        quality=record.quality,
        created_at=record.created_at,
    )


@router.get("/homes/{home_id}/utility-history", response_model=UtilityHistoryOut)
def get_utility_history(home_id: str, db: Session = Depends(get_db)) -> UtilityHistoryOut:
    _home(db, home_id)
    record = services.latest_utility_history(db, home_id)
    if record is None:
        raise HTTPException(404, "utility history has not been saved")
    return UtilityHistoryOut(
        id=record.id,
        home_id=record.home_id,
        as_of=record.as_of,
        periods=record.periods,
        quality=record.quality,
        created_at=record.created_at,
    )


@router.post("/homes/{home_id}/calibration", response_model=CalibrationOut)
def create_calibration(home_id: str, body: CalibrationRequest, db: Session = Depends(get_db)) -> CalibrationOut:
    home = _home(db, home_id)
    try:
        row = services.run_calibration(db, home, apply=body.apply_permitted_adjustments)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    return _calibration_out(db, row)


@router.get("/homes/{home_id}/calibration", response_model=CalibrationOut)
def get_calibration(home_id: str, db: Session = Depends(get_db)) -> CalibrationOut:
    _home(db, home_id)
    row = services.latest_calibration(db, home_id)
    if row is None:
        raise HTTPException(404, "calibration has not been run")
    return _calibration_out(db, row)


@router.post("/homes/{home_id}/packages", response_model=list[PackageOut])
def create_packages(home_id: str, db: Session = Depends(get_db)) -> list[PackageOut]:
    home = _home(db, home_id)
    try:
        rows = services.create_packages(db, home)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    return [_package_out(db, row) for row in rows]


@router.get("/homes/{home_id}/packages", response_model=list[PackageOut])
def list_packages(home_id: str, db: Session = Depends(get_db)) -> list[PackageOut]:
    _home(db, home_id)
    return [_package_out(db, row) for row in services.latest_packages(db, home_id)]


@router.get("/homes/{home_id}/hpxml.xml")
def hpxml_download(home_id: str, db: Session = Depends(get_db)) -> PlainTextResponse:
    home = _home(db, home_id)
    model = services.latest_model(db, home.id)
    if model is None:
        raise HTTPException(404, "no building model")
    doc = services.latest_hpxml(db, model.id)
    if doc is None:
        raise HTTPException(404, "HPXML has not been generated")
    return PlainTextResponse(doc.xml_text, media_type="application/xml")
