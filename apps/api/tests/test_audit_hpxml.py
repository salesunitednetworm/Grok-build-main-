from app.domain.building import apply_duct_leakage, apply_heat_pump, default_payload, validate_payload
from app.domain.hpxml import generate_hpxml, inspect_hpxml
from app.domain.schema_check import validate_against_xsd, xsd_available


def _xml(payload: dict) -> str:
    model, errors = validate_payload(payload)
    assert model is not None, errors
    xml = generate_hpxml(model)
    assert inspect_hpxml(xml) == []
    return xml


def test_vented_attic_and_crawl_and_rim_joists():
    payload = default_payload()
    payload["enclosure"]["attic_type"] = "vented"
    payload["enclosure"]["foundation_type"] = "vented_crawlspace"
    payload["enclosure"]["rim_joist_area_ft2"] = 140.0
    payload["enclosure"]["rim_joist_assembly_r"] = 15.0
    xml = _xml(payload)
    assert "<Vented>true</Vented>" in xml
    assert "attic - vented" in xml
    assert "<Crawlspace>" in xml
    assert "crawlspace - vented" in xml
    assert "<Area>140.0</Area>" in xml
    assert "RimJoist1Insulation" in xml
    if xsd_available():
        assert validate_against_xsd(xml) == []


def test_heat_pump_emits_hspf2_seer2():
    xml = _xml(apply_heat_pump(default_payload(), hspf2=8.5, seer2=16.0))
    assert "<HeatPump>" in xml
    assert "<HeatPumpType>air-to-air</HeatPumpType>" in xml
    assert "<Units>HSPF2</Units>" in xml
    assert "<Value>8.5</Value>" in xml
    assert "<Units>SEER2</Units>" in xml
    assert "<HeatingSystem>" not in xml
    if xsd_available():
        assert validate_against_xsd(xml) == []


def test_ductless_mini_split_omits_distribution():
    xml = _xml(apply_heat_pump(default_payload(), hspf2=9.0, seer2=19.0, ductless=True))
    assert "<HeatPumpType>mini-split</HeatPumpType>" in xml
    assert "HVACDistribution" not in xml


def test_measured_duct_leakage_cfm25():
    xml = _xml(apply_duct_leakage(default_payload(), 40.0, 15.0))
    assert "<Units>CFM25</Units>" in xml
    assert "<Value>40.0</Value>" in xml
    assert "<Value>15.0</Value>" in xml
    if xsd_available():
        assert validate_against_xsd(xml) == []


def test_slab_and_unconditioned_basement_emit():
    slab = default_payload()
    slab["enclosure"]["foundation_type"] = "slab_on_grade"
    slab_xml = _xml(slab)
    assert "<SlabOnGrade" in slab_xml or "<SlabOnGrade/>" in slab_xml
    assert "RimJoist1" not in slab_xml
    basement = default_payload()
    basement["enclosure"]["foundation_type"] = "unconditioned_basement"
    basement_xml = _xml(basement)
    assert "basement - unconditioned" in basement_xml
    assert "<Conditioned>false</Conditioned>" in basement_xml
