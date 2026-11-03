"""Street-address suggestions from documented public geocoders.

Photon (https://photon.komoot.io/) is the typeahead source: it is a
no-key OpenStreetMap geocoder that returns house-number matches for
partial US streets. The US Census Bureau Geocoder
(https://geocoding.geo.census.gov/geocoder/Geocoding_Services_API.html)
is used on select to standardize city / state / ZIP when it has a
match. Census is not used for typeahead; live probes return zero
matches for incomplete streets such as \"12 Pine\".

Neither path invents a street, city, state, or ZIP. Missing fields stay
empty.
"""

from __future__ import annotations

from typing import Any

import httpx

from app.schemas import AddressSuggestion

PHOTON_URL = "https://photon.komoot.io/api/"
CENSUS_URL = "https://geocoding.geo.census.gov/geocoder/locations/onelineaddress"
USER_AGENT = "hems-address/0.5.1 (home energy modeling demo)"
MIN_QUERY = 3
SUGGEST_LIMIT = 8

# Full names as Photon / OSM emit them. Abbreviations pass through.
US_STATE_CODES: dict[str, str] = {
    "ALABAMA": "AL",
    "ALASKA": "AK",
    "ARIZONA": "AZ",
    "ARKANSAS": "AR",
    "CALIFORNIA": "CA",
    "COLORADO": "CO",
    "CONNECTICUT": "CT",
    "DELAWARE": "DE",
    "DISTRICT OF COLUMBIA": "DC",
    "FLORIDA": "FL",
    "GEORGIA": "GA",
    "HAWAII": "HI",
    "IDAHO": "ID",
    "ILLINOIS": "IL",
    "INDIANA": "IN",
    "IOWA": "IA",
    "KANSAS": "KS",
    "KENTUCKY": "KY",
    "LOUISIANA": "LA",
    "MAINE": "ME",
    "MARYLAND": "MD",
    "MASSACHUSETTS": "MA",
    "MICHIGAN": "MI",
    "MINNESOTA": "MN",
    "MISSISSIPPI": "MS",
    "MISSOURI": "MO",
    "MONTANA": "MT",
    "NEBRASKA": "NE",
    "NEVADA": "NV",
    "NEW HAMPSHIRE": "NH",
    "NEW JERSEY": "NJ",
    "NEW MEXICO": "NM",
    "NEW YORK": "NY",
    "NORTH CAROLINA": "NC",
    "NORTH DAKOTA": "ND",
    "OHIO": "OH",
    "OKLAHOMA": "OK",
    "OREGON": "OR",
    "PENNSYLVANIA": "PA",
    "RHODE ISLAND": "RI",
    "SOUTH CAROLINA": "SC",
    "SOUTH DAKOTA": "SD",
    "TENNESSEE": "TN",
    "TEXAS": "TX",
    "UTAH": "UT",
    "VERMONT": "VT",
    "VIRGINIA": "VA",
    "WASHINGTON": "WA",
    "WEST VIRGINIA": "WV",
    "WISCONSIN": "WI",
    "WYOMING": "WY",
}


def fetch_json(url: str, params: dict[str, str]) -> dict[str, Any]:
    with httpx.Client(timeout=8.0, headers={"User-Agent": USER_AGENT}) as client:
        response = client.get(url, params=params)
        response.raise_for_status()
        payload = response.json()
    if not isinstance(payload, dict):
        raise ValueError("geocoder returned a non-object")
    return payload


def state_code(value: str | None) -> str | None:
    if not value:
        return None
    raw = value.strip()
    if not raw:
        return None
    if len(raw) == 2 and raw.isalpha():
        return raw.upper()
    return US_STATE_CODES.get(raw.upper())


def _text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _title_street(value: str) -> str:
    parts: list[str] = []
    for part in value.split():
        trailing = ""
        core = part
        while core and core[-1] in ",.":
            trailing = core[-1] + trailing
            core = core[:-1]
        lower = core.lower()
        if lower in {"nw", "ne", "sw", "se"}:
            styled = lower.upper()
        elif core:
            styled = core[:1].upper() + core[1:].lower()
        else:
            styled = core
        parts.append(f"{styled}{trailing}")
    return " ".join(parts)


def street_from_photon(props: dict[str, Any]) -> str | None:
    number = _text(props.get("housenumber"))
    street = _text(props.get("street"))
    if number and street:
        return f"{number} {street}"
    if street:
        return street
    return _text(props.get("name"))


