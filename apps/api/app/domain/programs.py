"""NC/GA HOMES/HEAR rule packs and evaluations.

Evaluations never mutate building models, never invent kWh or savings %,
never claim portal submission / reservation / approval / payment, and never
claim this product is DOE-approved. Rule packs are versioned; stored
evaluations keep the pack they used.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field

PACK_DIR = Path(__file__).resolve().parent.parent / "data" / "programs"

COMPLIANCE_CLAIM = "not_doe_approved_not_submitted"
PORTAL_STATUS = "not_submitted"
RESERVATION_STATUS = "not_reserved"
PAYMENT_STATUS = "not_paid"
SAVINGS_METHOD = "preliminary_site_energy_from_stored_energyplus_totals"

AmiBand = Literal["below_80", "80_to_150", "above_150"]
CheckStatus = Literal["pass", "fail", "incomplete", "not_evaluable", "unverified", "not_submittable"]
OverallStatus = Literal["ineligible", "incomplete", "screen_passed_not_submittable"]


class PackSource(BaseModel):
    title: str
    url: str
    retrieved: str
    status: str
    note: str | None = None


class Check(BaseModel):
    code: str
    status: CheckStatus
    field: str
    message: str
    source_url: str | None = None


class SavingsSnapshot(BaseModel):
    """Stored EnergyPlus totals only. Missing values stay None — never invented."""

    baseline_job_id: str | None = None
    upgrade_job_id: str | None = None
    baseline_total_mbtu: float | None = None
    upgrade_total_mbtu: float | None = None
    baseline_electricity_kwh: float | None = None
    upgrade_electricity_kwh: float | None = None
    both_jobs_succeeded: bool = False


class Application(BaseModel):
    pack_id: str
    household_size: int | None = None
    ami_band: AmiBand | None = None
    ami_band_source: Literal["user_declared"] = "user_declared"
    categorical_programs: list[str] = Field(default_factory=list)
    dwelling_type: Literal["single-family", "multifamily"] = "single-family"
    occupancy: Literal["owner", "renter"] = "owner"
    landlord_authorization: bool = False
    primary_residence: bool | None = None
    georgia_resident: bool | None = None
    existing_home: bool = True
    new_construction: bool = False
    measures: list[str] = Field(default_factory=list)
    replacing_fuel: dict[str, str] = Field(default_factory=dict)
    first_time_appliance: dict[str, bool] = Field(default_factory=dict)
    project_cost_usd: float | None = None
    prior_hear_usd: float = 0
    paired_homes_screen: Literal["none", "incomplete", "ineligible", "screen_passed_not_submittable"] = "none"
    docs_present: dict[str, bool] = Field(default_factory=dict)
    blower_door_pre: bool = False
    blower_door_post: bool = False
    bills_twelve_months_all_fuels: bool = False
    energy_star_when_spec: bool | None = None
    manual_j_uploaded: bool = False
    existing_equipment_photo: bool = False
    also_applying_homes: bool = False
    also_applying_hear: bool = False
    same_measure_on_both_programs: bool = False


class Evaluation(BaseModel):
    pack_id: str
    pack_version: str
    state_code: str
    program: str
    public_name: str
    overall_status: OverallStatus
    compliance_claim: str = COMPLIANCE_CLAIM
    portal_status: str = PORTAL_STATUS
    reservation_status: str = RESERVATION_STATUS
    payment_status: str = PAYMENT_STATUS
    this_product_doe_approved: bool = False
    named_modeling_software: str | None = None
    savings_percent: float | None = None
    savings_method: str | None = None
    savings_band: str | None = None
    rebate_cap_usd: int | None = None
    cost_share_percent: int | None = None
    product_caps_usd: dict[str, int] = Field(default_factory=dict)
    checks: list[Check]
    sources: list[PackSource]
    unverified: list[str]
    reservation_workflow: dict[str, Any]
    notes: str
    current_pack_id: str | None = None
    current_pack_version: str | None = None
    rule_pack_changed: bool = False


def _source_url(pack: dict[str, Any]) -> str | None:
    sources = pack.get("sources") or []
    if sources:
        return sources[0].get("url")
    return None


@lru_cache(maxsize=1)
def load_packs() -> dict[str, dict[str, Any]]:
    packs: dict[str, dict[str, Any]] = {}
    if not PACK_DIR.is_dir():
        return packs
    for path in sorted(PACK_DIR.glob("*.json")):
        with path.open(encoding="utf-8") as handle:
            data = json.load(handle)
        packs[data["pack_id"]] = data
    return packs


def reload_packs() -> dict[str, dict[str, Any]]:
    load_packs.cache_clear()
    return load_packs()


def get_pack(pack_id: str) -> dict[str, Any]:
    pack = load_packs().get(pack_id)
    if pack is None:
        raise KeyError(f"unknown rule pack {pack_id}")
    return pack


def current_pack_for(state_code: str, program: str) -> dict[str, Any] | None:
    matches = [
        pack
        for pack in load_packs().values()
        if pack["state_code"] == state_code.upper() and pack["program"] == program
    ]
    if not matches:
        return None
    matches.sort(key=lambda item: (item.get("effective_from") or "", item.get("pack_version") or ""), reverse=True)
    return matches[0]


def list_pack_summaries() -> list[dict[str, Any]]:
    rows = []
    for pack in load_packs().values():
        rows.append(
            {
                "pack_id": pack["pack_id"],
                "pack_version": pack["pack_version"],
                "state_code": pack["state_code"],
                "program": pack["program"],
                "public_name": pack["public_name"],
                "effective_from": pack.get("effective_from"),
                "effective_to": pack.get("effective_to"),
                "this_product_doe_approved": False,
                "named_modeling_software": pack.get("named_modeling_software"),
                "sources": pack.get("sources") or [],
                "unverified": pack.get("unverified") or [],
            }
        )
    rows.sort(key=lambda item: (item["state_code"], item["program"]))
    return rows


def site_energy_savings_percent(snapshot: SavingsSnapshot) -> tuple[float | None, Check]:
    """Percent from stored EnergyPlus totals. None if either side is missing."""
    if not snapshot.both_jobs_succeeded:
        return None, Check(
            code="savings_energyplus_pair",
            status="not_evaluable",
            field="energy_results",
            message=(
                "No succeeded EnergyPlus pair is stored. HOMES modeled thresholds "
                "are not evaluated and no percentage is invented."
            ),
        )
    baseline = snapshot.baseline_total_mbtu
    upgrade = snapshot.upgrade_total_mbtu
    if baseline is None or upgrade is None:
        return None, Check(
            code="savings_energyplus_pair",
            status="not_evaluable",
            field="energy_results.total_mbtu",
            message="Stored jobs succeeded but total_mbtu is missing on one side. No percentage is invented.",
        )
    if baseline <= 0:
        return None, Check(
            code="savings_energyplus_pair",
            status="not_evaluable",
            field="energy_results.total_mbtu",
            message="Baseline total_mbtu is not positive; a savings percent cannot be formed.",
        )
    percent = (baseline - upgrade) / baseline * 100.0
    return percent, Check(
        code="savings_energyplus_pair",
        status="pass",
        field="energy_results.total_mbtu",
        message=(
            f"Preliminary site-energy change from stored EnergyPlus totals: {percent:.2f}%. "
            "This is not BPI-2400 equivalent-energy savings and cannot qualify a HOMES/HER rebate."
        ),
    )


def _income_check(app: Application, pack: dict[str, Any]) -> Check:
    income = pack.get("income") or {}
    if app.ami_band is None:
        return Check(
            code="income_band",
            status="incomplete",
            field="ami_band",
            message="AMI band is required and must be user-declared. HUD/PNNL Address API lookup is not implemented.",
            source_url=_source_url(pack),
        )
    if app.ami_band in (income.get("ineligible_bands") or []):
        return Check(
            code="income_band",
            status="fail",
            field="ami_band",
            message=f"AMI band {app.ami_band} is ineligible under {pack['pack_id']}. {income.get('note') or ''}".strip(),
            source_url=_source_url(pack),
        )
    if app.ami_band not in (income.get("eligible_bands") or []):
        return Check(
            code="income_band",
            status="fail",
            field="ami_band",
            message=f"AMI band {app.ami_band} is not in the documented eligible list for {pack['pack_id']}.",
            source_url=_source_url(pack),
        )
    return Check(
        code="income_band",
        status="pass",
        field="ami_band",
        message=f"User-declared AMI band {app.ami_band} is in the documented eligible list. Not a verified HUD determination.",
        source_url=_source_url(pack),
    )


def _property_check(app: Application, pack: dict[str, Any]) -> list[Check]:
    checks: list[Check] = []
    prop = pack.get("property") or {}
    if prop.get("existing_homes_only") and not app.existing_home:
        checks.append(
            Check(
                code="existing_home",
                status="fail",
                field="existing_home",
                message=f"{pack['public_name']} is documented for existing homes, not new construction.",
                source_url=_source_url(pack),
            )
        )
    elif prop.get("existing_homes_only"):
        checks.append(
            Check(
                code="existing_home",
                status="pass",
                field="existing_home",
                message="Existing-home flag matches the documented program scope.",
                source_url=_source_url(pack),
            )
        )
    if app.new_construction and pack.get("program") == "hear":
        allowed_appliances = prop.get("new_construction_appliances")
        panel_ok = prop.get("new_construction_panel_wiring")
        if allowed_appliances is False:
            checks.append(
                Check(
                    code="new_construction",
                    status="fail",
                    field="new_construction",
                    message="This HEAR pack does not currently allow new construction.",
                    source_url=_source_url(pack),
                )
            )
        elif any(item in {"panel", "wiring"} for item in app.measures) and panel_ok is False:
            checks.append(
                Check(
                    code="new_construction_panel_wiring",
                    status="fail",
                    field="measures",
                    message="Panel and wiring are not eligible in new construction under documented HEAR product rules.",
                    source_url=_source_url(pack),
                )
            )
    dwelling_ok = app.dwelling_type in (prop.get("dwelling_types") or [app.dwelling_type])
    if not dwelling_ok or (app.dwelling_type == "multifamily" and prop.get("multifamily") == "will_not_reopen"):
        checks.append(
            Check(
                code="dwelling_type",
                status="fail",
                field="dwelling_type",
                message=f"{app.dwelling_type} is not in the current documented scope for {pack['pack_id']}.",
                source_url=_source_url(pack),
            )
        )
    else:
        checks.append(
            Check(
                code="dwelling_type",
                status="pass",
                field="dwelling_type",
                message=f"Dwelling type {app.dwelling_type} is in the documented scope.",
                source_url=_source_url(pack),
            )
        )
    if app.occupancy == "renter" and not app.landlord_authorization:
        checks.append(
            Check(
                code="landlord_authorization",
                status="fail",
                field="landlord_authorization",
                message="Renters need owner/landlord authorization in the cited state rules.",
                source_url=_source_url(pack),
            )
        )
    if pack["state_code"] == "GA" and app.georgia_resident is False:
        checks.append(
            Check(
                code="georgia_resident",
                status="fail",
                field="georgia_resident",
                message="Georgia eligibility pages require Georgia residency / primary-home rules.",
                source_url=_source_url(pack),
            )
        )
    return checks


def _measure_checks(app: Application, pack: dict[str, Any]) -> list[Check]:
    checks: list[Check] = []
    rules = pack.get("measures") or {}
    allowed = set(rules.get("allowed") or [])
    if not app.measures:
        checks.append(
            Check(
                code="measures",
                status="incomplete",
                field="measures",
                message="At least one measure is required to evaluate eligibility.",
                source_url=_source_url(pack),
            )
        )
        return checks
    unknown = [item for item in app.measures if allowed and item not in allowed]
    if unknown:
        checks.append(
            Check(
                code="measures",
                status="fail",
                field="measures",
                message=f"Measures not in the current pack allow-list: {', '.join(unknown)}.",
                source_url=_source_url(pack),
            )
        )
    else:
        checks.append(
            Check(
                code="measures",
                status="pass",
                field="measures",
                message="Requested measures are on the documented allow-list for this pack version.",
                source_url=_source_url(pack),
            )
        )
    if rules.get("panel_wiring_only_to_enable_appliance"):
        appliances = {"heat_pump_space", "heat_pump_water_heater", "heat_pump_dryer", "electric_stove"}
        has_panel = any(item in {"panel", "wiring"} for item in app.measures)
        has_appliance = any(item in appliances for item in app.measures)
        if has_panel and not has_appliance:
            checks.append(
                Check(
                    code="panel_wiring_enables_appliance",
                    status="fail",
                    field="measures",
                    message="Documented NC HEAR rule: panel and wiring only when required to enable an eligible appliance.",
                    source_url=_source_url(pack),
                )
            )
    if rules.get("must_pair_with_homes"):
        if app.paired_homes_screen == "screen_passed_not_submittable":
            checks.append(
                Check(
                    code="her_pairing",
                    status="pass",
                    field="paired_homes_screen",
                    message=(
                        "A paired HER/HOMES screen is present. This is not a Neighborly reservation "
                        "and does not mean HER was approved."
                    ),
                    source_url=_source_url(pack),
                )
            )
        elif app.paired_homes_screen == "ineligible":
            checks.append(
                Check(
                    code="her_pairing",
                    status="fail",
                    field="paired_homes_screen",
                    message="Georgia HEAR currently requires an eligible HER project. The paired HOMES screen is ineligible.",
                    source_url=_source_url(pack),
                )
            )
        else:
            checks.append(
                Check(
                    code="her_pairing",
                    status="fail" if app.paired_homes_screen == "none" else "incomplete",
                    field="paired_homes_screen",
                    message="Georgia HEAR (current pack) is wiring/panel only in conjunction with an eligible HER project.",
                    source_url=_source_url(pack),
                )
            )
    return checks


def _fuel_checks(app: Application, pack: dict[str, Any]) -> list[Check]:
    checks: list[Check] = []
    rules = pack.get("fuel_restrictions") or {}
    if pack.get("program") == "homes" and rules.get("all_fuels_bills_required"):
        checks.append(
            Check(
                code="all_fuel_bills",
                status="pass" if app.bills_twelve_months_all_fuels else "incomplete",
                field="bills_twelve_months_all_fuels",
                message=(
                    "NC HOMES requires 12 months of utility bills for all fuels."
                    if app.bills_twelve_months_all_fuels
                    else "12 months of all-fuel bills are not marked present. HOMES modeled path is incomplete."
                ),
                source_url=_source_url(pack),
            )
        )
    if pack.get("program") != "hear":
        return checks
    allowed_timing = set(rules.get("appliance_purchase_must_be") or [])
    appliance_types = {"heat_pump_space", "heat_pump_water_heater", "heat_pump_dryer", "electric_stove"}
    for measure in app.measures:
        if measure not in appliance_types or not allowed_timing:
            continue
        replacing = (app.replacing_fuel.get(measure) or "").lower()
        first_time = app.first_time_appliance.get(measure, False)
        if app.new_construction and "new_construction" in allowed_timing:
            checks.append(
                Check(
                    code=f"qep_timing_{measure}",
                    status="pass",
                    field="new_construction",
                    message=f"{measure}: new-construction QEP timing is documented as allowed for listed appliances.",
                    source_url=_source_url(pack),
                )
            )
            continue
        if first_time and "first_time" in allowed_timing:
            checks.append(
                Check(
                    code=f"qep_timing_{measure}",
                    status="pass",
                    field="first_time_appliance",
                    message=f"{measure}: marked first-time purchase.",
                    source_url=_source_url(pack),
                )
            )
            continue
        if replacing in {"natural gas", "fuel oil", "propane", "nonelectric", "gas"} and "replace_nonelectric" in allowed_timing:
            checks.append(
                Check(
                    code=f"qep_timing_{measure}",
                    status="pass",
                    field="replacing_fuel",
                    message=f"{measure}: replacing a nonelectric appliance as documented for QEP timing.",
                    source_url=_source_url(pack),
                )
            )
            continue
        if replacing in {"electricity", "heat pump", "electric"}:
            checks.append(
                Check(
                    code=f"qep_timing_{measure}",
                    status="fail",
                    field="replacing_fuel",
                    message=f"{measure}: replacing an existing electric/heat-pump appliance is not a documented eligible QEP.",
                    source_url=_source_url(pack),
                )
            )
        else:
            checks.append(
                Check(
                    code=f"qep_timing_{measure}",
                    status="incomplete",
                    field="replacing_fuel",
                    message=f"{measure}: QEP timing requires new construction, replacement of a nonelectric appliance, or first-time purchase.",
                    source_url=_source_url(pack),
                )
            )
    return checks


def _envelope_checks(app: Application, pack: dict[str, Any]) -> list[Check]:
    checks: list[Check] = []
    env = pack.get("envelope_prerequisites") or {}
    envelope_measures = {"attic_insulation", "air_sealing", "insulation", "ventilation", "envelope"}
    has_envelope = any(item in envelope_measures for item in app.measures)
    if env.get("blower_door_pre_and_post_if_envelope") and has_envelope:
        ok = app.blower_door_pre and app.blower_door_post
        checks.append(
            Check(
                code="blower_door",
                status="pass" if ok else "incomplete",
                field="blower_door_pre",
                message=(
                    "Envelope project has pre- and post-blower door flags. No ACH50 pass/fail is invented."
                    if ok
                    else "Georgia HER envelope projects require pre- and post-blower door (Consumer Protection Plan). Numeric ACH50 is not evaluated here."
                ),
                source_url=_source_url(pack),
            )
        )
    if pack.get("state_code") == "NC" and pack.get("program") == "homes" and has_envelope:
        photos = app.docs_present.get("weatherization_photos", False)
        pre_ins = app.docs_present.get("pre_existing_insulation_levels", False)
        checks.append(
            Check(
                code="nc_envelope_docs",
                status="pass" if photos and pre_ins else "incomplete",
                field="docs_present",
                message=(
                    "NC HOMES weatherization photos and pre-existing insulation levels are marked present."
                    if photos and pre_ins
                    else "NC HOMES lists weatherization photos and pre-existing insulation levels as required artifacts."
                ),
                source_url=_source_url(pack),
            )
        )
    return checks


def _doc_checks(app: Application, pack: dict[str, Any]) -> list[Check]:
    checks: list[Check] = []
    required = pack.get("required_docs") or []
    missing = [item for item in required if not app.docs_present.get(item)]
    # Some docs are collected as first-class flags rather than the docs map.
    aliases = {
        "twelve_months_all_fuel_bills": app.bills_twelve_months_all_fuels,
        "acca_manual_j_if_heat_pump_space": app.manual_j_uploaded or "heat_pump_space" not in app.measures,
        "limited_assessment_if_heat_pump_space": app.docs_present.get("limited_assessment_if_heat_pump_space")
        or "heat_pump_space" not in app.measures,
        "photo_of_existing_equipment_if_appliance_qep": app.existing_equipment_photo
        or not any(
            item in {"heat_pump_space", "heat_pump_water_heater", "heat_pump_dryer", "electric_stove"}
            for item in app.measures
        ),
        "landlord_authorization_if_renter": app.occupancy != "renter" or app.landlord_authorization,
        "eligible_her_project": app.paired_homes_screen == "screen_passed_not_submittable",
        "snugg_pro_model": False,
        "contractor_energy_audit_snuggpro": False,
        "neighborly_application": False,
    }
    still_missing = []
    for item in missing:
        if aliases.get(item) is True:
            continue
        if aliases.get(item) is False and item in aliases:
            still_missing.append(item)
            continue
        still_missing.append(item)
    if still_missing:
        named_model_docs = {
            "snugg_pro_model",
            "contractor_energy_audit_snuggpro",
            "neighborly_application",
        }
        blocking = [item for item in still_missing if item not in named_model_docs]
        unsubmittable = [item for item in still_missing if item in named_model_docs]
        if blocking:
            checks.append(
                Check(
                    code="required_docs",
                    status="incomplete",
                    field="docs_present",
                    message="Required documents not marked present: " + ", ".join(blocking) + ".",
                    source_url=_source_url(pack),
                )
            )
        if unsubmittable:
            checks.append(
                Check(
                    code="named_vendor_artifacts",
                    status="not_submittable",
                    field="docs_present",
                    message=(
                        "This product cannot supply "
                        + ", ".join(unsubmittable)
                        + ". The state pack names Snugg Pro / Neighborly; wrapping OpenStudio-HPXML is not a substitute."
                    ),
                    source_url=_source_url(pack),
                )
            )
    else:
        checks.append(
            Check(
                code="required_docs",
                status="pass",
                field="docs_present",
                message="Application marks the documented checklist present. This is not a portal filing.",
                source_url=_source_url(pack),
            )
        )
    if pack.get("program") == "hear" and "heat_pump_space" in app.measures:
        hp_rules = pack.get("heat_pump_space_rules") or {}
        if hp_rules.get("acca_manual_j_upload"):
            checks.append(
                Check(
                    code="manual_j",
                    status="pass" if app.manual_j_uploaded else "incomplete",
                    field="manual_j_uploaded",
                    message=(
                        "NC HEAR heat-pump reservation requires an ACCA Manual J upload. "
                        "This product's design loads are preliminary and are not that file."
                    ),
                    source_url=_source_url(pack),
                )
            )
    star = pack.get("energy_star") or {}
    if star.get("required_in_pack") and app.energy_star_when_spec is False:
        status: CheckStatus = "unverified" if star.get("notice_26_1_nc_adoption") == "unverified" else "fail"
        checks.append(
            Check(
                code="energy_star",
                status=status,
                field="energy_star_when_spec",
                message=(
                    "NC v2.0 requires ENERGY STAR when a specification exists. Notice 26-1 may make that optional "
                    "for HOMES; NC adoption of 26-1 is unverified. Not treated as a silent pass."
                ),
                source_url=_source_url(pack),
            )
        )
    return checks


def _stacking_checks(app: Application, pack: dict[str, Any]) -> list[Check]:
    stacking = pack.get("stacking") or {}
    if app.also_applying_homes and app.also_applying_hear and app.same_measure_on_both_programs:
        if stacking.get("same_measure_homes_and_hear") is False:
            return [
                Check(
                    code="same_measure_stacking",
                    status="fail",
                    field="same_measure_on_both_programs",
                    message="Documented stacking rules forbid 50121 and 50122 rebates for the same measure (wiring/panel braid is a documented exception, not a same-measure envelope rebate).",
                    source_url=_source_url(pack),
                )
            ]
    return [
        Check(
            code="same_measure_stacking",
            status="pass",
            field="same_measure_on_both_programs",
            message="No same-measure HOMES+HEAR conflict was declared.",
            source_url=_source_url(pack),
        )
    ]


def _savings_band(percent: float | None, pack: dict[str, Any]) -> tuple[str | None, Check]:
    modeled = pack.get("modeled_savings") or {}
    if not modeled.get("required"):
        return None, Check(
            code="modeled_savings",
            status="pass",
            field="savings_percent",
            message="This program does not use a modeled savings percentage.",
            source_url=_source_url(pack),
        )
    minimum = modeled.get("minimum_percent")
    higher = modeled.get("higher_tier_percent")
    if percent is None:
        return None, Check(
            code="modeled_savings",
            status="not_evaluable",
            field="savings_percent",
            message=(
                f"Documented threshold is {minimum}% (higher tier {higher}%). "
                "No stored EnergyPlus pair is available, so the band is not evaluated and no percent is invented."
            ),
            source_url=_source_url(pack),
        )
    if minimum is None:
        return None, Check(
            code="modeled_savings",
            status="unverified",
            field="savings_percent",
            message="No documented minimum percent is in this pack; none is invented.",
            source_url=_source_url(pack),
        )
    if percent < float(minimum):
        return "below_minimum", Check(
            code="modeled_savings",
            status="fail",
            field="savings_percent",
            message=(
                f"Preliminary site-energy change {percent:.2f}% is below the documented {minimum}% modeled threshold. "
                "Still not a BPI-2400 equivalent-energy figure."
            ),
            source_url=_source_url(pack),
        )
    band = "35_or_greater" if higher is not None and percent >= float(higher) else "20_to_34"
    return band, Check(
        code="modeled_savings",
        status="pass",
        field="savings_percent",
        message=(
            f"Preliminary site-energy change {percent:.2f}% meets the documented {band.replace('_', ' ')} screen. "
            "This product is not DOE-approved; the screen cannot qualify a rebate."
        ),
        source_url=_source_url(pack),
    )


def _rebate_row(pack: dict[str, Any], ami_band: str | None, savings_band: str | None, measures: list[str]) -> dict[str, Any] | None:
    rows = pack.get("rebate_limits") or []
    if pack.get("program") == "hear":
        # Lifetime / AMI rows, plus product caps applied separately.
        for row in rows:
            if ami_band and row.get("ami_band") == ami_band and "measure" not in row:
                return row
        # GA HEAR measure-specific rows: pick the first matching AMI+measure.
        matched = [row for row in rows if row.get("ami_band") == ami_band and row.get("measure") in measures]
        if matched:
            return matched[0]
        return None
    for row in rows:
        if row.get("ami_band") == ami_band and row.get("savings_band") == savings_band:
            return row
    return None


def _overall(checks: list[Check]) -> OverallStatus:
    household = [item for item in checks if item.status != "not_submittable"]
    if any(item.status == "fail" for item in household):
        return "ineligible"
    if any(item.status in {"incomplete", "not_evaluable"} for item in household):
        return "incomplete"
    return "screen_passed_not_submittable"


def evaluate(app: Application, snapshot: SavingsSnapshot, pack: dict[str, Any] | None = None) -> Evaluation:
    pack = pack or get_pack(app.pack_id)
    checks: list[Check] = []
    checks.append(_income_check(app, pack))
    checks.extend(_property_check(app, pack))
    checks.extend(_measure_checks(app, pack))
    checks.extend(_fuel_checks(app, pack))
    checks.extend(_envelope_checks(app, pack))
    checks.extend(_doc_checks(app, pack))
    checks.extend(_stacking_checks(app, pack))

    percent: float | None = None
    savings_method = None
    savings_band = None
    modeled = pack.get("modeled_savings") or {}
    if modeled.get("required"):
        percent, pair_check = site_energy_savings_percent(snapshot)
        checks.append(pair_check)
        savings_method = SAVINGS_METHOD
        savings_band, band_check = _savings_band(percent, pack)
        checks.append(band_check)
        checks.append(
            Check(
                code="doe_software_approval",
                status="not_submittable",
                field="this_product_doe_approved",
                message=(
                    "This product is not on the BPI or NASEO HOMES modeled-tool lists and has not completed "
                    "DOE/NREL single-family verification. OpenStudio-HPXML is an engine, not product approval. "
                    "A passing site-energy screen is not a rebate qualification."
                ),
                source_url="https://www.energy.gov/sites/default/files/2024-05/ira-home-rebates-single-family-software-verification_050324.pdf",
            )
        )
    else:
        _, band_check = _savings_band(None, pack)
        checks.append(band_check)

    if pack.get("named_modeling_software") and pack.get("program") == "homes":
        checks.append(
            Check(
                code="named_engine",
                status="not_submittable",
                field="named_modeling_software",
                message=(
                    f"{pack['state_code']} names {pack['named_modeling_software']} for 50121 modeled work "
                    f"({pack.get('named_modeling_software_status')}). This product does not impersonate that engine."
                ),
                source_url=_source_url(pack),
            )
        )

    rebate = _rebate_row(pack, app.ami_band, savings_band, app.measures)
    product_caps = dict(pack.get("product_caps_usd") or {})
    if (
        pack.get("program") == "hear"
        and pack.get("federal_combined_kitchen_dryer_nc_enforcement") == "unverified"
        and "heat_pump_dryer" in app.measures
        and "electric_stove" in app.measures
    ):
        checks.append(
            Check(
                code="federal_kitchen_dryer_cap",
                status="unverified",
                field="product_caps_usd",
                message=(
                    "Federal v2.1 says kitchen appliance + dryer together may not exceed $840. "
                    "NC Table 4 lists each at $840. Whether NC enforces the combined cap is unverified; not applied silently."
                ),
                source_url=_source_url(pack),
            )
        )

    checks.append(
        Check(
            code="portal_submission",
            status="pass",
            field="portal_status",
            message="This software does not submit to energysavernc.org, Neighborly, or PNNL APIs. Status is not_submitted.",
        )
    )

    overall = _overall(checks)
    notes = (
        f"Rule pack {pack['pack_id']} version {pack['pack_version']} pinned on this evaluation. "
        "Not DOE-approved. Not reserved. Not paid. Inputs were not adjusted to force a screen."
    )
    return Evaluation(
        pack_id=pack["pack_id"],
        pack_version=pack["pack_version"],
        state_code=pack["state_code"],
        program=pack["program"],
        public_name=pack["public_name"],
        overall_status=overall,
        named_modeling_software=pack.get("named_modeling_software"),
        savings_percent=percent,
        savings_method=savings_method,
        savings_band=savings_band,
        rebate_cap_usd=None if rebate is None else rebate.get("max_usd") or rebate.get("lifetime_max_usd"),
        cost_share_percent=None if rebate is None else rebate.get("cost_share_percent"),
        product_caps_usd=product_caps,
        checks=checks,
        sources=[PackSource.model_validate(item) for item in pack.get("sources") or []],
        unverified=list(pack.get("unverified") or []),
        reservation_workflow=dict(pack.get("reservation_workflow") or {}),
        notes=notes,
        current_pack_id=pack["pack_id"],
        current_pack_version=pack["pack_version"],
        rule_pack_changed=False,
    )


def flag_pack_change(evaluation: Evaluation, current: dict[str, Any] | None = None) -> Evaluation:
    current = current or current_pack_for(evaluation.state_code, evaluation.program)
    if current is None:
        return evaluation
    changed = current["pack_id"] != evaluation.pack_id or current["pack_version"] != evaluation.pack_version
    evaluation.current_pack_id = current["pack_id"]
    evaluation.current_pack_version = current["pack_version"]
    evaluation.rule_pack_changed = changed
    return evaluation
