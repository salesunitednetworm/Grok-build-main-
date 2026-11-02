"""Poll queued simulation jobs. PostgreSQL is the queue in v1."""

from __future__ import annotations

import time

from app.config import settings
from app.db import SessionLocal, init_db
from app import services


def loop() -> None:
    settings.artifact_root.mkdir(parents=True, exist_ok=True)
    init_db()
    while True:
        db = SessionLocal()
        try:
            job = services.claim_next_job(db)
            if job is None:
                time.sleep(settings.worker_poll_seconds)
                continue
            services.process_job(db, job.id)
        finally:
            db.close()


if __name__ == "__main__":
    loop()
