from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

from app.config import settings
from app.domain.building import CanonicalBuilding
from app.domain.hpxml import (
    HPXML_NS,
    HPXML_SCHEMA_LABEL,
    generate_hpxml,
    inspect_hpxml,
)
from app.domain.results import parse_annual_results
from app.providers.base import (
    Availability,
    ProviderInput,
    ProviderRun,
    ProviderValidation,
)


class OpenStudioHpxmlProvider:
    id = "openstudio_hpxml"
    display_name = "OpenStudio-HPXML v1.12.0 (EnergyPlus 25.2.0)"
    engine_versions = {
        "openstudio_hpxml": "1.12.0",
        "openstudio": "3.11.0",
        "energyplus": "25.2.0",
        "hpxml": "5.0-rc1",
    }

    def generate_input(self, model: CanonicalBuilding) -> ProviderInput:
        return ProviderInput(
            xml_text=generate_hpxml(model),
            schema_version=HPXML_SCHEMA_LABEL,
            namespace=HPXML_NS,
        )

    def validate_input(self, provider_input: ProviderInput) -> ProviderValidation:
        errors = inspect_hpxml(provider_input.xml_text)
        return ProviderValidation(ok=not errors, errors=errors)

    def is_available(self) -> Availability:
        cli = settings.openstudio_cli or shutil.which("openstudio")
        if not cli or not Path(cli).exists():
            return Availability(
                available=False,
                reason=(
                    "OpenStudio 3.11.0 CLI is not installed. HPXML was generated, "
                    "but EnergyPlus did not run. No kWh is reported."
                ),
            )
        hpxml_dir = settings.openstudio_hpxml_dir
        script = None
        if hpxml_dir:
            script = Path(hpxml_dir) / "workflow" / "run_simulation.rb"
        if script is None or not script.exists():
            return Availability(
                available=False,
                reason=(
                    "OpenStudio-HPXML v1.12.0 tree is not installed "
                    "(workflow/run_simulation.rb missing). No kWh is reported."
                ),
            )
        return Availability(available=True)

    def run(self, provider_input: ProviderInput, workdir: Path) -> ProviderRun:
        workdir.mkdir(parents=True, exist_ok=True)
        xml_path = workdir / "building.xml"
        xml_path.write_text(provider_input.xml_text, encoding="utf-8")
        availability = self.is_available()
        if not availability.available:
            return ProviderRun(
                status="unavailable",
                unavailable_reason=availability.reason,
                artifacts={"hpxml_input": xml_path},
            )

        cli = settings.openstudio_cli or shutil.which("openstudio")
        script = Path(settings.openstudio_hpxml_dir) / "workflow" / "run_simulation.rb"
        run_dir = workdir / "run"
        command = [
            str(cli),
            str(script),
            "-x",
            str(xml_path),
            "-o",
            str(run_dir),
            "--output-format",
            "json",
        ]
        try:
            completed = subprocess.run(
                command,
                check=False,
                capture_output=True,
                text=True,
                timeout=300,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            return ProviderRun(
                status="failed",
                error_message=str(exc),
                artifacts={"hpxml_input": xml_path},
            )

        artifacts: dict[str, Path] = {"hpxml_input": xml_path}
        log_path = run_dir / "run.log"
        if completed.stdout or completed.stderr:
            fallback_log = workdir / "run.log"
            fallback_log.write_text((completed.stdout or "") + (completed.stderr or ""), encoding="utf-8")
            artifacts["run_log"] = fallback_log
        if log_path.exists():
            artifacts["run_log"] = log_path
        in_xml = run_dir / "in.xml"
        if in_xml.exists():
            artifacts["in_xml"] = in_xml
        annual = run_dir / "results_annual.json"
        if annual.exists():
            artifacts["results_annual_json"] = annual

        if completed.returncode != 0 or not annual.exists():
            message = (completed.stderr or completed.stdout or "OpenStudio-HPXML run failed").strip()
            return ProviderRun(status="failed", error_message=message[:4000], artifacts=artifacts)

        energy = parse_annual_results(json.loads(annual.read_text(encoding="utf-8")))
        return ProviderRun(status="succeeded", artifacts=artifacts, energy=energy)
