from datetime import date

from fastapi.testclient import TestClient


def _home(client: TestClient) -> str:
    created = client.post(
        "/api/v1/homes",
        json={"name": "Bills House", "state_code": "CO", "postal_code": "80202", "city": "Denver"},
    )
    home_id = created.json()["id"]
    model = client.get(f"/api/v1/homes/{home_id}/model").json()
    client.put(f"/api/v1/homes/{home_id}/model", json={"payload": model["payload"]})
    return home_id


def _year_periods(fuel: str, usage: float, unit: str) -> list[dict]:
    from calendar import monthrange

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


def test_utility_history_and_uncalibrated_without_energyplus(client: TestClient):
    home_id = _home(client)
    body = {
        "as_of": "2026-01-15",
        "periods": _year_periods("electricity", 900, "kwh") + _year_periods("natural_gas", 70, "therm"),
    }
    saved = client.put(f"/api/v1/homes/{home_id}/utility-history", json=body)
    assert saved.status_code == 200
    quality = saved.json()["quality"]
    assert quality["any_fuel_qualifies"] is True
    assert quality["fuels"]["electricity"]["measured_kwh"] == 10800

    client.post(f"/api/v1/homes/{home_id}/simulate")
    cal = client.post(
        f"/api/v1/homes/{home_id}/calibration",
        json={"apply_permitted_adjustments": True},
    )
    assert cal.status_code == 200
    payload = cal.json()
    assert payload["model_label"] == "uncalibrated"
    assert payload["compliance_claim"] == "not_bpi_2400_calibrated"
    assert payload["qualification"] != "bpi_2400"
    assert "bpi_2400_calibrated" not in payload["run_status"]
    assert payload["residuals"] == []
    assert any("preliminary" in gap.lower() or "not certified" in gap.lower() for gap in payload["gaps"])


def test_packages_do_not_invent_deltas_when_engine_missing(client: TestClient):
    home_id = _home(client)
    rows = client.post(f"/api/v1/homes/{home_id}/packages")
    assert rows.status_code == 200
    packages = rows.json()
    assert len(packages) == 7
    assert {row["name"] for row in packages} == {
        "attic",
        "air_sealing",
        "hpwh",
        "attic+air_sealing",
        "attic+hpwh",
        "air_sealing+hpwh",
        "attic+air_sealing+hpwh",
    }
    for row in packages:
        assert row["electricity_kwh_delta"] is None
        assert row["natural_gas_therm_delta"] is None
        assert row["total_mbtu_delta"] is None
        assert row["status"] == "unavailable"
        assert row["upgrade_job"]["energy_result"] is None
        assert "percent" not in (row["notes"] or "").lower() or "not" in (row["notes"] or "").lower()
