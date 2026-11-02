from __future__ import annotations

import hashlib
from pathlib import Path

from app.config import settings


def write_artifact(job_id: str, kind: str, source: Path | str, suffix: str) -> tuple[str, int, str]:
    root = Path(settings.artifact_root)
    dest_dir = root / job_id
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / f"{kind}{suffix}"
    if isinstance(source, Path):
        data = source.read_bytes()
    else:
        data = source.encode("utf-8")
    dest.write_bytes(data)
    digest = hashlib.sha256(data).hexdigest()
    return str(dest), len(data), digest


def read_artifact(path: str) -> bytes:
    return Path(path).read_bytes()
