from app.domain.building import default_payload, validate_payload
from app.domain.hpxml import generate_hpxml
from app.domain.packages import (
    AIR_SEALING_ACH50,
    ATTIC_CEILING_R,
    HPWH_TYPE,
    apply_measures,
    baseline_post_consistency,
    enumerate_packages,
)


def test_seven_combined_packages():
    names = [item.name for item in enumerate_packages()]
    assert names == [
        "attic",
        "air_sealing",
        "hpwh",
        "attic+air_sealing",
        "attic+hpwh",
        "air_sealing+hpwh",
        "attic+air_sealing+hpwh",
    ]


def test_package_changes_only_ecm_fields():
    baseline = default_payload()
    upgraded = apply_measures(baseline, ["attic", "air_sealing", "hpwh"])
    report = baseline_post_consistency(baseline, upgraded, ["attic", "air_sealing", "hpwh"])
    assert report.ok is True
    assert "enclosure.ceiling_assembly_r" in report.changed
    assert "enclosure.ach50" in report.changed
    assert "systems.dhw_type" in report.changed
    assert upgraded["enclosure"]["ceiling_assembly_r"] == ATTIC_CEILING_R
    assert upgraded["enclosure"]["ach50"] == AIR_SEALING_ACH50
    assert upgraded["systems"]["dhw_type"] == HPWH_TYPE
    assert upgraded["systems"]["heating_efficiency_afue"] == baseline["systems"]["heating_efficiency_afue"]


def test_unexpected_field_change_fails_consistency():
    baseline = default_payload()
    upgraded = apply_measures(baseline, ["attic"])
    upgraded["systems"]["heating_efficiency_afue"] = 0.80
    report = baseline_post_consistency(baseline, upgraded, ["attic"])
    assert report.ok is False
    assert any("heating_efficiency_afue" in item for item in report.unexpected)


def test_hpwh_package_emits_heat_pump_water_heater():
    payload = apply_measures(default_payload(), ["hpwh"])
    model, errors = validate_payload(payload)
    assert errors == []
    assert model is not None
    xml = generate_hpxml(model)
    assert "<WaterHeaterType>heat pump water heater</WaterHeaterType>" in xml
    assert "<UniformEnergyFactor>3.50</UniformEnergyFactor>" in xml
