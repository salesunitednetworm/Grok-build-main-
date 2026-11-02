from pathlib import Path

import pytest

from app.config import settings
from app.domain.building import apply_attic_insulation, default_payload, validate_payload
from app.domain.comparison import compare_results
from app.providers.openstudio_hpxml import OpenStudioHpxmlProvider

CLI = Path("/usr/local/openstudio-3.11.0/bin/openstudio")
TREE = Path("/opt/OpenStudio-HPXML-1.12.0")


def _engine_present() -> bool:
    return CLI.exists() and (TREE / "workflow" / "run_simulation.rb").exists()


@pytest.mark.skipif(not _engine_present(), reason="OpenStudio 3.11.0 / OS-HPXML 1.12.0 not installed")
def test_live_baseline_and_attic_upgrade(tmp_path: Path):
    settings.openstudio_cli = str(CLI)
    settings.openstudio_hpxml_dir = TREE
    try:
        provider = OpenStudioHpxmlProvider()
        assert provider.is_available().available is True
        baseline_model, errors = validate_payload(default_payload())
        assert baseline_model is not None and errors == []
        baseline = provider.run(provider.generate_input(baseline_model), tmp_path / "baseline")
        assert baseline.status == "succeeded", baseline.error_message
        assert baseline.energy is not None
        assert baseline.energy.electricity_kwh is not None
        assert baseline.energy.electricity_kwh > 0
        assert baseline.energy.natural_gas_therm is not None
        assert baseline.energy.loads_qualification == "preliminary"

        upgraded_model, up_errors = validate_payload(apply_attic_insulation(default_payload(), 49.0))
        assert upgraded_model is not None and up_errors == []
        upgrade = provider.run(provider.generate_input(upgraded_model), tmp_path / "upgrade")
        assert upgrade.status == "succeeded", upgrade.error_message
        assert upgrade.energy is not None
        assert upgrade.energy.electricity_kwh is not None

        deltas = compare_results(baseline.energy, upgrade.energy)
        assert deltas.status == "complete"
        assert deltas.electricity_kwh_delta is not None
        assert deltas.total_mbtu_delta is not None
        assert "Not BPI-2400" in deltas.notes
    finally:
        settings.openstudio_cli = ""
        settings.openstudio_hpxml_dir = None
