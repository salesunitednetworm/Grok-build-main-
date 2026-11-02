"""Utility-history quality gate and annualization.

Implements the *workflow* described in BPI-2400-S-2015 v.2 §3.2.2 / §3.3.1
from the research notes — it does **not** implement the standard and does
**not** claim compliance. Official standard text we could not operationalize
is listed on every result as an explicit gap.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

Fuel = Literal["electricity", "natural_gas", "fuel_oil", "propane"]
ReadType = Literal["actual", "estimated"]
UsageUnit = Literal["kwh", "therm", "ccf", "mbtu", "gal"]

HEATING_COOLING_FUELS = frozenset({"electricity", "natural_gas"})
DELIVERED_FUELS = frozenset({"fuel_oil", "propane"})

# Documented §3.2.2 span. The 183-day + HDD/CDD alternate is *not* implemented.
MIN_DETAILED_SPAN_DAYS = 330
MIN_ALTERNATE_SPAN_DAYS = 183
MAX_DROPPED_ATYPICAL = 2
RECENT_READ_DAYS = 365

# 1 ccf treated as 1 therm only as a preliminary meter-unit stand-in.
# Heating value / weather-normalization is a cited gap.
CCF_TO_THERM_PRELIMINARY = 1.0
BTU_PER_KWH = 3412.0


class UtilityPeriod(BaseModel):
    start_date: date
    end_date: date
    fuel: Fuel
    usage: float = Field(ge=0)
    unit: UsageUnit
    read_type: ReadType = "actual"
    atypical: bool = False

    @model_validator(mode="after")
    def ordered(self) -> UtilityPeriod:
        if self.end_date < self.start_date:
            raise ValueError("end_date must be on or after start_date")
        return self


class FuelAnnual(BaseModel):
    fuel: Fuel
    period_count: int
    dropped_atypical: int
    estimated_count: int
    span_days: int | None
    most_recent_end: date | None
    measured_kwh: float | None = None
    measured_therm: float | None = None
    measured_mbtu: float | None = None
    meets_330_day_rule: bool = False
    meets_183_day_span_only: bool = False
    recent_read: bool = False
    qualifies_for_detailed_path: bool = False
    notes: list[str] = Field(default_factory=list)


class HistoryQuality(BaseModel):
    as_of: date
    fuels: dict[str, FuelAnnual]
    any_fuel_qualifies: bool
    dropped_atypical_total: int
    gaps: list[str]
    label: str


class UtilityHistoryInput(BaseModel):
    periods: list[UtilityPeriod]
    as_of: date | None = None

    @field_validator("periods")
    @classmethod
    def not_empty(cls, value: list[UtilityPeriod]) -> list[UtilityPeriod]:
        if not value:
            raise ValueError("at least one billing period is required")
        return value


STANDARD_GAPS = [
    "ASHRAE Guideline 14 change-point / linear CVRMSE is not computed (G14 is a paid standard; no invented pass/fail).",
    "183-day + HDD/CDD coverage path (BPI-2400 §3.2.2 alternate) is not implemented.",
    "Estimated reads are counted but not rolled into the next actual read.",
    "Delivered-fuel simplified path (oil / LP / pellets; §3.3.1) is not implemented.",
    "No actual-weather bill-period simulation and no TMY weather-normalization of bills.",
    "BPI-2400 §3.4 input-constraint table is not copied or enforced (copyrighted; implement from the official PDF later).",
    "Equivalent-energy kWhe (equation 4.3.1.i) is not implemented; PDF typesetting of the fossil term was degraded in the research extract.",
    "This workflow is preliminary / not certified and is not a BPI-2400 compliance claim.",
]


def _convert(period: UtilityPeriod) -> tuple[float | None, float | None, float | None, str | None]:
    """Return (kwh, therm, mbtu, note)."""
    usage = period.usage
    if period.fuel == "electricity":
        if period.unit == "kwh":
            kwh = usage
            return kwh, None, kwh * BTU_PER_KWH / 1_000_000.0, None
        if period.unit == "mbtu":
            return usage * 1_000_000.0 / BTU_PER_KWH, None, usage, None
        return None, None, None, f"electricity period uses unsupported unit {period.unit}"
    if period.fuel == "natural_gas":
        if period.unit == "therm":
            therm = usage
            return None, therm, therm / 10.0, None
        if period.unit == "ccf":
            therm = usage * CCF_TO_THERM_PRELIMINARY
            return (
                None,
                therm,
                therm / 10.0,
                "ccf treated as 1 therm (preliminary; heating value not weather-normalized)",
            )
        if period.unit == "mbtu":
            return None, usage * 10.0, usage, None
        return None, None, None, f"natural_gas period uses unsupported unit {period.unit}"
    return None, None, None, f"{period.fuel} is a delivered fuel; simplified path is not implemented"


def _select_periods(periods: list[UtilityPeriod], fuel: Fuel) -> tuple[list[UtilityPeriod], int]:
    group = [item for item in periods if item.fuel == fuel]
    atypical = [item for item in group if item.atypical]
    keep_atypical = atypical[MAX_DROPPED_ATYPICAL:]
    dropped = min(len(atypical), MAX_DROPPED_ATYPICAL)
    kept = [item for item in group if not item.atypical] + keep_atypical
    kept.sort(key=lambda item: item.start_date)
    return kept, dropped


def assess_history(periods: list[UtilityPeriod], as_of: date | None = None) -> HistoryQuality:
    as_of = as_of or date.today()
    fuels: dict[str, FuelAnnual] = {}
    dropped_total = 0
    extra_notes: list[str] = []

    for fuel in ("electricity", "natural_gas", "fuel_oil", "propane"):
        kept, dropped = _select_periods(periods, fuel)  # type: ignore[arg-type]
        dropped_total += dropped
        if not kept and not any(item.fuel == fuel for item in periods):
            continue
        kwh = therm = mbtu = 0.0
        have_kwh = have_therm = have_mbtu = False
        notes: list[str] = []
        for item in kept:
            ck, ct, cm, note = _convert(item)
            if note:
                notes.append(note)
            if ck is not None:
                kwh += ck
                have_kwh = True
            if ct is not None:
                therm += ct
                have_therm = True
            if cm is not None:
                mbtu += cm
                have_mbtu = True
        span = (kept[-1].end_date - kept[0].start_date).days if kept else None
        latest = kept[-1].end_date if kept else None
        recent = bool(latest and (as_of - latest) <= timedelta(days=RECENT_READ_DAYS))
        meets_330 = bool(span is not None and span >= MIN_DETAILED_SPAN_DAYS)
        meets_183 = bool(span is not None and MIN_ALTERNATE_SPAN_DAYS <= span < MIN_DETAILED_SPAN_DAYS)
        estimated = sum(1 for item in kept if item.read_type == "estimated")
        qualifies = False
        if fuel in DELIVERED_FUELS:
            notes.append("Delivered-fuel §3.3.1 path is not implemented; this fuel cannot qualify.")
        elif fuel in HEATING_COOLING_FUELS:
            qualifies = bool(kept and meets_330 and recent and (have_kwh or have_therm))
            if meets_183:
                notes.append(
                    f"Span is {span} days (≥183, <330). HDD/CDD coverage path is not implemented, so this fuel does not qualify."
                )
            if estimated:
                notes.append(
                    f"{estimated} estimated read(s) were kept as-is; they were not rolled into the next actual read."
                )
            if not recent and latest:
                notes.append(f"Most recent read ({latest.isoformat()}) is older than {RECENT_READ_DAYS} days before {as_of.isoformat()}.")
        fuels[fuel] = FuelAnnual(
            fuel=fuel,  # type: ignore[arg-type]
            period_count=len(kept),
            dropped_atypical=dropped,
            estimated_count=estimated,
            span_days=span,
            most_recent_end=latest,
            measured_kwh=kwh if have_kwh else None,
            measured_therm=therm if have_therm else None,
            measured_mbtu=mbtu if have_mbtu else None,
            meets_330_day_rule=meets_330,
            meets_183_day_span_only=meets_183,
            recent_read=recent,
            qualifies_for_detailed_path=qualifies,
            notes=notes,
        )
        extra_notes.extend(notes)

    any_qualifies = any(item.qualifies_for_detailed_path for item in fuels.values())
    label = (
        "bills_meet_documented_330_day_span"
        if any_qualifies
        else "bills_do_not_meet_implemented_quality_gate"
    )
    gaps = list(STANDARD_GAPS)
    if any(item.meets_183_day_span_only for item in fuels.values()):
        gaps.append("At least one fuel fell in the 183–329 day window; HDD/CDD coverage was not evaluated.")
    return HistoryQuality(
        as_of=as_of,
        fuels=fuels,
        any_fuel_qualifies=any_qualifies,
        dropped_atypical_total=dropped_total,
        gaps=gaps,
        label=label,
    )
