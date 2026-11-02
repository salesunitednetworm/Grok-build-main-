from app.domain.building import default_payload, validate_payload


def test_default_payload_is_valid():
    model, errors = validate_payload(default_payload())
    assert errors == []
    assert model is not None
    assert model.construction.conditioned_floor_area_ft2 == 2700


def test_rejects_tiny_floor_area():
    payload = default_payload()
    payload["construction"]["conditioned_floor_area_ft2"] = 10
    model, errors = validate_payload(payload)
    assert model is None
    assert any("conditioned_floor_area" in err["field"] for err in errors)


def test_rejects_heating_above_cooling():
    payload = default_payload()
    payload["systems"]["heating_setpoint_f"] = 80
    payload["systems"]["cooling_setpoint_f"] = 70
    model, errors = validate_payload(payload)
    assert model is None


def test_rejects_bad_zip():
    payload = default_payload()
    payload["site"]["postal_code"] = "CO"
    model, errors = validate_payload(payload)
    assert model is None


def test_rejects_window_area_larger_than_walls():
    payload = default_payload()
    payload["enclosure"]["wall_area_ft2"] = 100
    payload["enclosure"]["window_area_by_azimuth"] = {"0": 200, "180": 200}
    model, errors = validate_payload(payload)
    assert model is None
