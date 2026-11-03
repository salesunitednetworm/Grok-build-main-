"""Production US street typeahead.

Photon / OSM ranked parks, businesses, and foreign streets ahead of
ordinary US homes, so it is not used. Typeahead is a documented
production geocoder, in this order when credentials exist:

1. Smarty US Autocomplete Pro — ``SMARTY_AUTH_ID`` + ``SMARTY_AUTH_TOKEN``
2. Google Places Autocomplete — ``GOOGLE_PLACES_API_KEY`` or ``GOOGLE_MAPS_API_KEY``
3. Mapbox Geocoding v5 — ``MAPBOX_ACCESS_TOKEN``
4. Esri World Geocoding Service suggest (no key required)
   https://developers.arcgis.com/rest/geocode/api-reference/geocoding-suggest.htm

Selected lines are resolved to city / state / ZIP, then standardized
with the US Census Geocoder onelineaddress when Census has a match.
House number + street are required. Missing ZIP stays empty. Queries
are not written to application logs.
"""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import quote

import httpx

from app.config import settings
from app.schemas import AddressSuggestion

ESRI_SUGGEST_URL = "https://geocode.arcgis.com/arcgis/rest/services/World/GeocodeServer/suggest"
ESRI_FIND_URL = "https://geocode.arcgis.com/arcgis/rest/services/World/GeocodeServer/findAddressCandidates"
CENSUS_URL = "https://geocoding.geo.census.gov/geocoder/locations/onelineaddress"
SMARTY_URL = "https://us-autocomplete-pro.api.smarty.com/lookup"
GOOGLE_AUTOCOMPLETE_URL = "https://maps.googleapis.com/maps/api/place/autocomplete/json"
GOOGLE_DETAILS_URL = "https://maps.googleapis.com/maps/api/place/details/json"
MAPBOX_GEOCODE_URL = "https://api.mapbox.com/geocoding/v5/mapbox.places"
USER_AGENT = "hems-address/0.5.2 (home energy modeling)"
MIN_QUERY = 3
SUGGEST_LIMIT = 8
HOUSE_RE = re.compile(r"^(\d+[A-Za-z]?)\b")
ZIP_RE = re.compile(r"^\d{5}(?:-\d{4})?$")
HOUSE_LEVEL_TYPES = {"PointAddress", "StreetAddress", "Subaddress"}

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


def house_number(value: str | None) -> str | None:
    if not value:
        return None
    match = HOUSE_RE.match(value.strip())
    return match.group(1) if match else None


def _label(street: str, city: str | None, state: str | None, postal: str | None) -> str:
    tail = ", ".join(part for part in (city, state, postal) if part)
    return f"{street}, {tail}" if tail else street


def _suggestion(
    *,
    ident: str,
    street: str,
    city: str | None,
    state: str | None,
    postal: str | None,
    source: str,
    label: str | None = None,
) -> AddressSuggestion | None:
    if not street or house_number(street) is None:
        return None
    if not (city or state):
        return None
    return AddressSuggestion(
        id=ident,
        label=label or _label(street, city, state, postal),
        street=street,
        city=city,
        state_code=state,
        postal_code=postal,
        source=source,
    )


def parse_one_line(text: str) -> AddressSuggestion | None:
    raw = text.strip()
    if not raw:
        return None
    parts = [part.strip() for part in raw.split(",") if part.strip()]
    if parts and parts[-1].upper() in {"USA", "US", "UNITED STATES"}:
        parts = parts[:-1]
    postal = None
    state = None
    if parts and ZIP_RE.match(parts[-1].split()[0] if parts[-1] else ""):
        postal = parts.pop()[:5]
    if parts:
        state = state_code(parts[-1])
        if state:
            parts = parts[:-1]
    city = parts.pop() if len(parts) >= 2 else None
    street = ", ".join(parts) if parts else None
    if not street:
        return None
    return _suggestion(
        ident=f"line:{raw}",
        street=street,
        city=city,
        state=state,
        postal=postal,
        source="parsed",
        label=_label(street, city, state, postal),
    )


def _matches_query_house(query: str, street: str) -> bool:
    wanted = house_number(query)
    if wanted is None:
        return house_number(street) is not None
    return house_number(street) == wanted


def _dedupe(items: list[AddressSuggestion]) -> list[AddressSuggestion]:
    seen: set[str] = set()
    out: list[AddressSuggestion] = []
    for item in items:
        key = (item.street or "").lower() + "|" + (item.city or "").lower() + "|" + (item.state_code or "") + "|" + (item.postal_code or "")
        if key in seen:
            continue
        seen.add(key)
        out.append(item)
        if len(out) >= SUGGEST_LIMIT:
            break
    return out


