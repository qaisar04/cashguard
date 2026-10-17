from __future__ import annotations

import logging
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from app.schemas import STATUS_DONE, STATUS_FAILED, STATUS_PROCESSING, Event

log = logging.getLogger(__name__)
ID_LENGTH = 8


class JobNotFound(KeyError):
    pass


@dataclass
class Job:
    id: str
    video_path: Path
    status: str = STATUS_PROCESSING
    events: list[Event] = field(default_factory=list)
    error: str | None = None
    finished_at: float | None = None


class JobStore:
    def __init__(self, run: Callable[[Path], list[Event]], workers: int, ttl_sec: int):
        self._run = run
        self._jobs: dict[str, Job] = {}
        self._lock = threading.Lock()
        self._executor = ThreadPoolExecutor(max_workers=workers, thread_name_prefix="ml-job")
        self._ttl_sec = ttl_sec

    def submit(self, video_path: Path) -> Job:
        job = Job(id=uuid.uuid4().hex[:ID_LENGTH], video_path=video_path)
        with self._lock:
            self._jobs[job.id] = job
        self._executor.submit(self._execute, job)
        return job

    def get(self, job_id: str) -> Job:
        self._evict()
        with self._lock:
            job = self._jobs.get(job_id)
        if job is None:
            raise JobNotFound(job_id)
        return job

    def _execute(self, job: Job) -> None:
        try:
            job.events = self._run(job.video_path)
            job.status = STATUS_DONE
        except Exception as e:  # noqa: BLE001 - any failure must surface as a failed job, never a hung one
            log.exception("job %s failed", job.id)
            job.error = str(e)
            job.status = STATUS_FAILED
        finally:
            job.finished_at = time.time()
            job.video_path.unlink(missing_ok=True)

    def _evict(self) -> None:
        cutoff = time.time() - self._ttl_sec
        with self._lock:
            expired = [jid for jid, j in self._jobs.items() if j.finished_at is not None and j.finished_at < cutoff]
            for jid in expired:
                del self._jobs[jid]
