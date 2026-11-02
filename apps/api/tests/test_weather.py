from app.domain.weather import apply_weather, lookup_zip


def test_miami_maps_to_official_miami_tmy3():
    station = lookup_zip("33101")
    assert station is not None
    assert station.official_station == "USA_FL_Miami.Intl.AP.722020_TMY3"
    assert station.iecc_zone == "1A"
    assert station.state_code == "FL"
    if station.epw_available:
        assert station.used_station == station.official_station
        assert station.weather_source == "official_mapped"


def test_phoenix_and_portland_are_not_denver():
    phoenix = lookup_zip("85001")
    portland = lookup_zip("97201")
    assert phoenix is not None and portland is not None
    assert "Phoenix" in phoenix.official_station
    assert "Portland" in portland.official_station
    assert phoenix.official_station != portland.official_station
    assert "Denver" not in phoenix.official_station


def test_denver_zip_reports_official_and_may_fallback():
    station = lookup_zip("80202")
    assert station is not None
    assert station.iecc_zone == "5B"
    assert station.official_station == "USA_CO_Boulder-Broomfield-Jefferson.County.AP.724699_TMY3"
    if not station.epw_available or station.weather_source == "nearest_shipped":
        assert station.used_station != station.official_station
        assert "not in the 1.12.0 weather" in station.notes


def test_apply_weather_fills_payload():
    payload = {"site": {"postal_code": "33101", "state_code": "XX", "weather_source": "default"}}
    apply_weather(payload)
    assert payload["site"]["iecc_zone"] == "1A"
    assert "Miami" in payload["site"]["official_weather_station"]
    assert payload["site"]["weather_station"]


def test_unknown_zip_is_none():
    assert lookup_zip("00000") is None
