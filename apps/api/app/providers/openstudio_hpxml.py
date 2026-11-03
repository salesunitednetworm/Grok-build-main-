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
from app.domain.software_defaults import parse_run_log_warnings, parse_software_defaults
from app.providers.base import (
    Availability,
    ProviderInput,
    ProviderRun,
    ProviderValidation,
)


def _failure_message(stderr: str | None, stdout: str | None, run_log: Path | None) -> str:
    chunks: list[str] = []
    if run_log and run_log.exists():
        text = run_log.read_text(encoding="utf-8", errors="replace")
        errors = [line.strip() for line in text.splitlines() if line.strip().startswith("Error:")]
        if errors:
            chunks.append("\n".join(errors))
    cli = "\n".join(part for part in (stderr or "", stdout or "") if part.strip())
    if cli:
        chunks.append(cli.strip())
    return "\n".join(chunks) or "OpenStudio-HPXML run failed"


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
        hpxml_dir = Path(settings.openstudio_hpxml_dir)
        script = hpxml_dir / "workflow" / "run_simulation.rb"
        # OS-HPXML writes artifacts under <output>/run/, not <output>/ itself.
        command = [
            str(cli),
            str(script),
            "-x",
            str(xml_path.resolve()),
            "-o",
            str(workdir.resolve()),
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
                cwd=str(hpxml_dir),
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            return ProviderRun(
                status="failed",
                error_message=str(exc),
                artifacts={"hpxml_input": xml_path},
            )

        artifacts: dict[str, Path] = {"hpxml_input": xml_path}
        run_dir = workdir / "run"
        if completed.stdout or completed.stderr:
            fallback_log = workdir / "cli.log"
            fallback_log.write_text((completed.stdout or "") + "\n" + (completed.stderr or ""), encoding="utf-8")
            artifacts["run_log"] = fallback_log
        for candidate in (run_dir / "run.log", workdir / "run.log"):
            if candidate.exists():
                artifacts["run_log"] = candidate
                break
        for candidate in (run_dir / "in.xml", workdir / "in.xml"):
            if candidate.exists():
                artifacts["in_xml"] = candidate
                break
        annual = None
        for candidate in (run_dir / "results_annual.json", workdir / "results_annual.json"):
            if candidate.exists():
                annual = candidate
                artifacts["results_annual_json"] = candidate
                break

        if completed.returncode != 0 or annual is None:
            message = _failure_message(completed.stderr, completed.stdout, artifacts.get("run_log"))
            return ProviderRun(status="failed", error_message=message[:4000], artifacts=artifacts)

        energy = parse_annual_results(json.loads(annual.read_text(encoding="utf-8")))
        in_xml = artifacts.get("in_xml")
        if in_xml and in_xml.exists():
            energy.software_defaults = parse_software_defaults(in_xml.read_text(encoding="utf-8"))
        run_log = artifacts.get("run_log")
        if run_log and run_log.exists():
            energy.run_log_warnings = parse_run_log_warnings(run_log.read_text(encoding="utf-8"))
        return ProviderRun(status="succeeded", artifacts=artifacts, energy=energy)
