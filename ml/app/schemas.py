from __future__ import annotations

from pydantic import BaseModel, Field

STATUS_PROCESSING = "processing"
STATUS_DONE = "done"
STATUS_FAILED = "failed"
VERDICT_VIOLATION = "violation"
VERDICT_NO_VIOLATION = "no_violation"


class InferRequest(BaseModel):
    video_path: str = Field(min_length=1)


class EvidenceFrame(BaseModel):
    timestamp_sec: float
    image_base64: str


class RuleReference(BaseModel):
    document: str
    clause: str
    url: str


class Event(BaseModel):
    type_id: str
    type: str
    timecode_sec: float
    description: str
    evidence_frames: list[EvidenceFrame]
    rule: RuleReference


class InferMeta(BaseModel):
    frames: int
    sampled_fps: float
    duration_sec: float
    observations: int
    observers: list[str]
    elapsed_ms: int


class InferResponse(BaseModel):
    events: list[Event]
    meta: InferMeta


class AnalyzeResponse(BaseModel):
    job_id: str
    status: str


class JobResponse(BaseModel):
    job_id: str
    status: str
    verdict: str | None = None
    violations: list[Event] | None = None
    error: str | None = None


class ErrorResponse(BaseModel):
    error: str
