from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class OrmModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class HomeCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    address_line1: str | None = None
    city: str | None = None
    state_code: str | None = Field(default=None, max_length=2)
    postal_code: str | None = None


class HomeOut(HomeCreate, OrmModel):
    id: str
    created_at: datetime
    updated_at: datetime


class BuildingModelOut(OrmModel):
    id: str
    home_id: str
    version: int
    role: str
    status: str
    payload: dict[str, Any]
    validation_errors: list[dict[str, str]] | None = None
    parent_model_id: str | None = None
    created_at: datetime


class BuildingModelIn(BaseModel):
    payload: dict[str, Any]


class HpxmlOut(BaseModel):
    id: str
    building_model_id: str
    schema_version: str
    namespace: str
    xml_text: str
    generated_at: datetime
    validation_errors: list[dict[str, str]] = Field(default_factory=list)


class EnergyResultOut(OrmModel):
    id: str
    job_id: str
    source: str
    total_mbtu: float | None
    electricity_mbtu: float | None
    electricity_kwh: float | None
    natural_gas_mbtu: float | None
    natural_gas_therm: float | None
    fuel_oil_mbtu: float | None
    propane_mbtu: float | None
    end_uses: dict[str, float] | None
    heating_design_load_btuh: float | None
    cooling_sensible_design_load_btuh: float | None
    loads_qualification: str
    created_at: datetime


class ArtifactOut(OrmModel):
    id: str
    kind: str
    content_type: str
    byte_size: int
    checksum_sha256: str


class JobOut(BaseModel):
    id: str
    home_id: str
    building_model_id: str
    hpxml_document_id: str
    provider: str
    provider_version: str | None
    job_type: str
    scenario_id: str | None
    status: str
    unavailable_reason: str | None
    error_message: str | None
    queued_at: datetime
    started_at: datetime | None
    finished_at: datetime | None
    artifacts: list[ArtifactOut] = Field(default_factory=list)
    energy_result: EnergyResultOut | None = None


class ScenarioCreate(BaseModel):
    name: str = "Attic insulation upgrade"
    measure_type: str = "attic_insulation"
    ceiling_assembly_r: float = Field(ge=1, le=80, default=49.0)


class ComparisonOut(OrmModel):
    id: str
    scenario_id: str
    baseline_job_id: str
    upgrade_job_id: str
    status: str
    electricity_kwh_delta: float | None
    natural_gas_therm_delta: float | None
    total_mbtu_delta: float | None
    notes: str | None


class ScenarioOut(BaseModel):
    id: str
    home_id: str
    baseline_model_id: str
    upgraded_model_id: str
    name: str
    measure_type: str
    measure_payload: dict[str, Any]
    created_at: datetime
    comparison: ComparisonOut | None = None
    baseline_job: JobOut | None = None
    upgrade_job: JobOut | None = None


class EngineStatus(BaseModel):
    provider: str
    display_name: str
    versions: dict[str, str]
    available: bool
    reason: str | None
    regulatory: list[str]
