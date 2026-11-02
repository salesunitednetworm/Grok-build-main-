from app.domain.building import default_payload, validate_payload
from app.domain.hpxml import generate_hpxml
from app.domain.packages import apply_measures
from app.domain.schema_check import emit_and_schema_errors, official_sample_paths, validate_against_xsd, xsd_available

from .report import write_artifact


def test_generated_hpxml_passes_emit_and_optional_xsd():
    model, errors = validate_payload(default_payload())
    assert model is not None and errors == []
    xml = generate_hpxml(model)
    emit = emit_and_schema_errors(xml)
    assert emit == []
    xsd_errors = validate_against_xsd(xml) if xsd_available() else [{"code": "skipped", "message": "HPXML.xsd not installed"}]
    if xsd_available():
        assert xsd_errors == [], xsd_errors
    hpwh_model, hpwh_errors = validate_payload(apply_measures(default_payload(), ["hpwh"]))
    assert hpwh_model is not None and hpwh_errors == []
    hpwh_xml = generate_hpxml(hpwh_model)
    assert emit_and_schema_errors(hpwh_xml) == []
    if xsd_available():
        assert validate_against_xsd(hpwh_xml) == []
    write_artifact(
        "hpxml-schema",
        {
            "generated_emit_errors": emit,
            "generated_xsd_errors": xsd_errors,
            "xsd_available": xsd_available(),
            "official_samples_present": sorted(official_sample_paths()),
            "hpwh_water_heater_type": "heat pump water heater",
        },
    )
