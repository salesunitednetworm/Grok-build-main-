import xml.etree.ElementTree as ET

from app.domain.building import CanonicalBuilding, apply_attic_insulation, default_payload, validate_payload
from app.domain.hpxml import (
    HPXML_NS,
    HPXML_SCHEMA_VERSION,
    SOFTWARE_NAME,
    ceiling_r_from_xml,
    generate_hpxml,
    inspect_hpxml,
)


def _model() -> CanonicalBuilding:
    model, errors = validate_payload(default_payload())
    assert model is not None
    assert errors == []
    return model


def test_hpxml_namespace_and_schema():
    xml = generate_hpxml(_model())
    errors = inspect_hpxml(xml)
    assert errors == []
    root = ET.fromstring(xml)
    assert root.tag == f"{{{HPXML_NS}}}HPXML"
    assert root.attrib["schemaVersion"] == HPXML_SCHEMA_VERSION
    assert SOFTWARE_NAME in xml
    assert "OpenStudio" not in xml.split("SoftwareProgramUsed")[1][:80]


def test_hpxml_contains_energyplus_use_case_sections():
    xml = generate_hpxml(_model())
    for needle in (
        "BuildingSummary",
        "ClimateandRiskZones",
        "AirInfiltration",
        "Walls",
        "Windows",
        "HeatingSystem",
        "CoolingSystem",
        "WaterHeatingSystem",
        "ClothesWasher",
        "LightingGroup",
        "80202",
        "CO",
    ):
        assert needle in xml


def test_upgrade_changes_only_ceiling_r():
    baseline = generate_hpxml(_model())
    upgraded_payload = apply_attic_insulation(default_payload(), 49.0)
    upgraded_model, errors = validate_payload(upgraded_payload)
    assert errors == []
    assert upgraded_model is not None
    upgraded = generate_hpxml(upgraded_model)
    assert ceiling_r_from_xml(baseline) == 39.6
    assert ceiling_r_from_xml(upgraded) == 49.0
    assert baseline.count("39.6") >= 1
    assert "49.0" in upgraded


def test_address_schema_order_state_then_zip():
    xml = generate_hpxml(_model())
    assert xml.index("<StateCode>") < xml.index("<ZipCode>")


def test_inspect_rejects_wrong_namespace():
    errors = inspect_hpxml("<HPXML schemaVersion='5.0'></HPXML>")
    assert any(err["code"] == "namespace" for err in errors)
