from datetime import date

from app.domain.bills import UtilityPeriod, assess_history
from app.domain.building import default_payload
from app.domain.calibration import (
    COMPLIANCE_CLAIM,
    apply_adjustments,
    assess_calibration,
    is_permitted_adjustment,
    propose_setpoint_adjustments,
)
from app.domain.results import ParsedAnnual


def _months(fuel: str, usage: float, unit: str, year: int = 2025, count: int = 12) -> list[UtilityPeriod]:
    from calendar import monthrange

    periods: list[UtilityPeriod] = []
    for month in range(1, count + 1):
        last = monthrange(year, month)[1]
        periods.append(
            UtilityPeriod(
                start_date=date(year, month, 1),
                end_date=date(year, month, last),
                fuel=fuel,  # type: ignore[arg-type]
                usage=usage,
                unit=unit,  # type: ignore[arg-type]
            )
        )
    return periods


def test_330_day_gate_qualifies_and_annualizes():
    periods = _months("electricity", 900, "kwh") + _months("natural_gas", 70, "therm")
    quality = assess_history(periods, as_of=date(2026, 1, 15))
    assert quality.any_fuel_qualifies is True
    assert quality.fuels["electricity"].measured_kwh == 10800
    assert quality.fuels["natural_gas"].measured_therm == 840
    assert quality.fuels["electricity"].meets_330_day_rule is True
    assert "not a BPI-2400 compliance claim" in " ".join(quality.gaps)


def test_short_history_does_not_qualify():
    periods = _months("electricity", 900, "kwh", count=2)
    quality = assess_history(periods, as_of=date(2026, 1, 15))
    assert quality.any_fuel_qualifies is False
    assert quality.fuels["electricity"].qualifies_for_detailed_path is False


def test_183_day_span_is_gap_not_qualify():
    periods = _months("electricity", 800, "kwh", count=7)
    quality = assess_history(periods, as_of=date(2026, 1, 15))
    fuel = quality.fuels["electricity"]
    assert fuel.meets_183_day_span_only is True
    assert fuel.qualifies_for_detailed_path is False
    assert any("HDD/CDD" in note for note in fuel.notes)


def test_delivered_fuel_never_qualifies():
    periods = _months("fuel_oil", 80, "gal")
    quality = assess_history(periods, as_of=date(2026, 1, 15))
    assert quality.fuels["fuel_oil"].qualifies_for_detailed_path is False
    assert quality.any_fuel_qualifies is False


def test_residuals_and_uncalibrated_label():
    periods = _months("electricity", 900, "kwh") + _months("natural_gas", 70, "therm")
    quality = assess_history(periods, as_of=date(2026, 1, 15))
    energy = ParsedAnnual(electricity_kwh=11279.6, natural_gas_therm=289.28, total_mbtu=67.414)
    result = assess_calibration(quality, energy, default_payload(), apply=False)
    assert result.model_label == "uncalibrated"
    assert result.run_status == "residuals_computed_uncalibrated"
    assert result.compliance_claim == COMPLIANCE_CLAIM
    assert result.qualification == "none"
    elec = next(item for item in result.residuals if item.fuel == "electricity")
    assert elec.residual_kwh == 11279.6 - 10800
    assert any("Guideline 14" in note for note in elec.notes)
    assert any("not certified" in gap.lower() or "not a BPI-2400" in gap for gap in result.gaps)


def test_no_energy_does_not_invent_kwh():
    periods = _months("electricity", 900, "kwh")
    quality = assess_history(periods, as_of=date(2026, 1, 15))
    result = assess_calibration(quality, None, default_payload(), apply=False)
    assert result.residuals == []
    assert result.model_label == "uncalibrated"
    assert "No kWh is invented" in result.notes


def test_measured_setpoint_cannot_be_adjusted():
    payload = default_payload()
    payload["data_source"]["heating_setpoint_f"] = "measured"
    ok, reason = is_permitted_adjustment(payload, "systems.heating_setpoint_f")
    assert ok is False
    assert reason is not None
    assert "measured" in reason.lower() or "3.2.1" in reason


def test_nameplate_efficiency_never_adjusted():
    payload = default_payload()
    ok, reason = is_permitted_adjustment(payload, "systems.heating_efficiency_afue")
    assert ok is False
    assert reason is not None


def test_apply_only_permitted_setpoints():
    payload = default_payload()
    periods = _months("natural_gas", 20, "therm")
    quality = assess_history(periods, as_of=date(2026, 1, 15))
    # Force qualify for the assessment path by not using this quality for apply;
    # we test apply_adjustments directly with a proposed heating step.
    energy = ParsedAnnual(natural_gas_therm=289.28, electricity_kwh=10000, total_mbtu=60)
    proposed = propose_setpoint_adjustments(
        payload,
        assess_calibration(quality, energy, payload).residuals,
    )
    heating = [item for item in proposed if item.field == "systems.heating_setpoint_f" and item.permitted]
    assert heating
    cloned, applied = apply_adjustments(payload, heating)
    assert applied
    assert cloned["systems"]["heating_setpoint_f"] != payload["systems"]["heating_setpoint_f"]
    assert cloned["systems"]["heating_efficiency_afue"] == payload["systems"]["heating_efficiency_afue"]
    assert cloned["enclosure"]["ach50"] == payload["enclosure"]["ach50"]


def test_calibrated_label_is_preliminary_not_certified():
    payload = default_payload()
    periods = _months("electricity", 900, "kwh") + _months("natural_gas", 70, "therm")
    quality = assess_history(periods, as_of=date(2026, 1, 15))
    energy = ParsedAnnual(electricity_kwh=11279.6, natural_gas_therm=289.28, total_mbtu=67.414)
    draft = assess_calibration(quality, energy, payload)
    permitted = [item for item in draft.proposed_adjustments if item.permitted]
    cloned, applied = apply_adjustments(payload, permitted)
    adjusted = ParsedAnnual(electricity_kwh=11100.0, natural_gas_therm=300.0, total_mbtu=66.0)
    result = assess_calibration(
        quality, energy, payload, apply=True, adjusted_energy=adjusted, applied=applied
    )
    assert result.model_label == "calibrated"
    assert result.qualification == "preliminary_not_certified"
    assert result.run_status == "preliminarily_adjusted"
    assert result.compliance_claim == "not_bpi_2400_calibrated"
    assert "not BPI-2400" in result.notes
    assert cloned["systems"]["heating_setpoint_f"] != default_payload()["systems"]["heating_setpoint_f"] or applied
