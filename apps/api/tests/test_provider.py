from pathlib import Path

from app.domain.building import CanonicalBuilding, default_payload, validate_payload
from app.providers.openstudio_hpxml import OpenStudioHpxmlProvider


def test_provider_unavailable_without_openstudio(tmp_path: Path):
    provider = OpenStudioHpxmlProvider()
    availability = provider.is_available()
    assert availability.available is False
    assert availability.reason is not None
    assert "kWh" in availability.reason

    model, _ = validate_payload(default_payload())
    assert isinstance(model, CanonicalBuilding)
    generated = provider.generate_input(model)
    run = provider.run(generated, tmp_path)
    assert run.status == "unavailable"
    assert run.energy is None
    assert "hpxml_input" in run.artifacts
    assert run.artifacts["hpxml_input"].read_text().startswith("<?xml")


def test_validate_input_accepts_generated_file():
    provider = OpenStudioHpxmlProvider()
    model, _ = validate_payload(default_payload())
    assert model is not None
    generated = provider.generate_input(model)
    result = provider.validate_input(generated)
    assert result.ok is True
