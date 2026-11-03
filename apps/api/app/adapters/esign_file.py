"""File e-sign adapter. Never claims a legally binding signature."""

from __future__ import annotations

import json
from pathlib import Path
from uuid import uuid4

from app.config import settings
from app.ports.esign import Document, Envelope, Signer


class FileESignAdapter:
    provider = "file"

    def __init__(self, root: Path | None = None) -> None:
        self.root = Path(root or settings.artifact_root) / "esign"
        self.root.mkdir(parents=True, exist_ok=True)

    def send_for_signature(self, document: Document, signers: list[Signer]) -> Envelope:
        envelope_id = str(uuid4())
        record = {
            "id": envelope_id,
            "provider": self.provider,
            "status": "pending_vendor",
            "title": document.title,
            "text": document.text,
            "our_document_id": document.our_document_id,
            "signers": [signer.__dict__ for signer in signers],
            "completed_pdf_uri": None,
            "note": (
                "File draft only. Dropbox Sign / Acrobat Sign were not called. "
                "test_mode or production send is pending a vendor adapter. Not legally binding."
            ),
        }
        (self.root / f"{envelope_id}.json").write_text(json.dumps(record, indent=2), encoding="utf-8")
        return self._envelope(record)

    def get_status(self, envelope_id: str) -> Envelope:
        path = self.root / f"{envelope_id}.json"
        if not path.exists():
            raise FileNotFoundError(envelope_id)
        return self._envelope(json.loads(path.read_text(encoding="utf-8")))

    def download_completed(self, envelope_id: str) -> bytes:
        envelope = self.get_status(envelope_id)
        if not envelope.completed_pdf_uri:
            raise FileNotFoundError("completed PDF has not been ingested; envelope is not signed")
        return Path(envelope.completed_pdf_uri).read_bytes()

    def ingest_completed_pdf(self, envelope_id: str, pdf: bytes) -> Envelope:
        """Record a completed PDF that arrived outside this adapter. Does not invent a vendor send."""
        path = self.root / f"{envelope_id}.json"
        record = json.loads(path.read_text(encoding="utf-8"))
        pdf_path = self.root / f"{envelope_id}.pdf"
        pdf_path.write_bytes(pdf)
        record["completed_pdf_uri"] = str(pdf_path)
        record["status"] = "completed_ingested"
        record["note"] = "Completed PDF ingested from an external source. This adapter did not obtain the signature."
        path.write_text(json.dumps(record, indent=2), encoding="utf-8")
        return self._envelope(record)

    def _envelope(self, record: dict) -> Envelope:
        return Envelope(
            id=record["id"],
            provider=record["provider"],
            status=record["status"],
            note=record["note"],
            completed_pdf_uri=record.get("completed_pdf_uri"),
            signers=[item.get("email") or item.get("name") for item in record.get("signers") or []],
        )
