from __future__ import annotations

import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

TEST_ROOT = Path("/tmp/hems-tests")
TEST_ROOT.mkdir(parents=True, exist_ok=True)
os.environ["DATABASE_URL"] = "sqlite:///" + str(TEST_ROOT / "test.db")
os.environ["ARTIFACT_ROOT"] = str(TEST_ROOT / "artifacts")
os.environ["WORKER_INLINE"] = "true"
os.environ["OPENSTUDIO_CLI"] = ""
os.environ["OPENSTUDIO_HPXML_DIR"] = ""

from app.config import settings  # noqa: E402

settings.database_url = os.environ["DATABASE_URL"]
settings.artifact_root = Path(os.environ["ARTIFACT_ROOT"])
settings.worker_inline = True
settings.openstudio_cli = ""
settings.openstudio_hpxml_dir = None

from app.db import Base, SessionLocal, engine, init_db  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture(autouse=True)
def reset_db():
    Base.metadata.drop_all(bind=engine)
    init_db()
    settings.artifact_root.mkdir(parents=True, exist_ok=True)
    yield


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)
