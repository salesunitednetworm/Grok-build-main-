"""Parse OS-HPXML in.xml dataSource='software' defaults and run.log warnings."""

from __future__ import annotations

import xml.etree.ElementTree as ET

from app.domain.hpxml import HPXML_NS


def parse_software_defaults(xml_text: str) -> list[dict[str, str]]:
    """Return elements OS-HPXML marked dataSource='software'."""
    defaults: list[dict[str, str]] = []
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return defaults
    for node in root.iter():
        source = node.attrib.get("dataSource") or node.attrib.get("datasource")
        if source != "software":
            continue
        tag = node.tag.split("}", 1)[-1]
        ident = node.attrib.get("id") or ""
        text = (node.text or "").strip()
        if not text:
            child_bits = []
            for child in list(node):
                child_tag = child.tag.split("}", 1)[-1]
                child_text = (child.text or "").strip()
                if child_text:
                    child_bits.append(f"{child_tag}={child_text}")
            text = ", ".join(child_bits)
        defaults.append(
            {
                "element": tag,
                "id": ident,
                "value": text,
                "data_source": "software",
            }
        )
    return defaults


def parse_run_log_warnings(log_text: str) -> list[str]:
    warnings: list[str] = []
    for raw in log_text.splitlines():
        line = raw.strip()
        if not line:
            continue
        lowered = line.lower()
        if "warning" in lowered or lowered.startswith("warn"):
            warnings.append(line)
    return warnings


def inspect_in_xml_namespace(xml_text: str) -> bool:
    return HPXML_NS in xml_text
