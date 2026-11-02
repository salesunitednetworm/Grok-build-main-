from __future__ import annotations

from pydantic import BaseModel

from app.domain.results import ParsedAnnual


class ComparisonDeltas(BaseModel):
    status: str
    electricity_kwh_delta: float | None = None
    natural_gas_therm_delta: float | None = None
    total_mbtu_delta: float | None = None
    notes: str


def compare_results(baseline: ParsedAnnual | None, upgrade: ParsedAnnual | None) -> ComparisonDeltas:
    """Absolute deltas only when both sides were parsed from EnergyPlus output."""
    if baseline is None or upgrade is None:
        return ComparisonDeltas(
            status="unavailable",
            notes=(
                "Savings cannot be calculated without EnergyPlus results on both "
                "the baseline and the upgrade. This product does not estimate or "
                "invent savings percentages."
            ),
        )

    def delta(left: float | None, right: float | None) -> float | None:
        if left is None or right is None:
            return None
        return right - left

    elec = delta(baseline.electricity_kwh, upgrade.electricity_kwh)
    gas = delta(baseline.natural_gas_therm, upgrade.natural_gas_therm)
    total = delta(baseline.total_mbtu, upgrade.total_mbtu)
    if elec is None and gas is None and total is None:
        return ComparisonDeltas(
            status="unavailable",
            notes="Both jobs finished but parsed annual files had no comparable fuel totals.",
        )
    return ComparisonDeltas(
        status="complete",
        electricity_kwh_delta=elec,
        natural_gas_therm_delta=gas,
        total_mbtu_delta=total,
        notes=(
            "Upgrade minus baseline from OpenStudio-HPXML / EnergyPlus annual output. "
            "Negative means the upgrade used less. Not BPI-2400 equivalent-energy savings. "
            "Not a DOE HOMES qualified percentage."
        ),
    )
