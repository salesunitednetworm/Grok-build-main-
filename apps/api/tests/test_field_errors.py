from app.domain.field_errors import map_engine_error
from app.domain.software_defaults import parse_run_log_warnings, parse_software_defaults


def test_maps_schematron_text_onto_form_fields():
    assert map_engine_error("Expected AirLeakage for the building")["field"] == "enclosure.ach50"
    assert map_engine_error("DuctLeakage CFM25 is required")["field"] == "systems.duct_leakage_supply_cfm25"
    assert map_engine_error("HSPF2 value is below minimum")["field"] == "systems.heating_efficiency_hspf2"
    assert map_engine_error("ZipCode missing")["field"] == "site.postal_code"


def test_parse_software_defaults_and_warnings():
    xml = """<HPXML xmlns="http://hpxmlonline.com/2025/12">
      <Building>
        <HeatingCapacity dataSource="software">36000.0</HeatingCapacity>
        <extension dataSource="software"><EPWFilePath>USA_FL_Miami.Intl.AP.722020_TMY3.epw</EPWFilePath></extension>
      </Building>
    </HPXML>"""
    defaults = parse_software_defaults(xml)
    assert any(item["element"] == "HeatingCapacity" and item["value"] == "36000.0" for item in defaults)
    assert all(item["data_source"] == "software" for item in defaults)
    warnings = parse_run_log_warnings("Info: ok\nWarning: something defaulted\nERROR boom\n")
    assert warnings == ["Warning: something defaulted"]
