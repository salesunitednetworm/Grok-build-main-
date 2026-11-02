from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol


@dataclass
class Signer:
    name: str
    email: str


@dataclass
class Document:
    title: str
    text: str
    our_document_id: str


@dataclass
class Envelope:
    id: str
    provider: str
    status: str
    note: str
    completed_pdf_uri: str | None = None
    signers: list[str] = field(default_factory=list)


class ESignPort(Protocol):
    def send_for_signature(self, document: Document, signers: list[Signer]) -> Envelope: ...

    def get_status(self, envelope_id: str) -> Envelope: ...

    def download_completed(self, envelope_id: str) -> bytes: ...
