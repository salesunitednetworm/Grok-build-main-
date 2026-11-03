from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol


@dataclass
class JobSiteDraft:
    name: str
    our_job_id: str
    address: dict | None = None


@dataclass
class PhotoIngest:
    filename: str
    content_type: str
    data: bytes
    stage: str = "general"
    tags: list[str] = field(default_factory=list)
    visibility: str = "internal"
    client_uid: str | None = None


@dataclass
class Photo:
    id: str
    job_site_id: str
    captured_at: str
    stage: str
    tags: list[str]
    visibility: str
    bytes_uri: str
    sidecar_uri: str
    provider: str
    sha256: str
    external_id: str | None = None


@dataclass
class JobSite:
    id: str
    our_job_id: str
    name: str
    provider: str
    sidecar_uri: str


class JobPhotoPort(Protocol):
    def create_job_site(self, draft: JobSiteDraft) -> JobSite: ...

    def add_photo(self, job_site_id: str, ingest: PhotoIngest) -> Photo: ...

    def list_photos(self, job_site_id: str) -> list[Photo]: ...

    def add_tags(self, photo_id: str, tags: list[str]) -> Photo: ...

    def get_photo_bytes(self, photo_id: str) -> bytes: ...
