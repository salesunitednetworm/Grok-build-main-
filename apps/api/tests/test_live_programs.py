from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import settings

CLI = Path("/usr/local/openstudio-3.11.0/bin/openstudio")
TREE = Path("/opt/OpenStudio-HPXML-1.12.0")


def _engine_present() -> bool:
    return CLI.exists() and (TREE / "workflow" / "run_simulation.rb").exists()


@pytest.mark.skipif(not _engine_present(), reason="OpenStudio 3.11.0 / OS-HPXML 1.12.0 not installed")
def test_live_nc_homes_screen_uses_stored_energyplus(client: TestClient):
    settings.openstudio_cli = str(CLI)
    settings.openstudio_hpxml_dir = TREE
    try:
        home_id = client.post(
            "/api/v1/homes",
            json={"name": "NC program live", "state_code": "NC", "postal_code": "27601", "city": "Raleigh"},
        ).json()["id"]
        model = client.get(f"/api/v1/homes/{home_id}/model").json()
        client.put(f"/api/v1/homes/{home_id}/model", json={"payload": model["payload"]})
        scenario = client.post(
            f"/api/v1/homes/{home_id}/scenarios",
            json={"name": "Heat pump for program screen", "measure_type": "heat_pump"},
        )
        assert scenario.status_code == 200, scenario.text
        body = scenario.json()
        assert body["upgrade_job"]["status"] == "succeeded"
        assert body["comparison"]["status"] == "complete"
        baseline_kwh = body["baseline_job"]["energy_result"]["electricity_kwh"]
        upgrade_kwh = body["upgrade_job"]["energy_result"]["electricity_kwh"]
        assert baseline_kwh and upgrade_kwh
        evaluation = client.post(
            f"/api/v1/homes/{home_id}/program-evaluations",
            json={
                "pack_id": "nc-homes-v2.0-2026-02",
                "ami_band": "below_80",
                "measures": ["heat_pump"],
                "existing_home": True,
                "bills_twelve_months_all_fuels": True,
                "scenario_id": body["id"],
                "docs_present": {
                    "income_docs_or_categorical_letter": True,
                    "invoice_with_address_dates_cost_rebate": True,
                },
            },
        )
        assert evaluation.status_code == 200, evaluation.text
        data = evaluation.json()
        assert data["pack_version"] == "2.0.0"
        assert data["this_product_doe_approved"] is False
        assert data["portal_status"] == "not_submitted"
        if data["savings_percent"] is not None:
            assert data["savings_method"] == "preliminary_site_energy_from_stored_energyplus_totals"
            assert "bpi" not in (data["savings_method"] or "").lower() or "not" in data["notes"].lower()
        assert data["compliance_claim"] == "not_doe_approved_not_submitted"
        assert data["overall_status"] in {"incomplete", "ineligible", "screen_passed_not_submittable"}
    finally:
        settings.openstudio_cli = ""
        settings.openstudio_hpxml_dir = None
