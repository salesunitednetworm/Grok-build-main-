import json
from pathlib import Path

import pytest

from app.domain.results import parse_annual_results

from .report import write_artifact

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures"


def test_fuel_specific_totals_from_committed_fixtures():
    official = parse_annual_results(json.loads((FIXTURES / "results_annual.official-base.json").read_text()))
    sample = parse_annual_results(json.loads((FIXTURES / "results_annual.sample.json").read_text()))
    assert official.electricity_mbtu == 39.218
    assert official.electricity_kwh == pytest.approx(39.218 * 1_000_000 / 3412)
    assert official.natural_gas_mbtu == 32.638
    assert official.natural_gas_therm == pytest.approx(326.38)
    assert official.loads_qualification == "preliminary"
    heating = [key for key in official.end_uses if "Heating" in key]
    cooling = [key for key in official.end_uses if "Cooling" in key]
    dhw = [key for key in official.end_uses if "Hot Water" in key or "Water" in key]
    lighting = [key for key in official.end_uses if "Lighting" in key]
    assert heating and cooling and dhw
    write_artifact(
        "fuel-totals",
        {
            "official_base": {
                "electricity_mbtu": official.electricity_mbtu,
                "electricity_kwh": official.electricity_kwh,
                "natural_gas_mbtu": official.natural_gas_mbtu,
                "natural_gas_therm": official.natural_gas_therm,
                "total_mbtu": official.total_mbtu,
                "end_use_keys": sorted(official.end_uses),
                "heating_keys": heating,
                "cooling_keys": cooling,
                "dhw_keys": dhw,
                "lighting_keys": lighting,
                "loads_qualification": official.loads_qualification,
            },
            "sample_fixture": {
                "electricity_mbtu": sample.electricity_mbtu,
                "natural_gas_therm": sample.natural_gas_therm,
                "loads_qualification": sample.loads_qualification,
            },
            "ashrae_140_verdict": None,
        },
    )
