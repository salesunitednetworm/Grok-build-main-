from __future__ import annotations

from datetime import date, datetime
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


class AddressSuggestion(BaseModel):
    id: str
    label: str
    street: str
    city: str | None = None
    state_code: str | None = Field(default=None, max_length=2)
    postal_code: str | None = None
    source: str


class AddressSuggestionList(BaseModel):
    source: str
    items: list[AddressSuggestion]


class AddressSuggestIn(BaseModel):
    query: str = Field(default="", max_length=300)


class AddressLookupIn(BaseModel):
    address: str = Field(min_length=1, max_length=300)
    street: str | None = None
    city: str | None = None
    state_code: str | None = Field(default=None, max_length=2)
    postal_code: str | None = None
    source: str | None = None
    id: str | None = None


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
    run_log_warnings: list[str] | None = None
    software_defaults: list[dict[str, str]] | None = None
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
    heating_efficiency_hspf2: float = Field(ge=5, le=16, default=8.5)
    cooling_efficiency_seer2: float = Field(ge=8, le=40, default=16.0)
    ductless: bool = False
    duct_leakage_supply_cfm25: float = Field(ge=0, le=2000, default=40.0)
    duct_leakage_return_cfm25: float = Field(ge=0, le=2000, default=15.0)


class WeatherOut(BaseModel):
    zipcode: str
    city: str
    state_code: str
    iecc_zone: str
    official_station: str
    official_station_name: str
    used_station: str
    weather_source: str
    epw_available: bool
    notes: str


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


class UtilityPeriodIn(BaseModel):
    start_date: date
    end_date: date
    fuel: str
    usage: float = Field(ge=0)
    unit: str
    read_type: str = "actual"
    atypical: bool = False


class UtilityHistoryIn(BaseModel):
    periods: list[UtilityPeriodIn]
    as_of: date | None = None


class UtilityHistoryOut(BaseModel):
    id: str
    home_id: str
    as_of: str
    periods: list[dict[str, Any]]
    quality: dict[str, Any]
    created_at: datetime


class CalibrationRequest(BaseModel):
    apply_permitted_adjustments: bool = False


class CalibrationOut(BaseModel):
    id: str
    home_id: str
    utility_history_id: str
    baseline_job_id: str | None
    adjusted_model_id: str | None
    adjusted_job_id: str | None
    model_label: str
    qualification: str
    run_status: str
    compliance_claim: str
    residuals: list[dict[str, Any]]
    proposed_adjustments: list[dict[str, Any]]
    applied_adjustments: list[dict[str, Any]]
    gaps: list[str]
    notes: str
    created_at: datetime
    adjusted_job: JobOut | None = None


class PackageOut(BaseModel):
    id: str
    home_id: str
    name: str
    measures: list[str]
    measure_payload: dict[str, Any]
    baseline_model_id: str
    upgraded_model_id: str
    baseline_job_id: str
    upgrade_job_id: str
    status: str
    electricity_kwh_delta: float | None
    natural_gas_therm_delta: float | None
    total_mbtu_delta: float | None
    notes: str | None
    created_at: datetime
    baseline_job: JobOut | None = None
    upgrade_job: JobOut | None = None


class ProgramPackOut(BaseModel):
    pack_id: str
    pack_version: str
    state_code: str
    program: str
    public_name: str
    effective_from: str | None = None
    effective_to: str | None = None
    this_product_doe_approved: bool
    named_modeling_software: str | None = None
    sources: list[dict[str, Any]] = Field(default_factory=list)
    unverified: list[str] = Field(default_factory=list)


class ProgramApplicationIn(BaseModel):
    pack_id: str
    household_size: int | None = Field(default=None, ge=1, le=20)
    ami_band: str | None = None
    ami_band_source: str = "user_declared"
    categorical_programs: list[str] = Field(default_factory=list)
    dwelling_type: str = "single-family"
    occupancy: str = "owner"
    landlord_authorization: bool = False
    primary_residence: bool | None = None
    georgia_resident: bool | None = None
    existing_home: bool = True
    new_construction: bool = False
    measures: list[str] = Field(default_factory=list)
    replacing_fuel: dict[str, str] = Field(default_factory=dict)
    first_time_appliance: dict[str, bool] = Field(default_factory=dict)
    project_cost_usd: float | None = Field(default=None, ge=0)
    prior_hear_usd: float = Field(default=0, ge=0)
    paired_homes_screen: str = "none"
    docs_present: dict[str, bool] = Field(default_factory=dict)
    blower_door_pre: bool = False
    blower_door_post: bool = False
    bills_twelve_months_all_fuels: bool = False
    energy_star_when_spec: bool | None = None
    manual_j_uploaded: bool = False
    existing_equipment_photo: bool = False
    also_applying_homes: bool = False
    also_applying_hear: bool = False
    same_measure_on_both_programs: bool = False
    scenario_id: str | None = None
    package_id: str | None = None


class ProgramApplicationOut(OrmModel):
    id: str
    home_id: str
    pack_id: str
    payload: dict[str, Any]
    created_at: datetime
    updated_at: datetime


class ProgramEvaluationOut(BaseModel):
    id: str
    home_id: str
    application_id: str
    pack_id: str
    pack_version: str
    state_code: str
    program: str
    public_name: str
    overall_status: str
    compliance_claim: str
    portal_status: str
    reservation_status: str
    payment_status: str
    this_product_doe_approved: bool
    named_modeling_software: str | None
    savings_percent: float | None
    savings_method: str | None
    savings_band: str | None
    rebate_cap_usd: float | None
    cost_share_percent: float | None
    product_caps_usd: dict[str, int]
    checks: list[dict[str, Any]]
    sources: list[dict[str, Any]]
    unverified: list[str]
    reservation_workflow: dict[str, Any]
    notes: str
    current_pack_id: str | None
    current_pack_version: str | None
    rule_pack_changed: bool
    baseline_job_id: str | None = None
    upgrade_job_id: str | None = None
    scenario_id: str | None = None
    package_id: str | None = None
    created_at: datetime


class ProjectCreate(BaseModel):
    home_id: str
    name: str | None = None


class StagePatch(BaseModel):
    stage: str
    reason: str | None = None


class ConfirmationIn(BaseModel):
    kind: str
    source: str
    reference: str


class ProposalIn(BaseModel):
    title: str
    measures: list[str] = Field(default_factory=list)
    building_model_id: str | None = None
    program_evaluation_id: str | None = None
    notes: str = ""


class SignIn(BaseModel):
    signer_name: str
    signer_email: str


class WorkOrderIn(BaseModel):
    title: str
    scope: str
    proposal_id: str | None = None


