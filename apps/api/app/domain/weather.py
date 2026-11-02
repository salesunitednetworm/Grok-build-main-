"""ZIP → TMY3 mapping from OpenStudio-HPXML's official zipcode_weather_stations.csv.

The official station for a ZIP is always reported. EnergyPlus only runs when an
EPW file exists: the official file if it is in the 1.12.0 weather/ folder,
otherwise the nearest shipped TMY3. That fallback is labeled. No kWh is invented
when a file is missing.
"""

from __future__ import annotations

import csv
import math
from functools import lru_cache
from pathlib import Path

from pydantic import BaseModel

from app.config import settings

OFFICIAL_CSV = Path(
    "/opt/OpenStudio-HPXML-1.12.0/HPXMLtoOpenStudio/resources/data/zipcode_weather_stations.csv"
)
FIXTURE_CSV = Path(__file__).resolve().parent.parent / "data" / "zipcode_weather_stations.fixture.csv"
OFFICIAL_WEATHER_DIR = Path("/opt/OpenStudio-HPXML-1.12.0/weather")


class WeatherStation(BaseModel):
    zipcode: str
    city: str
    state_code: str
    latitude: float
    longitude: float
    iecc_zone: str
    official_station: str
    official_epw: str
    official_station_name: str
    used_station: str
    used_epw: str
    weather_source: str
    epw_available: bool
    station_distance_km: float | None = None
    notes: str


def _csv_path() -> Path:
    tree = settings.openstudio_hpxml_dir
    if tree:
        candidate = Path(tree) / "HPXMLtoOpenStudio" / "resources" / "data" / "zipcode_weather_stations.csv"
        if candidate.exists():
            return candidate
    if OFFICIAL_CSV.exists():
        return OFFICIAL_CSV
    return FIXTURE_CSV


def _weather_dir() -> Path | None:
    tree = settings.openstudio_hpxml_dir
    if tree:
        folder = Path(tree) / "weather"
        if folder.is_dir():
            return folder
    if OFFICIAL_WEATHER_DIR.is_dir():
        return OFFICIAL_WEATHER_DIR
    return None


def _station_id(filename: str) -> str:
    name = filename.strip()
    return name[:-4] if name.endswith(".epw") else name


@lru_cache(maxsize=1)
def _rows() -> dict[str, dict[str, str]]:
    path = _csv_path()
    if not path.exists():
        return {}
    with path.open(newline="", encoding="utf-8") as handle:
        return {row["zipcode"]: row for row in csv.DictReader(handle)}


def shipped_epw_names() -> set[str]:
    folder = _weather_dir()
    if folder is None:
        return set()
    return {path.name for path in folder.glob("*.epw")}


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    radius = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return 2 * radius * math.asin(math.sqrt(a))


@lru_cache(maxsize=1)
def _shipped_station_coords() -> list[tuple[str, float, float]]:
    shipped = shipped_epw_names()
    coords: dict[str, tuple[float, float]] = {}
    for row in _rows().values():
        epw = row["station_filename"]
        if epw not in shipped or epw in coords:
            continue
        coords[epw] = (float(row["station_latitude"]), float(row["station_longitude"]))
    folder = _weather_dir()
    extras: list[tuple[str, float, float]] = []
    if folder is not None:
        for epw, (lat, lon) in coords.items():
            extras.append((epw, lat, lon))
        # Shipped files that never appear in the (possibly fixture-sized) CSV.
        known = {item[0] for item in extras}
        for path in folder.glob("*_TMY3.epw"):
            if path.name not in known:
                extras.append((path.name, 0.0, 0.0))
    return extras


def _nearest_shipped(lat: float, lon: float) -> tuple[str | None, float | None]:
    best: tuple[str | None, float | None] = (None, None)
    for epw, slat, slon in _shipped_station_coords():
        if slat == 0.0 and slon == 0.0:
            continue
        distance = _haversine_km(lat, lon, slat, slon)
        if best[1] is None or distance < best[1]:
            best = (epw, distance)
    if best[0] is None:
        shipped = sorted(name for name in shipped_epw_names() if name.endswith("_TMY3.epw"))
        if shipped:
            return shipped[0], None
    return best


def lookup_zip(postal_code: str) -> WeatherStation | None:
    zip5 = "".join(ch for ch in postal_code if ch.isdigit())[:5]
    if len(zip5) != 5:
        return None
    row = _rows().get(zip5)
    if row is None:
        return None
    official_epw = row["station_filename"]
    official = _station_id(official_epw)
    shipped = shipped_epw_names()
    lat = float(row["zipcode_latitude"])
    lon = float(row["zipcode_longitude"])
    if official_epw in shipped:
        used_epw = official_epw
        source = "official_mapped"
        distance = float(row["station_distance"]) if row.get("station_distance") else None
        notes = "Official OS-HPXML ZIP→TMY3 mapping; EPW is in the 1.12.0 weather/ folder."
        available = True
    else:
        used_epw, distance = _nearest_shipped(lat, lon)
        available = bool(used_epw and used_epw in shipped)
        source = "nearest_shipped" if available else "official_mapped"
        notes = (
            f"Official mapped station is {official}. That EPW is not in the 1.12.0 weather/ folder. "
            + (
                f"Using nearest shipped TMY3 { _station_id(used_epw) } so EnergyPlus can run."
                if available and used_epw
                else "No shipped EPW is available; EnergyPlus will not invent a climate."
            )
        )
        used_epw = used_epw or official_epw
    return WeatherStation(
        zipcode=zip5,
        city=row["zipcode_city"],
        state_code=row["zipcode_state"],
        latitude=lat,
        longitude=lon,
        iecc_zone=row["zipcode_iecc_zone"],
        official_station=official,
        official_epw=official_epw,
        official_station_name=row["station_name"],
        used_station=_station_id(used_epw),
        used_epw=used_epw,
        weather_source=source,
        epw_available=available,
        station_distance_km=distance,
        notes=notes,
    )


def apply_weather(payload: dict, postal_code: str | None = None) -> dict:
    """Fill IECC zone and weather station from the official ZIP table."""
    zipcode = postal_code or (payload.get("site") or {}).get("postal_code")
    if not zipcode:
        return payload
    station = lookup_zip(str(zipcode))
    if station is None:
        return payload
    site = payload.setdefault("site", {})
    if site.get("weather_source") == "user" and site.get("weather_station"):
        site.setdefault("official_weather_station", station.official_station)
        site.setdefault("iecc_zone", station.iecc_zone)
        return payload
    site["postal_code"] = station.zipcode
    site["state_code"] = site.get("state_code") or station.state_code
    site["iecc_zone"] = station.iecc_zone
    site["weather_station"] = station.used_station
    site["official_weather_station"] = station.official_station
    site["weather_source"] = station.weather_source
    site["weather_epw_available"] = station.epw_available
    return payload
