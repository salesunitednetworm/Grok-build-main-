from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass
class ContactDraft:
    name: str
    email: str | None = None
    phone: str | None = None


@dataclass
class JobDraft:
    our_job_id: str
    name: str
    stage: str
    home_id: str


@dataclass
class ExternalRef:
    provider: str
    external_id: str
    status: str
    scopes_granted: list[str]
    note: str


class CrmPort(Protocol):
    def upsert_contact(self, draft: ContactDraft) -> ExternalRef: ...

    def upsert_job(self, draft: JobDraft) -> ExternalRef: ...

    def update_stage(self, ref: ExternalRef, stage: str) -> ExternalRef: ...

    def get_contact(self, ref: ExternalRef) -> dict: ...
