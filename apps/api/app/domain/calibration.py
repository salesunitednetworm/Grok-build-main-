"""BPI-2400 *scaffolding*: residuals and permitted adjustments.

This is a preliminary / not-certified workflow. It never emits a
`bpi_2400_calibrated` status or a compliance claim.
"""

from __future__ import annotations

import copy
from typing import Any, Literal

from pydantic import BaseModel, Field

from app.domain.bills import FuelAnnual, HistoryQuality, STANDARD_GAPS
from app.domain.results import ParsedAnnual

ModelLabel = Literal["uncalibrated", "calibrated"]
Qualification = Literal["none", "preliminary_not_certified"]
RunStatus = Literal[
    "uncalibrated",
    "bills_accepted_uncalibrated",
    "residuals_computed_uncalibrated",
    "preliminarily_adjusted",
]

# §3.2.1: prioritize uncertain, high-influence operational inputs.
# Do not adjust measurements or labeled / nameplate efficiencies.
PERMITTED_FIELDS = (
    "systems.heating_setpoint_f",
    "systems.cooling_setpoint_f",
)
NEVER_ADJUST = (
    "enclosure.ach50",
    "systems.heating_efficiency_afue",
    "systems.cooling_efficiency_seer2",
    "systems.dhw_uef",
)

# OpenStudio-HPXML-Calibration README helper bands — informational only.
HELPER_BIAS = 0.05
HELPER_ELEC_KWH = 500.0
HELPER_GAS_MBTU = 5.0

COMPLIANCE_CLAIM = "not_bpi_2400_calibrated"

CALIBRATION_GAPS = STANDARD_GAPS + [
    "No systematic / genetic-algorithm search (BPI-2400 §3.2.1). Setpoint steps of ±1 °F are a preliminary heuristic.",
    "OpenStudio-HPXML-Calibration helper bands (5% bias, 500 kWh, 5 MBtu) are informational labels only — not BPI-2400 acceptance.",
    "Monthly CVRMSE versus simulated bills is not computed (annual EnergyPlus totals only).",
]


class Residual(BaseModel):
    fuel: str
    measured_kwh: float | None = None
    simulated_kwh: float | None = None
    residual_kwh: float | None = None
    measured_therm: float | None = None
    simulated_therm: float | None = None
    residual_therm: float | None = None
    relative_bias: float | None = None
    helper_within_5pct_bias: bool | None = None
    helper_within_absolute: bool | None = None
    helper_source: str = "os_hpxml_calibration_readme_informational"
    notes: list[str] = Field(default_factory=list)


class ProposedAdjustment(BaseModel):
    field: str
    from_value: float
    to_value: float
    reason: str
    permitted: bool
    blocked_reason: str | None = None


class CalibrationAssessment(BaseModel):
    model_label: ModelLabel
    qualification: Qualification
    run_status: RunStatus
    compliance_claim: str = COMPLIANCE_CLAIM
    quality: HistoryQuality
    residuals: list[Residual]
    proposed_adjustments: list[ProposedAdjustment]
    applied_adjustments: list[ProposedAdjustment]
    gaps: list[str]
    notes: str


def _get_path(payload: dict[str, Any], path: str) -> Any:
    cursor: Any = payload
    for part in path.split("."):
        cursor = cursor[part]
    return cursor


def _set_path(payload: dict[str, Any], path: str, value: Any) -> None:
    parts = path.split(".")
    cursor: Any = payload
    for part in parts[:-1]:
        cursor = cursor[part]
    cursor[parts[-1]] = value


def data_source_for(payload: dict[str, Any], field: str) -> str:
    sources = payload.get("data_source") or {}
    short = field.split(".")[-1]
    return str(sources.get(field) or sources.get(short) or "user")


def field_is_measured(payload: dict[str, Any], field: str) -> bool:
    return data_source_for(payload, field) == "measured"


def is_permitted_adjustment(payload: dict[str, Any], field: str) -> tuple[bool, str | None]:
    if field in NEVER_ADJUST:
        return False, "BPI-2400 §3.2.1: do not adjust measured leakage or labeled / nameplate efficiency."
    if field not in PERMITTED_FIELDS:
        return False, "Field is not on the documented permitted-adjustment list for this scaffolding."
    if field_is_measured(payload, field):
        return False, "data_source is measured; §3.2.1 forbids adjusting direct observations."
    return True, None


def compute_residuals(quality: HistoryQuality, energy: ParsedAnnual | None) -> list[Residual]:
    residuals: list[Residual] = []
    if energy is None:
        return residuals
    mapping = (
        ("electricity", "measured_kwh", "electricity_kwh", "residual_kwh", HELPER_ELEC_KWH, None),
        ("natural_gas", "measured_therm", "natural_gas_therm", "residual_therm", HELPER_GAS_MBTU * 10.0, "therm"),
    )
    for fuel, measured_attr, sim_attr, residual_attr, abs_limit, _unit in mapping:
        annual: FuelAnnual | None = quality.fuels.get(fuel)
        if annual is None:
            continue
        measured = getattr(annual, measured_attr)
        simulated = getattr(energy, sim_attr)
        residual = None if measured is None or simulated is None else simulated - measured
        bias = None
        if residual is not None and measured not in (None, 0):
            bias = residual / measured
        helper_bias = None if bias is None else abs(bias) <= HELPER_BIAS
        helper_abs = None if residual is None else abs(residual) <= abs_limit
        notes = [
            "Residual is annual EnergyPlus total minus annualized bills. Not a Guideline 14 CVRMSE.",
            "Helper bands are from the OpenStudio-HPXML-Calibration README and are informational only.",
        ]
        if not annual.qualifies_for_detailed_path:
            notes.append("This fuel did not meet the implemented 330-day quality gate.")
        item = Residual(
            fuel=fuel,
            relative_bias=bias,
            helper_within_5pct_bias=helper_bias,
            helper_within_absolute=helper_abs,
            notes=notes,
        )
        if residual_attr == "residual_kwh":
            item.measured_kwh = measured
            item.simulated_kwh = simulated
            item.residual_kwh = residual
        else:
            item.measured_therm = measured
            item.simulated_therm = simulated
            item.residual_therm = residual
        residuals.append(item)
    return residuals