def city_from_photon(props: dict[str, Any]) -> str | None:
    for key in ("city", "locality", "town", "village", "district"):
        value = _text(props.get(key))
        if value:
            return value
    return None


def _is_us(props: dict[str, Any]) -> bool:
    country = (_text(props.get("countrycode")) or _text(props.get("country")) or "").upper()
    if country in {"US", "USA", "UNITED STATES"}:
        return True
    return state_code(props.get("state")) is not None and country in {"", "US", "USA", "UNITED STATES"}


def _label(street: str, city: str | None, state: str | None, postal: str | None) -> str:
    tail = ", ".join(part for part in (city, state, postal) if part)
    return f"{street}, {tail}" if tail else street


def map_photon_feature(feature: dict[str, Any]) -> AddressSuggestion | None:
    props = feature.get("properties") if isinstance(feature, dict) else None
    if not isinstance(props, dict) or not _is_us(props):
        return None
    street = street_from_photon(props)
    city = city_from_photon(props)
    state = state_code(props.get("state"))
    postal = _text(props.get("postcode"))
    if not street or not (city or state):
        return None
    osm_type = _text(props.get("osm_type")) or "x"
    osm_id = props.get("osm_id")
    return AddressSuggestion(
        id=f"photon:{osm_type}:{osm_id}" if osm_id is not None else _label(street, city, state, postal),
        label=_label(street, city, state, postal),
        street=street,
        city=city,
        state_code=state,
        postal_code=postal,
        source="photon",
    )


def suggest_addresses(query: str) -> list[AddressSuggestion]:
    q = query.strip()
    if len(q) < MIN_QUERY:
        return []
    try:
        payload = fetch_json(PHOTON_URL, {"q": q, "limit": str(SUGGEST_LIMIT), "lang": "en"})
    except (httpx.HTTPError, ValueError):
        return []
    seen: set[str] = set()
    items: list[AddressSuggestion] = []
    for feature in payload.get("features") or []:
        mapped = map_photon_feature(feature) if isinstance(feature, dict) else None
        if mapped is None or mapped.label in seen:
            continue
        seen.add(mapped.label)
        items.append(mapped)
        if len(items) >= SUGGEST_LIMIT:
            break
    return items


def map_census_match(match: dict[str, Any]) -> AddressSuggestion | None:
    comps = match.get("addressComponents") if isinstance(match, dict) else None
    if not isinstance(comps, dict):
        return None
    number = _text(comps.get("fromAddress"))
    street_name = " ".join(
        part
        for part in (
            _text(comps.get("preType")),
            _text(comps.get("preDirection")),
            _text(comps.get("streetName")),
            _text(comps.get("suffixType")),
            _text(comps.get("suffixDirection")),
        )
        if part
    )
    raw_street = " ".join(part for part in (number, street_name) if part)
    if not raw_street:
        return None
    street = _title_street(raw_street)
    city_raw = _text(comps.get("city"))
    city = _title_street(city_raw) if city_raw else None
    state = state_code(comps.get("state"))
    postal = _text(comps.get("zip"))
    matched = _text(match.get("matchedAddress"))
    label = _title_street(matched) if matched else _label(street, city, state, postal)
    return AddressSuggestion(
        id=f"census:{label}",
        label=label,
        street=street,
        city=city,
        state_code=state,
        postal_code=postal,
        source="census",
    )


def census_standardize(address: str) -> AddressSuggestion | None:
    line = address.strip()
    if not line:
        return None
    try:
        payload = fetch_json(
            CENSUS_URL,
            {"address": line, "benchmark": "Public_AR_Current", "format": "json"},
        )
    except (httpx.HTTPError, ValueError):
        return None
    matches = ((payload.get("result") or {}).get("addressMatches")) or []
    if not matches or not isinstance(matches[0], dict):
        return None
    return map_census_match(matches[0])


def merge_suggestion(
    primary: AddressSuggestion,
    standardized: AddressSuggestion | None,
) -> AddressSuggestion:
    """Prefer Census fields when present. Never invent a missing ZIP."""
    if standardized is None:
        return primary
    return AddressSuggestion(
        id=standardized.id,
        label=standardized.label or primary.label,
        street=standardized.street or primary.street,
        city=standardized.city or primary.city,
        state_code=standardized.state_code or primary.state_code,
        postal_code=standardized.postal_code or primary.postal_code,
        source=standardized.source,
    )


def fill_address(
    address: str,
    selected: AddressSuggestion | None = None,
) -> AddressSuggestion | None:
    standardized = census_standardize(address)
    if selected is None:
        return standardized
    return merge_suggestion(selected, standardized)
