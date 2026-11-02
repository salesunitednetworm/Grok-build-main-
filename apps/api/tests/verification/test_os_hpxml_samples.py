from pathlib import Path

import pytest

from app.config import settings
from app.domain.results import parse_annual_results
from app.domain.schema_check import OFFICIAL_BASE, OFFICIAL_HPWH, validate_against_xsd, xsd_available
from app.providers.base import ProviderInput
from app.providers.openstudio_hpxml import OpenStudioHpxmlProvider

from .report import write_artifact

CLI = Path("/usr/local/openstudio-3.11.0/bin/openstudio")
TREE = Path("/opt/OpenStudio-HPXML-1.12.0")


def _engine_present() -> bool:
    return CLI.exists() and (TREE / "workflow" / "run_simulation.rb").exists()


def test_official_samples_schema():
    assert OFFICIAL_BASE.exists()
    assert OFFICIAL_HPWH.exists()
    base_xml = OFFICIAL_BASE.read_text()
    hpwh_xml = OFFICIAL_HPWH.read_text()
    assert "http://hpxmlonline.com/2025/12" in base_xml
    assert "heat pump water heater" in hpwh_xml
    xsd_base = validate_against_xsd(base_xml) if xsd_available() else []
    xsd_hpwh = validate_against_xsd(hpwh_xml) if xsd_available() else []
    if xsd_available():
        assert xsd_base == []
        assert xsd_hpwh == []
    write_artifact(
        "os-hpxml-samples",
        {
            "base_xml": str(OFFICIAL_BASE),
            "hpwh_xml": str(OFFICIAL_HPWH),
            "xsd_base_errors": xsd_base,
            "xsd_hpwh_errors": xsd_hpwh,
            "live_engine_run": False,
            "ashrae_140_verdict": None,
            "ashrae_140_reason": "Paid standard; harness records schema/sample presence only.",
        },
    )


@pytest.mark.skipif(not _engine_present(), reason="OpenStudio 3.11.0 / OS-HPXML 1.12.0 not installed")
def test_official_base_live_energyplus(tmp_path: Path):
    settings.openstudio_cli = str(CLI)
    settings.openstudio_hpxml_dir = TREE
    try:
        provider = OpenStudioHpxmlProvider()
        xml = OFFICIAL_BASE.read_text()
        run = provider.run(ProviderInput(xml_text=xml, schema_version="5.0", namespace="http://hpxmlonline.com/2025/12"), tmp_path / "official-base")
        assert run.status == "succeeded", run.error_message
        assert run.energy is not None
        assert run.energy.electricity_kwh is not None and run.energy.electricity_kwh > 0
        assert run.energy.natural_gas_therm is not None
        assert run.energy.loads_qualification == "preliminary"
        parsed = parse_annual_results(run.energy.raw_annual)
        write_artifact(
            "os-hpxml-samples-live",
            {
                "status": run.status,
                "electricity_mbtu": parsed.electricity_mbtu,
                "electricity_kwh": parsed.electricity_kwh,
                "natural_gas_mbtu": parsed.natural_gas_mbtu,
                "natural_gas_therm": parsed.natural_gas_therm,
                "total_mbtu": parsed.total_mbtu,
                "heating_design_load_btuh": parsed.heating_design_load_btuh,
                "loads_qualification": parsed.loads_qualification,
                "ashrae_140_verdict": None,
            },
        )
    finally:
        settings.openstudio_cli = ""
        settings.openstudio_hpxml_dir = None
