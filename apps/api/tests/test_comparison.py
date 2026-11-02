from app.domain.comparison import compare_results
from app.domain.results import ParsedAnnual


def test_no_results_means_no_deltas():
    deltas = compare_results(None, None)
    assert deltas.status == "unavailable"
    assert deltas.electricity_kwh_delta is None
    assert deltas.natural_gas_therm_delta is None
    assert deltas.total_mbtu_delta is None
    assert "does not estimate" in deltas.notes


def test_one_sided_results_are_unavailable():
    baseline = ParsedAnnual(electricity_kwh=1000, natural_gas_therm=50, total_mbtu=20)
    deltas = compare_results(baseline, None)
    assert deltas.status == "unavailable"
    assert deltas.electricity_kwh_delta is None


def test_real_results_compute_absolute_delta_not_percent():
    baseline = ParsedAnnual(electricity_kwh=10000, natural_gas_therm=800, total_mbtu=120)
    upgrade = ParsedAnnual(electricity_kwh=9800, natural_gas_therm=700, total_mbtu=110)
    deltas = compare_results(baseline, upgrade)
    assert deltas.status == "complete"
    assert deltas.electricity_kwh_delta == -200
    assert deltas.natural_gas_therm_delta == -100
    assert deltas.total_mbtu_delta == -10
    assert "percent" not in deltas.notes.lower() or "not" in deltas.notes.lower()
    assert not hasattr(deltas, "savings_percent")
