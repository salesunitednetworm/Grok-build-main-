from fastapi.testclient import TestClient

from app.services_address import (
    census_standardize,
    fill_address,
    map_census_match,
    map_esri_suggestion,
    map_smarty_suggestion,
    parse_one_line,
    suggest_addresses,
)

ESRI_TRYON = {
    "text": "100 N Tryon St, Charlotte, NC, 28202, USA",
    "magicKey": "tryon-key",
    "isCollection": False,
}
ESRI_EDENTON = {
    "text": "1 E Edenton St, Raleigh, NC, 27601, USA",
    "magicKey": "edenton-key",
    "isCollection": False,
}
ESRI_CAPITOL = {
    "text": "206 Washington St SW, Atlanta, GA, 30334, USA",
    "magicKey": "capitol-key",
    "isCollection": False,
}
ESRI_POI_COLLECTION = {
    "text": "Tryon, NC, USA",
    "magicKey": "city-key",
    "isCollection": True,
}
CENSUS_TRYON = {
    "matchedAddress": "100 N TRYON ST, CHARLOTTE, NC, 28202",
    "addressComponents": {
        "fromAddress": "100",
        "preDirection": "N",
        "streetName": "TRYON",
        "suffixType": "ST",
        "city": "CHARLOTTE",
        "state": "NC",
        "zip": "28202",
    },
}


def test_parse_esri_us_line():
    parsed = parse_one_line("100 N Tryon St, Charlotte, NC, 28202, USA")
    assert parsed is not None
    assert parsed.street == "100 N Tryon St"
    assert parsed.city == "Charlotte"
    assert parsed.state_code == "NC"
    assert parsed.postal_code == "28202"


def test_esri_maps_house_level_and_drops_collections():
    mapped = map_esri_suggestion(ESRI_TRYON, "100 N Tryon")
    assert mapped is not None
    assert mapped.source == "esri"
    assert mapped.id == "esri:tryon-key"
    assert map_esri_suggestion(ESRI_POI_COLLECTION, "100 N Tryon") is None


def test_esri_requires_query_house_number():
    other = {
        "text": "200 N Tryon St, Charlotte, NC, 28202, USA",
        "magicKey": "other",
        "isCollection": False,
    }
    assert map_esri_suggestion(other, "100 N Tryon") is None


def test_smarty_maps_without_inventing_zip():
    mapped = map_smarty_suggestion(
        {"street_line": "1 E Edenton St", "city": "Raleigh", "state": "NC"},
        "1 E Edenton",
    )
    assert mapped is not None
    assert mapped.postal_code is None
    assert mapped.city == "Raleigh"


def test_census_standardizes_components():
    mapped = map_census_match(CENSUS_TRYON)
    assert mapped is not None
    assert mapped.street == "100 N Tryon St"
    assert mapped.city == "Charlotte"
    assert mapped.state_code == "NC"
    assert mapped.postal_code == "28202"
    assert mapped.source == "census"


def test_suggest_rejects_short_or_street_only_queries():
    items, _source = suggest_addresses("12")
    assert items == []
    items, _source = suggest_addresses("Tryon Street")
    assert items == []


def test_suggest_uses_esri_and_keeps_nc_ga(monkeypatch):
    def fake_fetch(url: str, params: dict[str, str]):
        assert "geocode.arcgis.com" in url
        assert params["countryCode"] == "USA"
        assert params["category"] == "Address"
        return {"suggestions": [ESRI_TRYON, ESRI_EDENTON, ESRI_CAPITOL, ESRI_POI_COLLECTION]}

    monkeypatch.setattr("app.services_address.fetch_json", fake_fetch)
    items, source = suggest_addresses("100 N Tryon")
    assert source == "esri"
    assert [item.city for item in items] == ["Charlotte"]
    assert items[0].state_code == "NC"
    assert items[0].postal_code == "28202"


def test_fill_prefers_census_zip(monkeypatch):
    selected = map_esri_suggestion(ESRI_TRYON, "100 N Tryon")
    assert selected is not None

    def fake_fetch(url: str, params: dict[str, str]):
        if "census.gov" in url:
            return {"result": {"addressMatches": [CENSUS_TRYON]}}
        return {"candidates": []}

    monkeypatch.setattr("app.services_address.fetch_json", fake_fetch)
    monkeypatch.setattr("app.services_address.resolve_esri", lambda *_args: selected)
    filled = fill_address(selected.label, selected)
    assert filled is not None
    assert filled.postal_code == "28202"


def test_address_suggestions_are_post_only(client: TestClient, monkeypatch):
    monkeypatch.setattr(
        "app.services_address.suggest_addresses",
        lambda _q: ([map_esri_suggestion(ESRI_TRYON, "100 N Tryon")], "esri"),
    )
    get_response = client.get("/api/v1/address-suggestions", params={"q": "100 N Tryon"})
    assert get_response.status_code == 405
    response = client.post("/api/v1/address-suggestions", json={"query": "100 N Tryon"})
    assert response.status_code == 200
    body = response.json()
    assert "query" not in body
    assert body["source"] == "esri"
    assert body["items"][0]["street"] == "100 N Tryon St"
    assert body["items"][0]["state_code"] == "NC"


def test_address_lookup_endpoint(client: TestClient, monkeypatch):
    monkeypatch.setattr(
        "app.services_address.census_standardize",
        lambda _address: map_census_match(CENSUS_TRYON),
    )
    monkeypatch.setattr(
        "app.services_address.resolve_esri",
        lambda *_args: map_esri_suggestion(ESRI_TRYON, "100 N Tryon"),
    )
    response = client.post(
        "/api/v1/address-lookup",
        json={
            "address": "100 N Tryon St, Charlotte, NC, 28202",
            "street": "100 N Tryon St",
            "city": "Charlotte",
            "state_code": "NC",
            "source": "esri",
            "id": "esri:tryon-key",
        },
    )
    assert response.status_code == 200
    assert response.json()["postal_code"] == "28202"


def test_census_standardize_empty_line_skips_network():
    assert census_standardize("   ") is None
