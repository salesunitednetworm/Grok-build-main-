from __future__ import annotations

import copy
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator

SCHEMA_ID = "hems.building/v1"
FacilityType = Literal["single-family detached"]
FoundationType = Literal["conditioned_basement", "slab_on_grade"]
HeatingType = Literal["furnace"]
CoolingType = Literal["central air conditioner"]
HeatingFuel = Literal["natural gas", "electricity"]
DhwType = Literal["storage water heater"]
DhwFuel = Literal["electricity", "natural gas"]
DataSource = Literal["user", "default", "measured"]


class Site(BaseModel):
    state_code: str = Field(min_length=2, max_length=2)
    postal_code: str
    azimuth_front: int = Field(default=180, ge=0, le=359)
    iecc_zone: str = "5B"
    weather_station: str = "USA_CO_Denver.Intl.AP.725650_TMY3"

    @field_validator("state_code")
    @classmethod
    def upper_state(cls, value: str) -> str:
        return value.upper()

    @field_validator("postal_code")
    @classmethod
    def zip5(cls, value: str) -> str:
        digits = value.strip()
        if len(digits) < 5 or not digits[:5].isdigit():
            raise ValueError("postal_code must be a 5-digit US ZIP")
        return digits[:5]


class Construction(BaseModel):
    facility_type: FacilityType = "single-family detached"
    conditioned_floor_area_ft2: float = Field(ge=100, le=20000)
    stories: float = Field(ge=1, le=4)
    stories_above_grade: float = Field(ge=1, le=4)
    ceiling_height_ft: float = Field(ge=7, le=14)
    bedrooms: int = Field(ge=1, le=10)
    bathrooms: int = Field(ge=1, le=8)
    year_built: int = Field(ge=1800, le=2100)


class Enclosure(BaseModel):
    ach50: float = Field(ge=0.1, le=30)
    wall_area_ft2: float = Field(ge=50, le=20000)
    wall_assembly_r: float = Field(ge=1, le=80)
    ceiling_area_ft2: float = Field(ge=50, le=20000)
    ceiling_assembly_r: float = Field(ge=1, le=80)
    roof_area_ft2: float = Field(ge=50, le=20000)
    foundation_type: FoundationType = "conditioned_basement"
    window_u: float = Field(ge=0.1, le=1.2)
    window_shgc: float = Field(ge=0.1, le=0.9)
    window_area_by_azimuth: dict[str, float]
    door_area_ft2: float = Field(ge=0, le=200)
    door_r: float = Field(ge=1, le=20)

    @field_validator("window_area_by_azimuth")
    @classmethod
    def window_keys(cls, value: dict[str, float]) -> dict[str, float]:
        if not value:
            raise ValueError("window_area_by_azimuth is required")
        cleaned: dict[str, float] = {}
        for key, area in value.items():
            if area < 0:
                raise ValueError("window areas must be >= 0")
            cleaned[str(key)] = float(area)
        return cleaned

    @model_validator(mode="after")
    def windows_fit_walls(self) -> Enclosure:
        total = sum(self.window_area_by_azimuth.values())
        if total > self.wall_area_ft2 * 0.95:
            raise ValueError("total window area exceeds 95% of wall area")
        return self


class Systems(BaseModel):
    heating_type: HeatingType = "furnace"
    heating_fuel: HeatingFuel = "natural gas"
    heating_efficiency_afue: float = Field(ge=0.60, le=0.99)
    cooling_type: CoolingType = "central air conditioner"
    cooling_efficiency_seer2: float = Field(ge=8, le=40)
    dhw_type: DhwType = "storage water heater"
    dhw_fuel: DhwFuel = "electricity"
    dhw_uef: float = Field(ge=0.45, le=4.0)
    heating_setpoint_f: float = Field(default=68, ge=50, le=80)
    cooling_setpoint_f: float = Field(default=78, ge=65, le=90)

    @model_validator(mode="after")
    def setpoints(self) -> Systems:
        if self.heating_setpoint_f >= self.cooling_setpoint_f:
            raise ValueError("heating setpoint must be below cooling setpoint")
        return self


class CanonicalBuilding(BaseModel):
    schema_name: Literal["hems.building/v1"] = Field(default=SCHEMA_ID, alias="schema")
    model_config = {"populate_by_name": True}
    site: Site
    construction: Construction
    enclosure: Enclosure
    systems: Systems
    data_source: dict[str, DataSource] = Field(default_factory=dict)

    @property
    def conditioned_volume(self) -> float:
        return self.construction.conditioned_floor_area_ft2 * self.construction.ceiling_height_ft


class FieldError(BaseModel):
    code: str
    field: str
    message: str


def default_payload() -> dict[str, Any]:
    """Defaults shaped like OS-HPXML v1.12.0 workflow/sample_files/base.xml."""
    return CanonicalBuilding(
        site=Site(state_code="CO", postal_code="80202"),
        construction=Construction(
            conditioned_floor_area_ft2=2700,
            stories=2,
            stories_above_grade=1,
            ceiling_height_ft=8,
            bedrooms=3,
            bathrooms=2,
            year_built=2006,
        ),
        enclosure=Enclosure(
            ach50=3.0,
            wall_area_ft2=1200,
            wall_assembly_r=22.7,
            ceiling_area_ft2=1350,
            ceiling_assembly_r=39.6,
            roof_area_ft2=1509.3,
            foundation_type="conditioned_basement",
            window_u=0.35,
            window_shgc=0.44,
            window_area_by_azimuth={"0": 108, "90": 72, "180": 108, "270": 72},
            door_area_ft2=40,
            door_r=4.4,
        ),
        systems=Systems(
            heating_efficiency_afue=0.92,
            cooling_efficiency_seer2=13.4,
            dhw_uef=0.94,
        ),
        data_source={
            "ach50": "user",
            "heating_efficiency_afue": "user",
            "cooling_efficiency_seer2": "user",
            "appliances": "default",
            "lighting": "default",
        },
        ).model_dump(by_alias=True)


def validate_payload(data: dict[str, Any]) -> tuple[CanonicalBuilding | None, list[dict[str, str]]]:
    try:
        model = CanonicalBuilding.model_validate(data)
        return model, []
    except Exception as exc:
        errors: list[dict[str, str]] = []
        if hasattr(exc, "errors"):
            for item in exc.errors():
                loc = ".".join(str(part) for part in item.get("loc", ()))
                errors.append(
                    {
                        "code": item.get("type", "invalid"),
                        "field": loc or "payload",
                        "message": item.get("msg", str(exc)),
                    }
                )
        else:
            errors.append({"code": "invalid", "field": "payload", "message": str(exc)})
        return None, errors


def apply_attic_insulation(payload: dict[str, Any], ceiling_assembly_r: float) -> dict[str, Any]:
    cloned = copy.deepcopy(payload)
    enclosure = cloned.setdefault("enclosure", {})
    enclosure["ceiling_assembly_r"] = ceiling_assembly_r
    sources = cloned.setdefault("data_source", {})
    sources["ceiling_assembly_r"] = "user"
    return cloned
