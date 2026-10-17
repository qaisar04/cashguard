from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CONFIG = ROOT / "config.yml"
OBSERVER_DETECTOR = "detector"
OBSERVER_STUB = "stub"


class VideoConfig(BaseModel):
    fps: float = Field(gt=0)
    max_side: int = Field(gt=0)
    max_frames: int = Field(gt=0, description="long videos are sampled sparser so the frame count stays within the time budget")


class DetectorConfig(BaseModel):
    backend: str
    model: str
    device: str = "auto"
    batch_size: int = Field(gt=0)
    score_threshold: float = Field(ge=0, le=1)
    queries: dict[str, list[str]]


class ScreenConfig(BaseModel):
    enabled: bool = True
    clip_model: str
    min_luminance: float = Field(ge=0, le=255)
    panel_fraction: float = Field(gt=0, le=1, default=1.0)
    prototypes: Path | None = None
    knn_k: int = Field(ge=1, default=5)
    min_similarity: float = Field(ge=0, le=1, default=0.0)
    prompts: dict[str, list[str]]


class ZonesConfig(BaseModel):
    cashier_radius: float = Field(gt=0)
    desk_radius: float = Field(gt=0)
    safe_radius: float = Field(gt=0)
    door: list[list[float]] = Field(min_length=3)
    glass: list[list[float]] = Field(min_length=3)


class TrackingConfig(BaseModel):
    iou_threshold: float = Field(ge=0, le=1)
    max_missing_sec: float = Field(ge=0)
    reflection_corr: float = Field(ge=0, le=1)
    reflection_min_steps: int = Field(ge=2)
    reflection_min_motion: float = Field(ge=0)
    edge_margin: float = Field(ge=0, le=0.5)
    inside_vote_ratio: float = Field(ge=0, le=1)


class PersonVerifierConfig(BaseModel):
    enabled: bool = False
    prompts: dict[str, list[str]]


class RulesConfig(BaseModel):
    enabled: list[str] = Field(min_length=1)
    door_state_trusted: bool = False
    unattended_sec: float = Field(ge=0)
    safe_open_sec: float = Field(ge=0)
    door_open_sec: float = Field(ge=0)
    min_presence_sec: float = Field(ge=0)
    merge_gap_sec: float = Field(ge=0)
    max_events: int = Field(gt=0)


class EvidenceConfig(BaseModel):
    frames: int = Field(ge=1, le=3)
    max_side: int = Field(gt=0)
    jpeg_quality: int = Field(ge=1, le=100)
    draw_boxes: bool = True


class PipelineConfig(BaseModel):
    video: VideoConfig
    detectors: list[DetectorConfig] = Field(min_length=1)
    screen: ScreenConfig
    person_verifier: PersonVerifierConfig
    zones: ZonesConfig
    tracking: TrackingConfig
    rules: RulesConfig
    evidence: EvidenceConfig


def load_pipeline_config(path: Path = DEFAULT_CONFIG) -> PipelineConfig:
    with path.open(encoding="utf-8") as f:
        return PipelineConfig.model_validate(yaml.safe_load(f))


class Settings(BaseSettings):
    """Process-level settings (env vars); pipeline thresholds live in config.yml."""

    model_config = SettingsConfigDict(env_prefix="ML_", env_file=".env", extra="ignore")

    api_key: str = "change-me-ml"
    config_path: Path = DEFAULT_CONFIG
    observer: str = OBSERVER_DETECTOR
    stub_fixture: Path | None = None
    data_dir: Path = ROOT / "data"
    job_ttl_sec: int = 7200
    workers: int = 1
