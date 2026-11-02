"""Map XSD / Schematron / emit messages onto canonical form fields."""

from __future__ import annotations

FIELD_HINTS = (
    ("zipcode", "site.postal_code"),
    ("statecode", "site.state_code"),
    ("address", "site.postal_code"),
    ("weatherstation", "site.weather_station"),
    ("epwfilepath", "site.weather_station"),
    ("climatezone", "site.iecc_zone"),
    ("conditionedfloorarea", "construction.conditioned_floor_area_ft2"),
    ("numberofbedrooms", "construction.bedrooms"),
    ("airleakage", "enclosure.ach50"),
    ("infiltration", "enclosure.ach50"),
    ("assemblyeffectivervalue", "enclosure.ceiling_assembly_r"),
    ("rimjoist", "enclosure.rim_joist_area_ft2"),
    ("attic", "enclosure.attic_type"),
    ("foundationtype", "enclosure.foundation_type"),
    ("crawlspace", "enclosure.foundation_type"),
    ("slabongrade", "enclosure.foundation_type"),
    ("basement", "enclosure.foundation_type"),
    ("ductleakage", "systems.duct_leakage_supply_cfm25"),
    ("cfm25", "systems.duct_leakage_supply_cfm25"),
    ("hspf", "systems.heating_efficiency_hspf2"),
    ("afue", "systems.heating_efficiency_afue"),
    ("seer", "systems.cooling_efficiency_seer2"),
    ("heatpump", "systems.heating_type"),
    ("heatingsystem", "systems.heating_type"),
    ("coolingsystem", "systems.cooling_type"),
    ("waterheater", "systems.dhw_type"),
    ("uniformenergyfactor", "systems.dhw_uef"),
    ("setpointtempheating", "systems.heating_setpoint_f"),
    ("setpointtempcooling", "systems.cooling_setpoint_f"),
    ("hvacdistribution", "systems.ductless"),
)


def map_engine_error(message: str, code: str = "schema") -> dict[str, str]:
    lowered = message.lower().replace(" ", "").replace("_", "").replace("-", "")
    field = "hpxml"
    for hint, path in FIELD_HINTS:
        if hint in lowered:
            field = path
            break
    return {"code": code, "field": field, "message": message}


def map_engine_errors(messages: list[dict[str, str] | str], code: str = "schema") -> list[dict[str, str]]:
    mapped: list[dict[str, str]] = []
    for item in messages:
        if isinstance(item, dict):
            message = item.get("message") or str(item)
            existing_field = item.get("field")
            if existing_field and existing_field not in {"hpxml", "Address"}:
                mapped.append({"code": item.get("code", code), "field": existing_field, "message": message})
                continue
            row = map_engine_error(message, item.get("code", code))
            if existing_field == "Address":
                row["field"] = "site.postal_code"
            mapped.append(row)
        else:
            mapped.append(map_engine_error(str(item), code))
    return mapped