def active_geocoder() -> str:
    if settings.smarty_auth_id and settings.smarty_auth_token:
        return "smarty"
    if settings.google_places_api_key or settings.google_maps_api_key:
        return "google"
    if settings.mapbox_access_token:
        return "mapbox"
    return "esri"


def map_esri_suggestion(row: dict[str, Any], query: str) -> AddressSuggestion | None:
    if row.get("isCollection"):
        return None
    text = _text(row.get("text"))
    magic = _text(row.get("magicKey"))
    if not text:
        return None
    parsed = parse_one_line(text)
    if parsed is None or not _matches_query_house(query, parsed.street):
        return None
    return parsed.model_copy(update={"id": f"esri:{magic}" if magic else parsed.id, "source": "esri"})


def suggest_esri(query: str) -> list[AddressSuggestion]:
    params = {
        "text": query,
        "f": "json",
        "countryCode": "USA",
        "category": "Address",
        "maxSuggestions": "15",
    }
    if settings.arcgis_geocode_token:
        params["token"] = settings.arcgis_geocode_token
    payload = fetch_json(ESRI_SUGGEST_URL, params)
    items: list[AddressSuggestion] = []
    for row in payload.get("suggestions") or []:
        if not isinstance(row, dict):
            continue
        mapped = map_esri_suggestion(row, query)
        if mapped is not None:
            items.append(mapped)
    return _dedupe(items)


def resolve_esri(label: str, magic_key: str) -> AddressSuggestion | None:
    params = {
        "SingleLine": label,
        "magicKey": magic_key,
        "f": "json",
        "countryCode": "USA",
        "category": "Address",
        "maxLocations": "1",
        "outFields": "Addr_type,StAddr,City,RegionAbbr,Postal,Score",
        "forStorage": "false",
    }
    if settings.arcgis_geocode_token:
        params["token"] = settings.arcgis_geocode_token
    try:
        payload = fetch_json(ESRI_FIND_URL, params)
    except (httpx.HTTPError, ValueError):
        return None
    candidates = payload.get("candidates") or []
    if not candidates or not isinstance(candidates[0], dict):
        return None
    attrs = candidates[0].get("attributes") or {}
    if not isinstance(attrs, dict):
        return None
    if _text(attrs.get("Addr_type")) not in HOUSE_LEVEL_TYPES:
        return parse_one_line(label)
    street = _text(attrs.get("StAddr"))
    city = _text(attrs.get("City"))
    state = state_code(attrs.get("RegionAbbr"))
    postal = _text(attrs.get("Postal"))
    return _suggestion(
        ident=f"esri:{magic_key}",
        street=street or "",
        city=city,
        state=state,
        postal=postal,
        source="esri",
    ) or parse_one_line(label)


def map_smarty_suggestion(row: dict[str, Any], query: str) -> AddressSuggestion | None:
    street = _text(row.get("street_line"))
    city = _text(row.get("city"))
    state = state_code(row.get("state"))
    postal = _text(row.get("zipcode"))
    if street is None or not _matches_query_house(query, street):
        return None
    return _suggestion(
        ident=f"smarty:{street}|{city}|{state}|{postal}",
        street=street,
        city=city,
        state=state,
        postal=postal,
        source="smarty",
    )


def suggest_smarty(query: str) -> list[AddressSuggestion]:
    payload = fetch_json(
        SMARTY_URL,
        {
            "search": query,
            "max_results": str(SUGGEST_LIMIT),
            "auth-id": settings.smarty_auth_id,
            "auth-token": settings.smarty_auth_token,
        },
    )
    items: list[AddressSuggestion] = []
    for row in payload.get("suggestions") or []:
        if isinstance(row, dict):
            mapped = map_smarty_suggestion(row, query)
            if mapped is not None:
                items.append(mapped)
    return _dedupe(items)


def map_google_prediction(row: dict[str, Any], query: str) -> AddressSuggestion | None:
    description = _text(row.get("description"))
    place_id = _text(row.get("place_id"))
    if not description:
        return None
    parsed = parse_one_line(description)
    if parsed is None or not _matches_query_house(query, parsed.street):
        return None
    return parsed.model_copy(update={"id": f"google:{place_id}" if place_id else parsed.id, "source": "google"})


def suggest_google(query: str) -> list[AddressSuggestion]:
    key = settings.google_places_api_key or settings.google_maps_api_key
    payload = fetch_json(
        GOOGLE_AUTOCOMPLETE_URL,
        {"input": query, "types": "address", "components": "country:us", "key": key},
    )
    items: list[AddressSuggestion] = []
    for row in payload.get("predictions") or []:
        if isinstance(row, dict):
            mapped = map_google_prediction(row, query)
            if mapped is not None:
                items.append(mapped)
    return _dedupe(items)


