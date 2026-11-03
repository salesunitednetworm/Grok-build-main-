from fastapi.testclient import TestClient

from app.services_address import (
    census_standardize,
    fill_address,
    map_census_match,
    map_photon_feature,
    suggest_addresses,
)

PHOTON_WHITE_HOUSE = {
    "type": "Feature",
    "properties": {
        "osm_type": "W",
        "osm_id": 23824122,
        "name": "White House",
        "housenumber": "1600",
        "street": "Pennsylvania Avenue Northwest",
        "city": "Washington",
        "state": "District of Columbia",
        "postcode": "20500",
        "country": "United States",
        "countrycode": "US",
    },
}

PHOTON_NO_ZIP = {
    "type": "Feature",
    "properties": {
        "osm_type": "N",
        "osm_id": 1,
        "housenumber": "12",
        "street": "Pine Street",
        "city": "Denver",
        "state": "Colorado",
        "countrycode": "US",
    },
}

PHOTON_CANADA = {
    "type": "Feature",
    "properties": {
        "osm_type": "W",
        "osm_id": 9,
        "housenumber": "100",
        "street": "Queen Street West",
        "city": "Toronto",
        "state": "Ontario",
        "postcode": "M5H 2N2",
        "countrycode": "CA",
    },
}

CENSUS_WHITE_HOUSE = {
    "matchedAddress": "1600 PENNSYLVANIA AVE NW, WASHINGTON, DC, 20500",
    "addressComponents": {
        "fromAddress": "1600",
        "streetName": "PENNSYLVANIA",
        "suffixType": "AVE",
        "suffixDirection": "NW",
        "city": "WASHINGTON",
        "state": "DC",
        "zip": "20500",
    },
}


def test_photon_maps_us_house_without_inventing_fields():
    mapped = map_photon_feature(PHOTON_WHITE_HOUSE)
    assert mapped is not None
    assert mapped.street == "1600 Pennsylvania Avenue Northwest"
    assert mapped.city == "Washington"
    assert mapped.state_code == "DC"
    assert mapped.postal_code == "20500"
    assert mapped.source == "photon"


def test_photon_keeps_missing_zip_empty():
    mapped = map_photon_feature(PHOTON_NO_ZIP)
    assert mapped is not None
    assert mapped.street == "12 Pine Street"
    assert mapped.city == "Denver"
    assert mapped.state_code == "CO"
    assert mapped.postal_code is None


def test_photon_drops_non_us():
    assert map_photon_feature(PHOTON_CANADA) is None


def test_census_standardizes_components():
    mapped = map_census_match(CENSUS_WHITE_HOUSE)
    assert mapped is not None
    assert mapped.street == "1600 Pennsylvania Ave NW"
    assert mapped.city == "Washington"
    assert mapped.state_code == "DC"
    assert mapped.postal_code == "20500"
    assert mapped.source == "census"


def test_suggest_short_query_skips_network():
    assert suggest_addresses("12") == []


def test_suggest_uses_photon_payload(monkeypatch):
    def fake_fetch(url: str, params: dict[str, str]):
        assert "photon.komoot.io" in url
        assert params["q"] == "1600 Pennsylvania"
        return {"features": [PHOTON_WHITE_HOUSE, PHOTON_CANADA]}

    monkeypatch.setattr("app.services_address.fetch_json", fake_fetch)
    items = suggest_addresses("1600 Pennsylvania")
    assert len(items) == 1
    assert items[0].city == "Washington"
    assert items[0].postal_code == "20500"


def test_fill_prefers_census_zip_when_photon_omits_it(monkeypatch):
    selected = map_photon_feature(PHOTON_NO_ZIP)
    assert selected is not None

    def fake_fetch(url: str, params: dict[str, str]):
        assert "geocoding.geo.census.gov" in url
        return {"result": {"addressMatches": [CENSUS_WHITE_HOUSE]}}

    monkeypatch.setattr("app.services_address.fetch_json", fake_fetch)
    filled = fill_address("12 Pine Street, Denver, CO", selected)
    assert filled is not None
    assert filled.postal_code == "20500"
    assert filled.source == "census"


def test_fill_keeps_photon_when_census_has_no_match(monkeypatch):
    selected = map_photon_feature(PHOTON_NO_ZIP)
    assert selected is not None

    def fake_fetch(url: str, params: dict[str, str]):
        return {"result": {"addressMatches": []}}

    monkeypatch.setattr("app.services_address.fetch_json", fake_fetch)
    filled = fill_address("12 Pine Street, Denver, CO", selected)
    assert filled is not None
    assert filled.street == "12 Pine Street"
    assert filled.postal_code is None


def test_address_suggestions_endpoint(client: TestClient, monkeypatch):
    monkeypatch.setattr(
        "app.services_address.suggest_addresses",
        lambda q: [map_photon_feature(PHOTON_WHITE_HOUSE)],
    )
    response = client.get("/api/v1/address-suggestions", params={"q": "1600 Penn"})
    assert response.status_code == 200
    body = response.json()
    assert body["source"] == "photon"
    assert body["items"][0]["street"].startswith("1600")
    assert body["items"][0]["postal_code"] == "20500"


def test_address_lookup_endpoint(client: TestClient, monkeypatch):
    monkeypatch.setattr(
        "app.services_address.census_standardize",
        lambda _address: map_census_match(CENSUS_WHITE_HOUSE),
    )
    response = client.post(
        "/api/v1/address-lookup",
        json={
            "address": "1600 Pennsylvania Avenue Northwest, Washington, DC",
            "street": "1600 Pennsylvania Avenue Northwest",
            "city": "Washington",
            "state_code": "DC",
            "source": "photon",
        },
    )
    assert response.status_code == 200
    assert response.json()["postal_code"] == "20500"


def test_census_standardize_empty_line_skips_network():
    assert census_standardize("   ") is None
