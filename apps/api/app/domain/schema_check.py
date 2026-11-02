"""HPXML schema / emit checks used by the verification harness."""

from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path

from app.domain.field_errors import map_engine_errors
from app.domain.hpxml import inspect_hpxml
from app.config import settings

OFFICIAL_XSD = Path("/opt/OpenStudio-HPXML-1.12.0/HPXMLtoOpenStudio/resources/hpxml_schema/HPXML.xsd")
OFFICIAL_SCH = Path("/opt/OpenStudio-HPXML-1.12.0/HPXMLtoOpenStudio/resources/hpxml_schematron/EPvalidator.sch")
OFFICIAL_BASE = Path("/opt/OpenStudio-HPXML-1.12.0/workflow/sample_files/base.xml")
OFFICIAL_HPWH = Path("/opt/OpenStudio-HPXML-1.12.0/workflow/sample_files/base-dhw-tank-heat-pump.xml")


def xsd_available() -> bool:
    return OFFICIAL_XSD.exists()


def validate_against_xsd(xml_text: str, xsd_path: Path | None = None) -> list[dict[str, str]]:
    """Validate instance XML with the OS-HPXML 1.12.0 HPXML.xsd via xmllint.

    Returns structured errors. Does not invent an ASHRAE 140 verdict.
    """
    schema = xsd_path or OFFICIAL_XSD
    if not schema.exists():
        return [
            {
                "code": "xsd_unavailable",
                "field": "hpxml",
                "message": f"HPXML.xsd not found at {schema}",
            }
        ]
    with tempfile.NamedTemporaryFile("w", suffix=".xml", delete=False) as handle:
        handle.write(xml_text)
        xml_path = Path(handle.name)
    try:
        result = subprocess.run(
            ["xmllint", "--noout", "--schema", str(schema), str(xml_path)],
            capture_output=True,
            text=True,
            check=False,
        )
    finally:
        xml_path.unlink(missing_ok=True)
    if result.returncode == 0:
        return []
    message = (result.stderr or result.stdout or "xmllint failed").strip()
    return map_engine_errors([{"code": "xsd", "field": "hpxml", "message": message}], code="xsd")


def schematron_available() -> bool:
    cli = settings.openstudio_cli
    return bool(cli and Path(cli).exists() and OFFICIAL_SCH.exists())


def validate_against_schematron(xml_text: str) -> list[dict[str, str]]:
    """Run the official EnergyPlus-use-case Schematron via OpenStudio XMLValidator when present."""
    if not schematron_available():
        return []
    with tempfile.NamedTemporaryFile("w", suffix=".xml", delete=False) as handle:
        handle.write(xml_text)
        xml_path = Path(handle.name)
    ruby = (
        "require 'openstudio'; "
        f"v=OpenStudio::XMLValidator.new({str(OFFICIAL_SCH)!r}); "
        f"v.validate({str(xml_path)!r}); "
        "v.errors.each{|e| puts('ERROR '+e.logMessage.to_s)}; "
        "v.warnings.each{|w| puts('WARN '+w.logMessage.to_s)}"
    )
    try:
        result = subprocess.run(
            [str(settings.openstudio_cli), "-e", ruby],
            capture_output=True,
            text=True,
            check=False,
            timeout=60,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        xml_path.unlink(missing_ok=True)
        return [{"code": "schematron_unavailable", "field": "hpxml", "message": str(exc)}]
    xml_path.unlink(missing_ok=True)
    errors = []
    for line in (result.stdout or "").splitlines():
        if line.startswith("ERROR "):
            errors.append(line[6:].strip())
    return map_engine_errors(errors, code="schematron")


def emit_and_schema_errors(xml_text: str) -> list[dict[str, str]]:
    errors = inspect_hpxml(xml_text)
    if xml_text.find("<StateCode>") != -1 and xml_text.find("<ZipCode>") != -1:
        if xml_text.index("<StateCode>") > xml_text.index("<ZipCode>"):
            errors.append(
                {
                    "code": "address_order",
                    "field": "Address",
                    "message": "XSD requires StateCode before ZipCode",
                }
            )
    return errors


def official_sample_paths() -> dict[str, Path]:
    found = {}
    for key, path in (("base", OFFICIAL_BASE), ("hpwh", OFFICIAL_HPWH), ("xsd", OFFICIAL_XSD)):
        if path.exists():
            found[key] = path
    return found