def resolve_google(place_id: str) -> AddressSuggestion | None:
    key = settings.google_places_api_key or settings.google_maps_api_key
    try:
        payload = fetch_json(
            GOOGLE_DETAILS_URL,
            {"place_id": place_id, "fields": "address_component,formatted_address", "key": key},
        )
    except (httpx.HTTPError, ValueError):
        return None
    result = payload.get("result") if isinstance(payload.get("result"), dict) else {}
    comps = result.get("address_components") if isinstance(result, dict) else None
    if not isinstance(comps, list):
        return None
    by_type: dict[str, str] = {}
    for item in comps:
        if not isinstance(item, dict):
            continue
        types = item.get("types") or []
        value = _text(item.get("short_name")) or _text(item.get("long_name"))
        if value:
            for typ in types:
                by_type[str(typ)] = value
    number = by_type.get("street_number")
    route = by_type.get("route")
    street = " ".join(part for part in (number, route) if part)
    city = by_type.get("locality") or by_type.get("sublocality") or by_type.get("neighborhood")
    state = state_code(by_type.get("administrative_area_level_1"))
    postal = by_type.get("postal_code")
    return _suggestion(ident=f"google:{place_id}", street=street, city=city, state=state, postal=postal, source="google")


def map_mapbox_feature(feature: dict[str, Any], query: str) -> AddressSuggestion | None:
    props = feature.get("properties") if isinstance(feature, dict) else None
    if feature.get("id") and str(feature.get("id")).startswith("poi."):
        return None
    number = _text((props or {}).get("address")) or _text(feature.get("address"))
    street_name = _text(feature.get("text"))
    street = " ".join(part for part in (number, street_name) if part) if number else None
    city = None
    state = None
    postal = None
    for item in feature.get("context") or []:
        if not isinstance(item, dict):
            continue
        ident = str(item.get("id") or "")
        text = _text(item.get("text"))
        if ident.startswith("place") or ident.startswith("locality"):
            city = city or text
        elif ident.startswith("region"):
            state = state_code(item.get("short_code") and str(item.get("short_code")).split("-")[-1]) or state_code(text)
        elif ident.startswith("postcode"):
            postal = text
    if street is None:
        parsed = parse_one_line(_text(feature.get("place_name")) or "")
        return parsed.model_copy(update={"source": "mapbox"}) if parsed and _matches_query_house(query, parsed.street) else None
    if not _matches_query_house(query, street):
        return None
    return _suggestion(
        ident=f"mapbox:{feature.get('id')}",
        street=street,
        city=city,
        state=state,
        postal=postal,
        source="mapbox",
    )


def suggest_mapbox(query: str) -> list[AddressSuggestion]:
    url = f"{MAPBOX_GEOCODE_URL}/{quote(query)}.json"
    payload = fetch_json(
        url,
        {
            "access_token": settings.mapbox_access_token,
            "country": "us",
            "types": "address",
            "limit": str(SUGGEST_LIMIT),
            "autocomplete": "true",
        },
    )
    items: list[AddressSuggestion] = []
    for feature in payload.get("features") or []:
        if isinstance(feature, dict):
            mapped = map_mapbox_feature(feature, query)
            if mapped is not None:
                items.append(mapped)
    return _dedupe(items)


def suggest_addresses(query: str) -> tuple[list[AddressSuggestion], str]:
    q = query.strip()
    source = active_geocoder()
    if len(q) < MIN_QUERY or house_number(q) is None:
        return [], source
    try:
        if source == "smarty":
            items = suggest_smarty(q)
        elif source == "google":
            items = suggest_google(q)
        elif source == "mapbox":
            items = suggest_mapbox(q)
        else:
            items = suggest_esri(q)
    except (httpx.HTTPError, ValueError, KeyError):
        items = []
    return items, source


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
    return _suggestion(
        ident=f"census:{label}",
        street=street,
        city=city,
        state=state,
        postal=postal,
        source="census",
        label=label,
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


def _resolve_selected(selected: AddressSuggestion) -> AddressSuggestion:
    ident = selected.id or ""
    if ident.startswith("esri:") and ident.split(":", 1)[1]:
        return resolve_esri(selected.label, ident.split(":", 1)[1]) or selected
    if ident.startswith("google:") and ident.split(":", 1)[1]:
        return resolve_google(ident.split(":", 1)[1]) or selected
    return selected


def fill_address(
    address: str,
    selected: AddressSuggestion | None = None,
) -> AddressSuggestion | None:
    resolved = _resolve_selected(selected) if selected is not None else None
    line = resolved.label if resolved is not None else address
    standardized = census_standardize(line)
    if resolved is None:
        return standardized
    return merge_suggestion(resolved, standardized)
