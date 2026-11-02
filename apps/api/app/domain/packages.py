"""Upgrade packages that change only documented ECM fields.

Each package is a combination of attic insulation, air sealing, and/or HPWH.
Energy for a package comes only from a real model re-run — never from added
percentages.
"""

from __future__ import annotations

import copy
import itertools
from typing import Any, Literal

from pydantic import BaseModel, Field

MeasureId = Literal["attic", "air_sealing", "hpwh"]

# Package assumptions — measure *targets*, not savings claims.
ATTIC_CEILING_R = 49.0
AIR_SEALING_ACH50 = 1.5
HPWH_TYPE = "heat pump water heater"
HPWH_FUEL = "electricity"
HPWH_UEF = 3.5

MEASURE_FIELDS: dict[str, list[str]] = {
    "attic": ["enclosure.ceiling_assembly_r", "data_source.ceiling_assembly_r"],
    "air_sealing": ["enclosure.ach50", "data_source.ach50"],
    "hpwh": [
        "systems.dhw_type",
        "systems.dhw_fuel",
        "systems.dhw_uef",
        "data_source.dhw_type",
        "data_source.dhw_fuel",
        "data_source.dhw_uef",
    ],
}


class PackageSpec(BaseModel):
    name: str
    measures: list[MeasureId]
    measure_payload: dict[str, Any]
    notes: str


def _set_path(payload: dict[str, Any], path: str, value: Any) -> None:
    parts = path.split(".")
    cursor: Any = payload
    for part in parts[:-1]:
        cursor = cursor.setdefault(part, {})
    cursor[parts[-1]] = value


def apply_measure(payload: dict[str, Any], measure: MeasureId) -> dict[str, Any]:
    cloned = copy.deepcopy(payload)
    sources = cloned.setdefault("data_source", {})
    if measure == "attic":
        cloned.setdefault("enclosure", {})["ceiling_assembly_r"] = ATTIC_CEILING_R
        sources["ceiling_assembly_r"] = "user"
    elif measure == "air_sealing":
        cloned.setdefault("enclosure", {})["ach50"] = AIR_SEALING_ACH50
        sources["ach50"] = "user"
    elif measure == "hpwh":
        systems = cloned.setdefault("systems", {})
        systems["dhw_type"] = HPWH_TYPE
        systems["dhw_fuel"] = HPWH_FUEL
        systems["dhw_uef"] = HPWH_UEF
        sources["dhw_type"] = "user"
        sources["dhw_fuel"] = "user"
        sources["dhw_uef"] = "user"
    return cloned


def apply_measures(payload: dict[str, Any], measures: list[MeasureId]) -> dict[str, Any]:
    next_payload = copy.deepcopy(payload)
    for measure in measures:
        next_payload = apply_measure(next_payload, measure)
    return next_payload


def measure_payload_for(measures: list[MeasureId]) -> dict[str, Any]:
    body: dict[str, Any] = {}
    if "attic" in measures:
        body["ceiling_assembly_r"] = ATTIC_CEILING_R
    if "air_sealing" in measures:
        body["ach50"] = AIR_SEALING_ACH50
    if "hpwh" in measures:
        body["dhw_type"] = HPWH_TYPE
        body["dhw_fuel"] = HPWH_FUEL
        body["dhw_uef"] = HPWH_UEF
    return body


def enumerate_packages() -> list[PackageSpec]:
    ids: tuple[MeasureId, ...] = ("attic", "air_sealing", "hpwh")
    packages: list[PackageSpec] = []
    for length in range(1, len(ids) + 1):
        for combo in itertools.combinations(ids, length):
            measures = list(combo)
            packages.append(
                PackageSpec(
                    name="+".join(measures),
                    measures=measures,
                    measure_payload=measure_payload_for(measures),
                    notes=(
                        "Combined package. EnergyPlus must be re-run on the cloned model. "
                        "No percentage is added to the baseline. Not BPI-2400 savings."
                    ),
                )
            )
    return packages


def ecm_paths_for(measures: list[str]) -> set[str]:
    paths: set[str] = set()
    for measure in measures:
        paths.update(MEASURE_FIELDS.get(measure, []))
    return paths


def flatten(payload: dict[str, Any], prefix: str = "") -> dict[str, Any]:
    flat: dict[str, Any] = {}
    for key, value in payload.items():
        path = f"{prefix}.{key}" if prefix else str(key)
        if isinstance(value, dict):
            flat.update(flatten(value, path))
        else:
            flat[path] = value
    return flat


class ConsistencyReport(BaseModel):
    ok: bool
    changed: list[str] = Field(default_factory=list)
    unexpected: list[str] = Field(default_factory=list)
    allowed: list[str] = Field(default_factory=list)
    notes: str


def baseline_post_consistency(
    baseline: dict[str, Any],
    upgraded: dict[str, Any],
    measures: list[str],
) -> ConsistencyReport:
    """Pre/post models must be identical except ECM fields (BPI-2400 / DOE review Q2)."""
    allowed = ecm_paths_for(measures)
    # Attic-only scenarios from the original slice use this name.
    if not allowed and measures == ["attic_insulation"]:
        allowed = ecm_paths_for(["attic"])
    left = flatten(baseline)
    right = flatten(upgraded)
    keys = set(left) | set(right)
    changed: list[str] = []
    unexpected: list[str] = []
    for key in sorted(keys):
        if left.get(key) != right.get(key):
            changed.append(key)
            if key not in allowed:
                unexpected.append(key)
    return ConsistencyReport(
        ok=not unexpected,
        changed=changed,
        unexpected=unexpected,
        allowed=sorted(allowed),
        notes=(
            "Baseline vs post must differ only on ECM fields. "
            "This is a structural check, not a qualified savings prediction."
        ),
    )
