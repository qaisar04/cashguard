from __future__ import annotations

import logging
import shutil
import uuid
from contextlib import asynccontextmanager
from dataclasses import asdict
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, UploadFile, status
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse

from app.auth import require_api_key
from app.jobs import JobNotFound
from app.schemas import (
    STATUS_DONE,
    VERDICT_NO_VIOLATION,
    VERDICT_VIOLATION,
    AnalyzeResponse,
    ErrorResponse,
    InferMeta,
    InferRequest,
    InferResponse,
    JobResponse,
)
from app.settings import Settings
from app.state import state, to_schema
from pipeline.video import VideoReadError

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger(__name__)

ALLOWED_SUFFIXES = {".mov", ".mp4"}
API_V1 = "/api/v1"


@asynccontextmanager
async def lifespan(_: FastAPI):
    if not state.initialized:
        state.init(Settings())
    yield


app = FastAPI(title="CashGuard ML", version="0.1.0", lifespan=lifespan)


@app.exception_handler(VideoReadError)
async def video_error(_, exc: VideoReadError):
    return JSONResponse(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, content=ErrorResponse(error=str(exc)).model_dump())


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "observer": state.settings.observer}


@app.post("/infer", response_model=InferResponse, dependencies=[Depends(require_api_key)])
async def infer(request: InferRequest) -> InferResponse:
    path = Path(request.video_path)
    if not path.is_file():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Video not found: {path}")
    events, meta = await run_in_threadpool(state.analyzer.analyze, path)
    return InferResponse(events=[to_schema(e) for e in events], meta=InferMeta.model_validate(asdict(meta)))


@app.post(f"{API_V1}/analyze", response_model=AnalyzeResponse, status_code=status.HTTP_202_ACCEPTED,
          dependencies=[Depends(require_api_key)])
async def analyze(file: UploadFile) -> AnalyzeResponse:
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in ALLOWED_SUFFIXES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Unsupported file type, expected {sorted(ALLOWED_SUFFIXES)}")
    target = state.settings.data_dir / f"{uuid.uuid4().hex}{suffix}"
    with target.open("wb") as out:
        await run_in_threadpool(shutil.copyfileobj, file.file, out)
    job = state.jobs.submit(target)
    return AnalyzeResponse(job_id=job.id, status=job.status)


@app.get(f"{API_V1}/jobs/{{job_id}}", response_model=JobResponse, response_model_exclude_none=True,
         dependencies=[Depends(require_api_key)])
def job_status(job_id: str) -> JobResponse:
    try:
        job = state.jobs.get(job_id)
    except JobNotFound:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Job not found: {job_id}")
    if job.status != STATUS_DONE:
        return JobResponse(job_id=job.id, status=job.status, error=job.error)
    verdict = VERDICT_VIOLATION if job.events else VERDICT_NO_VIOLATION
    return JobResponse(job_id=job.id, status=job.status, verdict=verdict, violations=job.events)
