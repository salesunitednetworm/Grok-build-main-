"""PreSite Pro file adapter: disk + JSON sidecars. Not a clone of pre-site-pro."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path

from app.config import settings
from app.ports.photos import JobSite, JobSiteDraft, Photo, PhotoIngest


class PreSiteProFileAdapter:
    provider = "presitepro_file"

    def __init__(self, root: Path | None = None) -> None:
        self.root = Path(root or settings.artifact_root) / "presitepro"

    def _site_dir(self, job_site_id: str) -> Path:
        path = self.root / job_site_id
        path.mkdir(parents=True, exist_ok=True)
        return path

    def create_job_site(self, draft: JobSiteDraft) -> JobSite:
        site_id = str(uuid.uuid4())
        folder = self._site_dir(site_id)
        sidecar = {
            "schema": "presitepro.jobsite/v1",
            "job_site_id": site_id,
            "our_job_id": draft.our_job_id,
            "name": draft.name,
            "address": draft.address,
            "provider": self.provider,
        }
        path = folder / "jobsite.json"
        path.write_text(json.dumps(sidecar, indent=2), encoding="utf-8")
        return JobSite(
            id=site_id,
            our_job_id=draft.our_job_id,
            name=draft.name,
            provider=self.provider,
            sidecar_uri=str(path),
        )

    def add_photo(self, job_site_id: str, ingest: PhotoIngest) -> Photo:
        folder = self._site_dir(job_site_id)
        photo_id = str(uuid.uuid4())
        digest = sha256(ingest.data).hexdigest()
        blob = folder / f"{photo_id}.bin"
        blob.write_bytes(ingest.data)
        captured = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
        sidecar = {
            "schema": "presitepro.photo/v1",
            "job_site_id": job_site_id,
            "photo_id": photo_id,
            "client_uid": ingest.client_uid,
            "captured_at": captured,
            "stage": ingest.stage,
            "tags": ingest.tags,
            "visibility": ingest.visibility,
            "bytes_uri": str(blob),
            "sha256": digest,
            "provider": self.provider,
            "exif": {"original_filename": ingest.filename, "content_type": ingest.content_type},
        }
        sidecar_path = folder / f"{photo_id}.json"
        sidecar_path.write_text(json.dumps(sidecar, indent=2), encoding="utf-8")
        return self._photo(sidecar)

    def list_photos(self, job_site_id: str) -> list[Photo]:
        folder = self._site_dir(job_site_id)
        photos = []
        for path in sorted(folder.glob("*.json")):
            if path.name == "jobsite.json":
                continue
            photos.append(self._photo(json.loads(path.read_text(encoding="utf-8"))))
        return photos

    def add_tags(self, photo_id: str, tags: list[str]) -> Photo:
        path = self._find_sidecar(photo_id)
        data = json.loads(path.read_text(encoding="utf-8"))
        merged = list(dict.fromkeys([*(data.get("tags") or []), *tags]))
        data["tags"] = merged
        path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        return self._photo(data)

    def get_photo_bytes(self, photo_id: str) -> bytes:
        sidecar = json.loads(self._find_sidecar(photo_id).read_text(encoding="utf-8"))
        return Path(sidecar["bytes_uri"]).read_bytes()

    def _find_sidecar(self, photo_id: str) -> Path:
        matches = list(self.root.glob(f"*/{photo_id}.json"))
        if not matches:
            raise FileNotFoundError(photo_id)
        return matches[0]

    def _photo(self, sidecar: dict) -> Photo:
        return Photo(
            id=sidecar["photo_id"],
            job_site_id=sidecar["job_site_id"],
            captured_at=sidecar["captured_at"],
            stage=sidecar.get("stage") or "general",
            tags=list(sidecar.get("tags") or []),
            visibility=sidecar.get("visibility") or "internal",
            bytes_uri=sidecar["bytes_uri"],
            sidecar_uri=str(self.root / sidecar["job_site_id"] / f"{sidecar['photo_id']}.json"),
            provider=sidecar.get("provider") or self.provider,
            sha256=sidecar["sha256"],
        )
