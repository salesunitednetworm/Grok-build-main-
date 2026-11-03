"""File CRM adapter. Never reports Zoho or HighLevel success."""

from __future__ import annotations

import json
from pathlib import Path
from uuid import uuid4

from app.config import settings
from app.ports.crm import ContactDraft, ExternalRef, JobDraft


class FileCrmAdapter:
    provider = "file"
    status = "pending_vendor"

    def __init__(self, root: Path | None = None) -> None:
        self.root = Path(root or settings.artifact_root) / "crm"
        self.root.mkdir(parents=True, exist_ok=True)

    def upsert_contact(self, draft: ContactDraft) -> ExternalRef:
        return self._write("contact", draft.__dict__)

    def upsert_job(self, draft: JobDraft) -> ExternalRef:
        return self._write("job", draft.__dict__)

    def update_stage(self, ref: ExternalRef, stage: str) -> ExternalRef:
        path = self.root / f"{ref.external_id}.json"
        if not path.exists():
            raise FileNotFoundError(ref.external_id)
        data = json.loads(path.read_text(encoding="utf-8"))
        data["payload"]["stage"] = stage
        path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        return ExternalRef(
            provider=self.provider,
            external_id=ref.external_id,
            status=self.status,
            scopes_granted=[],
            note="Stage stored in the file adapter only. No CRM vendor was called.",
        )

    def get_contact(self, ref: ExternalRef) -> dict:
        path = self.root / f"{ref.external_id}.json"
        return json.loads(path.read_text(encoding="utf-8"))

    def _write(self, kind: str, payload: dict) -> ExternalRef:
        external_id = str(uuid4())
        record = {
            "provider": self.provider,
            "status": self.status,
            "kind": kind,
            "payload": payload,
            "note": "File-only CRM record. Zoho/HighLevel were not called.",
        }
        (self.root / f"{external_id}.json").write_text(json.dumps(record, indent=2), encoding="utf-8")
        return ExternalRef(
            provider=self.provider,
            external_id=external_id,
            status=self.status,
            scopes_granted=[],
            note=record["note"],
        )
