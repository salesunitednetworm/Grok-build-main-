from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.domain.building import apply_duct_leakage, apply_heat_pump, default_payload, validate_payload
from app.providers.openstudio_hpxml import OpenStudioHpxmlProvider

CLI = Path("/usr/local/openstudio-3.11.0/bin/openstudio")
TREE = Path("/opt/OpenStudio-HPXML-1.12.0")


def _engine_present() -> bool:
    return CLI.exists() and (TREE / "workflow" / "run_simulation.rb").exists()


@pytest.mark.skipif(not _engine_present(), reason="OpenStudio 3.11.0 / OS-HPXML 1.12.0 not installed")
def test_live_heat_pump_and_duct_leakage_and_miami_weather(tmp_path: Path):
    settings.openstudio_cli = str(CLI)
    settings.openstudio_hpxml_dir = TREE
    try:
        provider = OpenStudioHpxmlProvider()
        hp_model, errors = validate_payload(apply_heat_pump(default_payload(), hspf2=8.5, seer2=16.0))
        assert hp_model is not None and errors == []
        hp = provider.run(provider.generate_input(hp_model), tmp_path / "heat-pump")
        assert hp.status == "succeeded", hp.error_message
        assert hp.energy is not None
        assert hp.energy.electricity_kwh and hp.energy.electricity_kwh > 0
        assert hp.energy.loads_qualification == "preliminary"
        assert hp.energy.software_defaults
        assert any(item["data_source"] == "software" for item in hp.energy.software_defaults)

        leak_model, leak_errors = validate_payload(apply_duct_leakage(default_payload(), 40.0, 15.0))
        assert leak_model is not None and leak_errors == []
        leak = provider.run(provider.generate_input(leak_model), tmp_path / "ducts")
        assert leak.status == "succeeded", leak.error_message
        assert leak.energy is not None
        assert leak.energy.electricity_kwh and leak.energy.electricity_kwh > 0

        miami = default_payload()
        miami["site"]["postal_code"] = "33101"
        miami["site"]["state_code"] = "FL"
        from app.domain.weather import apply_weather

        apply_weather(miami)
        assert "Miami" in miami["site"]["weather_station"]
        miami_model, miami_errors = validate_payload(miami)
        assert miami_model is not None and miami_errors == []
        miami_run = provider.run(provider.generate_input(miami_model), tmp_path / "miami")
        assert miami_run.status == "succeeded", miami_run.error_message
        assert miami_run.energy is not None
        assert miami_run.energy.electricity_kwh and miami_run.energy.electricity_kwh > 0
        # Different climate than the Denver-shaped default heat-pump run.
        assert miami_run.energy.electricity_kwh != hp.energy.electricity_kwh
    finally:
        settings.openstudio_cli = ""
        settings.openstudio_hpxml_dir = None


@pytest.mark.skipif(not _engine_present(), reason="OpenStudio 3.11.0 / OS-HPXML 1.12.0 not installed")
def test_live_api_heat_pump_scenario(client: TestClient):
    settings.openstudio_cli = str(CLI)
    settings.openstudio_hpxml_dir = TREE
    try:
        home_id = client.post(
            "/api/v1/homes",
            json={"name": "HP house", "state_code": "CO", "postal_code": "80202", "city": "Denver"},
        ).json()["id"]
        model = client.get(f"/api/v1/homes/{home_id}/model").json()
        client.put(f"/api/v1/homes/{home_id}/model", json={"payload": model["payload"]})
        weather = client.get("/api/v1/weather/33101").json()
        assert weather["official_station"].endswith("Miami.Intl.AP.722020_TMY3")
        scenario = client.post(
            f"/api/v1/homes/{home_id}/scenarios",
            json={
                "name": "Heat pump",
                "measure_type": "heat_pump",
                "heating_efficiency_hspf2": 8.5,
                "cooling_efficiency_seer2": 16,
            },
        )
        assert scenario.status_code == 200, scenario.text
        body = scenario.json()
        assert body["measure_type"] == "heat_pump"
        assert body["upgrade_job"]["status"] == "succeeded"
        assert body["comparison"]["status"] == "complete"
        assert body["comparison"]["electricity_kwh_delta"] is not None
        assert body["upgrade_job"]["energy_result"]["software_defaults"]
        assert body["upgrade_job"]["energy_result"]["loads_qualification"] == "preliminary"
    finally:
        settings.openstudio_cli = ""
        settings.openstudio_hpxml_dir = None
