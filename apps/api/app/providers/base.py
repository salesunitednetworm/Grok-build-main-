from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

from app.domain.building import CanonicalBuilding
from app.domain.results import ParsedAnnual


@dataclass
class Availability:
    available: bool
    reason: str | None = None


@dataclass
class ProviderInput:
    xml_text: str
    schema_version: str
    namespace: str


@dataclass
class ProviderValidation:
    ok: bool
    errors: list[dict[str, str]] = field(default_factory=list)


@dataclass
class ProviderRun:
    status: str  # succeeded | failed | unavailable
    unavailable_reason: str | None = None
    error_message: str | None = None
    artifacts: dict[str, Path] = field(default_factory=dict)
    energy: ParsedAnnual | None = None


class ModelProvider(Protocol):
    id: str
    display_name: str

    def generate_input(self, model: CanonicalBuilding) -> ProviderInput: ...

    def validate_input(self, provider_input: ProviderInput) -> ProviderValidation: ...

    def is_available(self) -> Availability: ...

    def run(self, provider_input: ProviderInput, workdir: Path) -> ProviderRun: ...
