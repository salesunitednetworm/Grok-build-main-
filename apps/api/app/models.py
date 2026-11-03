import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from app.db import Base


def _uuid() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    return datetime.now(timezone.utc)


class Home(Base):
    __tablename__ = "homes"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    address_line1: Mapped[str | None] = mapped_column(Text)
    city: Mapped[str | None] = mapped_column(Text)
    state_code: Mapped[str | None] = mapped_column(String(2))
    postal_code: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now)

    models: Mapped[list["BuildingModel"]] = relationship(back_populates="home")


class BuildingModel(Base):
    __tablename__ = "building_models"
    __table_args__ = (UniqueConstraint("home_id", "version"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    home_id: Mapped[str] = mapped_column(ForeignKey("homes.id"), nullable=False, index=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    role: Mapped[str] = mapped_column(String(32), nullable=False, default="baseline")
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="draft")
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    validation_errors: Mapped[list | None] = mapped_column(JSON)
    parent_model_id: Mapped[str | None] = mapped_column(ForeignKey("building_models.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    home: Mapped[Home] = relationship(back_populates="models")
    hpxml_documents: Mapped[list["HpxmlDocument"]] = relationship(back_populates="building_model")


class HpxmlDocument(Base):
    __tablename__ = "hpxml_documents"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    building_model_id: Mapped[str] = mapped_column(ForeignKey("building_models.id"), nullable=False)
    schema_version: Mapped[str] = mapped_column(String(32), nullable=False)
    namespace: Mapped[str] = mapped_column(Text, nullable=False)
    xml_text: Mapped[str] = mapped_column(Text, nullable=False)
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    building_model: Mapped[BuildingModel] = relationship(back_populates="hpxml_documents")


class UpgradeScenario(Base):
    __tablename__ = "upgrade_scenarios"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    home_id: Mapped[str] = mapped_column(ForeignKey("homes.id"), nullable=False)
    baseline_model_id: Mapped[str] = mapped_column(ForeignKey("building_models.id"), nullable=False)
    upgraded_model_id: Mapped[str] = mapped_column(ForeignKey("building_models.id"), nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    measure_type: Mapped[str] = mapped_column(String(64), nullable=False)
    measure_payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    comparison: Mapped["Comparison | None"] = relationship(back_populates="scenario")


class SimulationJob(Base):
    __tablename__ = "simulation_jobs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    home_id: Mapped[str] = mapped_column(ForeignKey("homes.id"), nullable=False, index=True)
    building_model_id: Mapped[str] = mapped_column(ForeignKey("building_models.id"), nullable=False)
    hpxml_document_id: Mapped[str] = mapped_column(ForeignKey("hpxml_documents.id"), nullable=False)
    provider: Mapped[str] = mapped_column(String(64), nullable=False, default="openstudio_hpxml")
    provider_version: Mapped[str | None] = mapped_column(String(32))
    job_type: Mapped[str] = mapped_column(String(32), nullable=False)
    scenario_id: Mapped[str | None] = mapped_column(ForeignKey("upgrade_scenarios.id"))
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="queued", index=True)
    unavailable_reason: Mapped[str | None] = mapped_column(Text)
    error_message: Mapped[str | None] = mapped_column(Text)
    queued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    attempt_count: Mapped[int] = mapped_column(Integer, default=0)

    artifacts: Mapped[list["SimulationArtifact"]] = relationship(back_populates="job")
    energy_result: Mapped["EnergyResult | None"] = relationship(back_populates="job")


class SimulationArtifact(Base):
    __tablename__ = "simulation_artifacts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    job_id: Mapped[str] = mapped_column(ForeignKey("simulation_jobs.id"), nullable=False, index=True)
    kind: Mapped[str] = mapped_column(String(64), nullable=False)
    content_type: Mapped[str] = mapped_column(String(128), nullable=False)
    storage_path: Mapped[str] = mapped_column(Text, nullable=False)
    byte_size: Mapped[int] = mapped_column(Integer, nullable=False)
    checksum_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    job: Mapped[SimulationJob] = relationship(back_populates="artifacts")


class EnergyResult(Base):
    __tablename__ = "energy_results"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    job_id: Mapped[str] = mapped_column(ForeignKey("simulation_jobs.id"), unique=True, nullable=False)
    source: Mapped[str] = mapped_column(String(64), nullable=False)
    total_mbtu: Mapped[float | None] = mapped_column(Float)
    electricity_mbtu: Mapped[float | None] = mapped_column(Float)
    electricity_kwh: Mapped[float | None] = mapped_column(Float)
    natural_gas_mbtu: Mapped[float | None] = mapped_column(Float)
    natural_gas_therm: Mapped[float | None] = mapped_column(Float)
    fuel_oil_mbtu: Mapped[float | None] = mapped_column(Float)
    propane_mbtu: Mapped[float | None] = mapped_column(Float)
    end_uses: Mapped[dict | None] = mapped_column(JSON)
    heating_design_load_btuh: Mapped[float | None] = mapped_column(Float)
    cooling_sensible_design_load_btuh: Mapped[float | None] = mapped_column(Float)
    loads_qualification: Mapped[str] = mapped_column(String(32), nullable=False, default="preliminary")
    raw_annual: Mapped[dict | None] = mapped_column(JSON)
    run_log_warnings: Mapped[list | None] = mapped_column(JSON)
    software_defaults: Mapped[list | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    job: Mapped[SimulationJob] = relationship(back_populates="energy_result")


class Comparison(Base):
    __tablename__ = "comparisons"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    scenario_id: Mapped[str] = mapped_column(ForeignKey("upgrade_scenarios.id"), unique=True, nullable=False)
    baseline_job_id: Mapped[str] = mapped_column(ForeignKey("simulation_jobs.id"), nullable=False)
    upgrade_job_id: Mapped[str] = mapped_column(ForeignKey("simulation_jobs.id"), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    electricity_kwh_delta: Mapped[float | None] = mapped_column(Float)
    natural_gas_therm_delta: Mapped[float | None] = mapped_column(Float)
    total_mbtu_delta: Mapped[float | None] = mapped_column(Float)
    notes: Mapped[str | None] = mapped_column(Text)

    scenario: Mapped[UpgradeScenario] = relationship(back_populates="comparison")


class UtilityHistory(Base):
    __tablename__ = "utility_histories"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    home_id: Mapped[str] = mapped_column(ForeignKey("homes.id"), unique=True, nullable=False)
    as_of: Mapped[str] = mapped_column(String(10), nullable=False)
    periods: Mapped[list] = mapped_column(JSON, nullable=False)
    quality: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class CalibrationRun(Base):
    __tablename__ = "calibration_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    home_id: Mapped[str] = mapped_column(ForeignKey("homes.id"), nullable=False, index=True)
    utility_history_id: Mapped[str] = mapped_column(ForeignKey("utility_histories.id"), nullable=False)
    baseline_job_id: Mapped[str | None] = mapped_column(ForeignKey("simulation_jobs.id"))
    adjusted_model_id: Mapped[str | None] = mapped_column(ForeignKey("building_models.id"))
    adjusted_job_id: Mapped[str | None] = mapped_column(ForeignKey("simulation_jobs.id"))
    model_label: Mapped[str] = mapped_column(String(32), nullable=False, default="uncalibrated")
    qualification: Mapped[str] = mapped_column(String(64), nullable=False, default="none")
    run_status: Mapped[str] = mapped_column(String(64), nullable=False)
    compliance_claim: Mapped[str] = mapped_column(String(64), nullable=False, default="not_bpi_2400_calibrated")
    residuals: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    proposed_adjustments: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    applied_adjustments: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    gaps: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    notes: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class PackageProposal(Base):
    __tablename__ = "package_proposals"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    home_id: Mapped[str] = mapped_column(ForeignKey("homes.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    measures: Mapped[list] = mapped_column(JSON, nullable=False)
    measure_payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    baseline_model_id: Mapped[str] = mapped_column(ForeignKey("building_models.id"), nullable=False)
    upgraded_model_id: Mapped[str] = mapped_column(ForeignKey("building_models.id"), nullable=False)
    baseline_job_id: Mapped[str] = mapped_column(ForeignKey("simulation_jobs.id"), nullable=False)
    upgrade_job_id: Mapped[str] = mapped_column(ForeignKey("simulation_jobs.id"), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    electricity_kwh_delta: Mapped[float | None] = mapped_column(Float)
    natural_gas_therm_delta: Mapped[float | None] = mapped_column(Float)
    total_mbtu_delta: Mapped[float | None] = mapped_column(Float)
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class ProgramApplication(Base):
    __tablename__ = "program_applications"
    __table_args__ = (UniqueConstraint("home_id", "pack_id"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    home_id: Mapped[str] = mapped_column(ForeignKey("homes.id"), nullable=False, index=True)
    pack_id: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now)


class ProgramEvaluation(Base):
    __tablename__ = "program_evaluations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    home_id: Mapped[str] = mapped_column(ForeignKey("homes.id"), nullable=False, index=True)
    application_id: Mapped[str] = mapped_column(ForeignKey("program_applications.id"), nullable=False)
    pack_id: Mapped[str] = mapped_column(String(64), nullable=False)
    pack_version: Mapped[str] = mapped_column(String(32), nullable=False)
    state_code: Mapped[str] = mapped_column(String(2), nullable=False)
    program: Mapped[str] = mapped_column(String(16), nullable=False)
    overall_status: Mapped[str] = mapped_column(String(64), nullable=False)
    compliance_claim: Mapped[str] = mapped_column(String(64), nullable=False, default="not_doe_approved_not_submitted")
    portal_status: Mapped[str] = mapped_column(String(32), nullable=False, default="not_submitted")
    reservation_status: Mapped[str] = mapped_column(String(32), nullable=False, default="not_reserved")
    payment_status: Mapped[str] = mapped_column(String(32), nullable=False, default="not_paid")
    savings_percent: Mapped[float | None] = mapped_column(Float)
    savings_method: Mapped[str | None] = mapped_column(String(128))
    savings_band: Mapped[str | None] = mapped_column(String(32))
    rebate_cap_usd: Mapped[float | None] = mapped_column(Float)
    cost_share_percent: Mapped[float | None] = mapped_column(Float)
    baseline_job_id: Mapped[str | None] = mapped_column(ForeignKey("simulation_jobs.id"))
    upgrade_job_id: Mapped[str | None] = mapped_column(ForeignKey("simulation_jobs.id"))
    scenario_id: Mapped[str | None] = mapped_column(ForeignKey("upgrade_scenarios.id"))
    package_id: Mapped[str | None] = mapped_column(ForeignKey("package_proposals.id"))
    result: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class ContractorProject(Base):
    __tablename__ = "contractor_projects"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    home_id: Mapped[str] = mapped_column(ForeignKey("homes.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    stage: Mapped[str] = mapped_column(String(32), nullable=False, default="lead", index=True)
    building_model_id: Mapped[str | None] = mapped_column(ForeignKey("building_models.id"))
    program_evaluation_id: Mapped[str | None] = mapped_column(ForeignKey("program_evaluations.id"))
    program_evaluation_pack_version: Mapped[str | None] = mapped_column(String(32))
    crm_ref: Mapped[dict | None] = mapped_column(JSON)
    program_submission_confirmation: Mapped[dict | None] = mapped_column(JSON)
    approval_confirmation: Mapped[dict | None] = mapped_column(JSON)
    reservation_confirmation: Mapped[dict | None] = mapped_column(JSON)
    final_submission_confirmation: Mapped[dict | None] = mapped_column(JSON)
    payment_confirmation: Mapped[dict | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now)


class StageEvent(Base):
    __tablename__ = "stage_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    project_id: Mapped[str] = mapped_column(ForeignKey("contractor_projects.id"), nullable=False, index=True)
    from_stage: Mapped[str | None] = mapped_column(String(32))
    to_stage: Mapped[str] = mapped_column(String(32), nullable=False)
    reason: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class PhotoSite(Base):
    __tablename__ = "photo_sites"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("contractor_projects.id"), nullable=False, index=True)
    home_id: Mapped[str] = mapped_column(ForeignKey("homes.id"), nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    provider: Mapped[str] = mapped_column(String(64), nullable=False)
    sidecar_uri: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class PhotoRecord(Base):
    __tablename__ = "photo_records"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    site_id: Mapped[str] = mapped_column(ForeignKey("photo_sites.id"), nullable=False, index=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("contractor_projects.id"), nullable=False)
    stage: Mapped[str] = mapped_column(String(32), nullable=False)
    tags: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    sidecar_uri: Mapped[str] = mapped_column(Text, nullable=False)
    bytes_uri: Mapped[str] = mapped_column(Text, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    provider: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class PhotoChecklistItem(Base):
    __tablename__ = "photo_checklist_items"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    project_id: Mapped[str] = mapped_column(ForeignKey("contractor_projects.id"), nullable=False, index=True)
    code: Mapped[str] = mapped_column(String(64), nullable=False)
    label: Mapped[str] = mapped_column(Text, nullable=False)
    required: Mapped[bool] = mapped_column(default=True)
    completed: Mapped[bool] = mapped_column(default=False)
    photo_id: Mapped[str | None] = mapped_column(String(36))


class ProposalRecord(Base):
    __tablename__ = "proposal_records"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    project_id: Mapped[str] = mapped_column(ForeignKey("contractor_projects.id"), nullable=False, index=True)
    building_model_id: Mapped[str | None] = mapped_column(ForeignKey("building_models.id"))
    program_evaluation_id: Mapped[str | None] = mapped_column(ForeignKey("program_evaluations.id"))
    program_evaluation_pack_version: Mapped[str | None] = mapped_column(String(32))
    title: Mapped[str] = mapped_column(Text, nullable=False)
    measures: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="draft")
    envelope_id: Mapped[str | None] = mapped_column(String(64))
    envelope_status: Mapped[str | None] = mapped_column(String(32))
    notes: Mapped[str] = mapped_column(Text, nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class WorkOrder(Base):
    __tablename__ = "work_orders"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    project_id: Mapped[str] = mapped_column(ForeignKey("contractor_projects.id"), nullable=False, index=True)
    proposal_id: Mapped[str | None] = mapped_column(ForeignKey("proposal_records.id"))
    building_model_id: Mapped[str | None] = mapped_column(ForeignKey("building_models.id"))
    program_evaluation_id: Mapped[str | None] = mapped_column(ForeignKey("program_evaluations.id"))
    program_evaluation_pack_version: Mapped[str | None] = mapped_column(String(32))
    title: Mapped[str] = mapped_column(Text, nullable=False)
    scope: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="draft")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
