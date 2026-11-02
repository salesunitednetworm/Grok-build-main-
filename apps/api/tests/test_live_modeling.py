from calendar import monthrange
from datetime import date
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import settings

CLI = Path("/usr/local/openstudio-3.11.0/bin/openstudio")
TREE = Path("/opt/OpenStudio-HPXML-1.12.0")


def _engine_present() -> bool:
    return CLI.exists() and (TREE / "workflow" / "run_simulation.rb").exists()


def _year_periods(fuel: str, usage: float, unit: str) -> list[dict]:
    rows = []
    for month in range(1, 13):
        last = monthrange(2025, month)[1]
        rows.append(
            {
                "start_date": date(2025, month, 1).isoformat(),
                "end_date": date(2025, month, last).isoformat(),
                "fuel": fuel,
                "usage": usage,
                "unit": unit,
                "read_type": "actual",
            }
        )
    return rows


@pytest.mark.skipif(not _engine_present(), reason="OpenStudio 3.11.0 / OS-HPXML 1.12.0 not installed")
def test_live_calibration_and_packages_rerun_energyplus(client: TestClient):
    settings.openstudio_cli = str(CLI)
    settings.openstudio_hpxml_dir = TREE
    try:
        created = client.post(
            "/api/v1/homes",
            json={"name": "Live modeling", "state_code": "CO", "postal_code": "80202", "city": "Denver"},
        )
        home_id = created.json()["id"]
        model = client.get(f"/api/v1/homes/{home_id}/model").json()
        client.put(f"/api/v1/homes/{home_id}/model", json={"payload": model["payload"]})
        job = client.post(f"/api/v1/homes/{home_id}/simulate").json()
        assert job["status"] == "succeeded", job.get("error_message")
        energy = job["energy_result"]
        assert energy is not None
        assert energy["electricity_kwh"] is not None and energy["electricity_kwh"] > 0
        assert energy["loads_qualification"] == "preliminary"

        elec_month = energy["electricity_kwh"] / 12.0
        gas_month = energy["natural_gas_therm"] / 12.0
        bills = client.put(
            f"/api/v1/homes/{home_id}/utility-history",
            json={
                "as_of": "2026-01-15",
                "periods": _year_periods("electricity", elec_month, "kwh")
                + _year_periods("natural_gas", gas_month, "therm"),
            },
        )
        assert bills.status_code == 200
        assert bills.json()["quality"]["any_fuel_qualifies"] is True

        cal = client.post(
            f"/api/v1/homes/{home_id}/calibration",
            json={"apply_permitted_adjustments": True},
        ).json()
        assert cal["compliance_claim"] == "not_bpi_2400_calibrated"
        assert "bpi_2400_calibrated" not in cal["run_status"]
        assert cal["residuals"]
        if cal["applied_adjustments"]:
            assert cal["adjusted_job"] is not None
            if cal["adjusted_job"]["status"] == "succeeded":
                assert cal["model_label"] == "calibrated"
                assert cal["qualification"] == "preliminary_not_certified"
                assert cal["adjusted_job"]["energy_result"]["electricity_kwh"] > 0
            else:
                assert cal["model_label"] == "uncalibrated"
        else:
            assert cal["model_label"] == "uncalibrated"

        packages = client.post(f"/api/v1/homes/{home_id}/packages").json()
        assert len(packages) == 7
        for row in packages:
            assert row["upgrade_job"]["status"] == "succeeded", (row["name"], row["upgrade_job"].get("error_message"))
            assert row["status"] == "complete"
            assert row["electricity_kwh_delta"] is not None
            assert row["upgrade_job"]["energy_result"]["electricity_kwh"] > 0
            notes = (row["notes"] or "").lower()
            assert "not bpi-2400" in notes or "percentage" not in notes or "not" in notes
    finally:
        settings.openstudio_cli = ""
        settings.openstudio_hpxml_dir = None