def propose_setpoint_adjustments(payload: dict[str, Any], residuals: list[Residual]) -> list[ProposedAdjustment]:
    """One-step ±1 °F heuristic. Preliminary; not a systematic §3.2.1 search."""
    proposed: list[ProposedAdjustment] = []
    systems = payload.get("systems") or {}
    heating = float(systems.get("heating_setpoint_f", 68))
    cooling = float(systems.get("cooling_setpoint_f", 78))

    for residual in residuals:
        if residual.fuel == "natural_gas" and residual.residual_therm is not None:
            field = "systems.heating_setpoint_f"
            delta = -1.0 if residual.residual_therm > 0 else 1.0
            target = min(80.0, max(50.0, heating + delta))
            if target >= cooling:
                target = cooling - 1.0
            ok, blocked = is_permitted_adjustment(payload, field)
            if target == heating:
                continue
            proposed.append(
                ProposedAdjustment(
                    field=field,
                    from_value=heating,
                    to_value=target,
                    reason=(
                        "Preliminary heuristic: gas residual suggests a 1 °F heating-setpoint step. "
                        "Not a BPI-2400 systematic search."
                    ),
                    permitted=ok,
                    blocked_reason=blocked,
                )
            )
            if ok:
                heating = target
        if residual.fuel == "electricity" and residual.residual_kwh is not None:
            field = "systems.cooling_setpoint_f"
            delta = 1.0 if residual.residual_kwh > 0 else -1.0
            target = min(90.0, max(65.0, cooling + delta))
            if target <= heating:
                target = heating + 1.0
            ok, blocked = is_permitted_adjustment(payload, field)
            if target == cooling:
                continue
            proposed.append(
                ProposedAdjustment(
                    field=field,
                    from_value=cooling,
                    to_value=target,
                    reason=(
                        "Preliminary heuristic: electricity residual suggests a 1 °F cooling-setpoint step. "
                        "Not a BPI-2400 systematic search."
                    ),
                    permitted=ok,
                    blocked_reason=blocked,
                )
            )
            if ok:
                cooling = target
    return proposed


def apply_adjustments(payload: dict[str, Any], adjustments: list[ProposedAdjustment]) -> tuple[dict[str, Any], list[ProposedAdjustment]]:
    cloned = copy.deepcopy(payload)
    applied: list[ProposedAdjustment] = []
    for item in adjustments:
        ok, blocked = is_permitted_adjustment(cloned, item.field)
        if not ok or not item.permitted:
            continue
        _set_path(cloned, item.field, item.to_value)
        sources = cloned.setdefault("data_source", {})
        sources[item.field.split(".")[-1]] = "user"
        applied.append(item.model_copy(update={"permitted": True, "blocked_reason": blocked}))
    return cloned, applied


def assess_calibration(
    quality: HistoryQuality,
    energy: ParsedAnnual | None,
    payload: dict[str, Any],
    *,
    apply: bool = False,
    adjusted_energy: ParsedAnnual | None = None,
    applied: list[ProposedAdjustment] | None = None,
) -> CalibrationAssessment:
    residuals = compute_residuals(quality, adjusted_energy or energy)
    proposed = propose_setpoint_adjustments(payload, compute_residuals(quality, energy))
    applied = applied or []

    if not quality.fuels:
        status: RunStatus = "uncalibrated"
        label: ModelLabel = "uncalibrated"
        qualification: Qualification = "none"
        notes = "No utility history. Model remains uncalibrated."
    elif energy is None:
        status = "bills_accepted_uncalibrated"
        label = "uncalibrated"
        qualification = "none"
        notes = "Bills were stored but there is no parsed EnergyPlus annual result. Residuals cannot be computed. No kWh is invented."
    elif not quality.any_fuel_qualifies:
        status = "bills_accepted_uncalibrated"
        label = "uncalibrated"
        qualification = "none"
        notes = (
            "Bills were accepted. They do not meet the implemented 330-day quality gate, "
            "so the model stays uncalibrated. Residuals are informational only."
        )
    elif apply and applied and adjusted_energy is not None:
        status = "preliminarily_adjusted"
        label = "calibrated"
        qualification = "preliminary_not_certified"
        notes = (
            "Calibrated (preliminary / not certified). Permitted setpoint adjustments were applied "
            "and EnergyPlus was re-run. This is not BPI-2400 compliance."
        )
    elif apply and applied and adjusted_energy is None:
        status = "bills_accepted_uncalibrated"
        label = "uncalibrated"
        qualification = "none"
        notes = (
            "Permitted adjustments were prepared but the follow-up EnergyPlus run did not produce "
            "parsed results. Model stays uncalibrated. No kWh was invented."
        )
    else:
        status = "residuals_computed_uncalibrated"
        label = "uncalibrated"
        qualification = "none"
        notes = (
            "Residuals versus simulated annual fuels were computed. No adjustments were applied. "
            "Model remains uncalibrated."
        )

    return CalibrationAssessment(
        model_label=label,
        qualification=qualification,
        run_status=status,
        quality=quality,
        residuals=residuals,
        proposed_adjustments=proposed,
        applied_adjustments=applied,
        gaps=list(CALIBRATION_GAPS),
        notes=notes,
    )
