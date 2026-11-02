"""HPXML schema / emit checks used by the verification harness."""

from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path

from app.domain.hpxml import inspect_hpxml

OFFICIAL_XSD = Path("/opt/OpenStudio-HPXML-1.12.0/HPXMLtoOpenStudio/resources/hpxml_schema/HPXML.xsd")
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
    return [{"code": "xsd", "field": "hpxml", "message": message}]


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
