import json
from pathlib import Path

import pytest

from app.domain.results import parse_annual_results

FIXTURE = Path(__file__).parent / "fixtures" / "results_annual.sample.json"


def test_parse_fixture_converts_units():
    data = json.loads(FIXTURE.read_text())
    parsed = parse_annual_results(data)
    assert parsed.source == "openstudio_hpxml_energyplus"
    assert parsed.total_mbtu == 120.0
    assert parsed.electricity_mbtu == 40.0
    assert parsed.electricity_kwh == pytest.approx(40.0 * 1_000_000 / 3412)
    assert parsed.natural_gas_therm == 800.0
    assert parsed.heating_design_load_btuh == 35000
    assert parsed.loads_qualification == "preliminary"
    assert parsed.end_uses["End Use: Natural Gas: Heating (MBtu)"] == 75.0


def test_missing_keys_stay_none():
    parsed = parse_annual_results({})
    assert parsed.electricity_kwh is None
    assert parsed.total_mbtu is None
    assert parsed.end_uses == {}


def test_parse_official_nested_engine_file():
    data = json.loads((Path(__file__).parent / "fixtures" / "results_annual.official-base.json").read_text())
    parsed = parse_annual_results(data)
    assert parsed.electricity_mbtu == 39.218
    assert parsed.electricity_kwh == pytest.approx(39.218 * 1_000_000 / 3412)
    assert parsed.natural_gas_therm == pytest.approx(326.38)
    assert parsed.heating_design_load_btuh == 41543
    assert parsed.cooling_sensible_design_load_btuh == 27993
    assert parsed.loads_qualification == "preliminary"


def test_nested_annual_json():
    parsed = parse_annual_results(
        {
            "Fuel Use": {"Electricity: Total (MBtu)": 10},
            "Energy Use": {"Total (MBtu)": 12},
        }
    )
    assert parsed.electricity_mbtu == 10
    assert parsed.electricity_kwh == 10 * 1_000_000 / 3412
    assert parsed.total_mbtu == 12
