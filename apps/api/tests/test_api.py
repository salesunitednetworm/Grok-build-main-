from fastapi.testclient import TestClient


def test_health(client: TestClient):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_engine_status_is_unavailable(client: TestClient):
    response = client.get("/api/v1/status")
    body = response.json()
    assert body["available"] is False
    assert body["versions"]["energyplus"] == "25.2.0"
    assert any("not DOE HOMES" in line for line in body["regulatory"])


def test_vertical_slice_without_energyplus(client: TestClient):
    created = client.post(
        "/api/v1/homes",
        json={"name": "12 Pine St", "state_code": "CO", "postal_code": "80202", "city": "Denver"},
    )
    assert created.status_code == 200
    home_id = created.json()["id"]

    model = client.get(f"/api/v1/homes/{home_id}/model").json()
    assert model["payload"]["schema"] == "hems.building/v1"

    saved = client.put(f"/api/v1/homes/{home_id}/model", json={"payload": model["payload"]})
    assert saved.status_code == 200
    assert saved.json()["status"] == "valid"

    validated = client.post(f"/api/v1/homes/{home_id}/validate")
    assert validated.json()["status"] == "valid"
    assert validated.json()["validation_errors"] is None

    hpxml = client.post(f"/api/v1/homes/{home_id}/hpxml")
    assert hpxml.status_code == 200
    assert "http://hpxmlonline.com/2025/12" in hpxml.json()["xml_text"]
    assert hpxml.json()["schema_version"] == "5.0-rc1"

    job = client.post(f"/api/v1/homes/{home_id}/simulate").json()
    assert job["status"] == "unavailable"
    assert job["energy_result"] is None
    assert any(item["kind"] == "hpxml_input" for item in job["artifacts"])
    assert job["unavailable_reason"]

    scenario = client.post(
        f"/api/v1/homes/{home_id}/scenarios",
        json={"name": "Attic to R-49", "measure_type": "attic_insulation", "ceiling_assembly_r": 49},
    )
    assert scenario.status_code == 200
    body = scenario.json()
    assert body["comparison"]["status"] == "unavailable"
    assert body["comparison"]["electricity_kwh_delta"] is None
    assert body["comparison"]["natural_gas_therm_delta"] is None
    assert "does not estimate" in body["comparison"]["notes"]
    assert body["baseline_job"]["status"] == "unavailable"
    assert body["upgrade_job"]["status"] == "unavailable"
    assert body["baseline_job"]["energy_result"] is None
    assert body["upgrade_job"]["energy_result"] is None


def test_invalid_model_rejected(client: TestClient):
    home_id = client.post("/api/v1/homes", json={"name": "Bad House"}).json()["id"]
    payload = client.get(f"/api/v1/homes/{home_id}/model").json()["payload"]
    payload["construction"]["conditioned_floor_area_ft2"] = 1
    saved = client.put(f"/api/v1/homes/{home_id}/model", json={"payload": payload})
    assert saved.json()["status"] == "invalid"
    hpxml = client.post(f"/api/v1/homes/{home_id}/hpxml")
    assert hpxml.status_code == 400
