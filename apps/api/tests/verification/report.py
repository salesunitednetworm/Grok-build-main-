from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

HARNESS_VERSION = "0.2.0"
ARTIFACT_DIR = Path(__file__).parent / "artifacts"


def write_artifact(name: str, payload: dict[str, Any]) -> Path:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    document = {
        "harness_version": HARNESS_VERSION,
        "written_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "ashrae_140": {
            "verdict": None,
            "reason": "ASHRAE 140 / Guideline 14 are paid standards. This harness does not invent pass/fail.",
        },
        **payload,
    }
    path = ARTIFACT_DIR / f"{name}-v{HARNESS_VERSION}.json"
    path.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n")
    return path
