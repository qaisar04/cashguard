from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CONFIG = ROOT / "config.yml"
OBSERVER_DETECTOR = "detector"
OBSERVER_STUB = "stub"
EMBEDDING_GLOBAL = "global"
EMBEDDING_SPATIAL = "spatial"


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
    group_thresholds: dict[str, float] = Field(default_factory=dict, description="per-group override of score_threshold")
    frame_stride: int = Field(ge=1, default=1, description="run on every n-th sampled frame; detections are carried to the skipped frames")
    queries: dict[str, list[str]]

    @property
    def detection_threshold(self) -> float:
        return min([self.score_threshold, *self.group_thresholds.values()])

    def passes(self, group: str, score: float) -> bool:
        return score >= self.group_thresholds.get(group, self.score_threshold)


class ScreenConfig(BaseModel):
    enabled: bool = True
    clip_model: str
    min_luminance: float = Field(ge=0, le=255)
    panel_fraction: float = Field(gt=0, le=1, default=1.0)
    prototypes: Path | None = None
    embedding: str = Field(default=EMBEDDING_GLOBAL, pattern=f"^({EMBEDDING_GLOBAL}|{EMBEDDING_SPATIAL})$")
    knn_k: int = Field(ge=1, default=5)
    min_similarity: float = Field(ge=0, le=1, default=0.0)
    prompts: dict[str, list[str]]


class GlassDetectionConfig(BaseModel):
    enabled: bool = True
    min_frames: int = Field(ge=1, default=3, description="frames with a detected glass pane before detections replace the polygons")
    edge_pane_max_fraction: float = Field(gt=0, le=1, default=0.75, description="a pane at the frame edge narrower than this share of the glazing is the reflection strip")
    pad: float = Field(ge=0, le=0.2, default=0.02)
class AnchorConfig(BaseModel):
    """Where a static object (safe, door) is in the frame: OWLv2 median box over the video, else a fixed normalized box."""

    queries: list[str] = Field(default_factory=list)
    score_threshold: float = Field(ge=0, le=1, default=0.15)
    stride: int = Field(ge=1, default=5, description="every n-th sampled frame is searched")
    min_hits: int = Field(ge=1, default=3)
    min_similarity: float = Field(ge=0, le=1, default=0.0, description="candidate crops less similar to the prototypes are look-alikes")
    pad: float = Field(ge=0, default=0.0, description="crop margin as a fraction of the detected box size")
    fallback_box: list[float] = Field(min_length=4, max_length=4)


class StateConfig(BaseModel):
    """Few-shot open/closed classifier of a static crop (safe, door)."""

    enabled: bool = True
    prototypes: Path
    embedding: str = Field(default=EMBEDDING_SPATIAL, pattern=f"^({EMBEDDING_GLOBAL}|{EMBEDDING_SPATIAL})$")
    knn_k: int = Field(ge=1, default=1)
    min_similarity: float = Field(ge=0, le=1, default=0.0)
    smooth_frames: int = Field(ge=1, default=1, description="odd window of a per-frame majority vote")
    anchor: AnchorConfig


class ZonesConfig(BaseModel):
    cashier_radius: float = Field(gt=0)
    desk_radius: float = Field(gt=0)
    seat_radius: float = Field(gt=0, default=0.08)
    seat_settle_sec: float = Field(ge=0, default=2.0)
    safe_radius: float = Field(gt=0)
    door: list[list[float]] = Field(min_length=3)
    glass: list[list[float]] = Field(min_length=3)
    glass_detection: GlassDetectionConfig = Field(default_factory=GlassDetectionConfig)


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


class VlmConfig(BaseModel):
    """Action understanding over short frame windows with a small vision-language model (pipeline/observers/vlm.py)."""

    enabled: bool = False
    model: str = "Qwen/Qwen3-VL-2B-Instruct"
    device: str = "auto"
    mode: str = Field(default="json", pattern="^(list|json|yes_no)$", description="json: one JSON answer per window; list: one short answer naming the true keys; yes_no: P(yes) per question (7 forward passes)")
    stride_sec: float = Field(gt=0, default=5.0)
    window_sec: float = Field(gt=0, default=6.0)
    frames_per_window: int = Field(ge=1, le=4, default=3)
    max_side: int = Field(gt=0, default=640, description="each window frame is cropped to the desk area and resized to this")
    crop_margin: float = Field(ge=0, le=0.5, default=0.08)
    min_crop_height: float = Field(gt=0, le=1, default=0.5)
    max_new_tokens: int = Field(gt=0, default=120)
    min_confidence: float = Field(ge=0, le=1, default=0.5)
    require_person_near_desk: bool = True


class RulesConfig(BaseModel):
    enabled: list[str] = Field(min_length=1)
    door_state_trusted: bool = False
    seat_core_radius: float = Field(gt=0, default=0.10, description="within this distance of the seat the cashier is 'working'; leaving it marks the departure time")
    departure_lookback_sec: float = Field(ge=0, default=6)
    unattended_sec: float = Field(ge=0)
    safe_open_sec: float = Field(ge=0)
    door_open_sec: float = Field(ge=0)
    personal_items_sec: float = Field(ge=0, default=4)
    food_drink_sec: float = Field(ge=0, default=4)
    min_presence_sec: float = Field(ge=0)
    merge_gap_sec: float = Field(ge=0)
    max_events: int = Field(gt=0)
    machine_lookaround_sec: float = Field(ge=0, default=15.0, description="hand counting this close to machine counting is a pre-count, not a violation")
    recount_lookback_sec: float = Field(ge=0, default=60.0, description="counting this long before cash goes into the safe counts as a recount")
    collector_leave_sec: float = Field(ge=0, default=12.0, description="a collector gone this soon after dropping the bag left without a check")
    client_gone_sec: float = Field(ge=0, default=3.0, description="a visitor counts as gone after this many visitor-free seconds (shorter gaps are track dropouts)")


class EvidenceConfig(BaseModel):
    frames: int = Field(ge=1, le=3)
    max_side: int = Field(gt=0)
    jpeg_quality: int = Field(ge=1, le=100)
    draw_boxes: bool = True


class PipelineConfig(BaseModel):
    video: VideoConfig
    detectors: list[DetectorConfig] = Field(min_length=1)
    screen: ScreenConfig
    safe: StateConfig
    door: StateConfig
    person_verifier: PersonVerifierConfig
    zones: ZonesConfig
    tracking: TrackingConfig
    rules: RulesConfig
    evidence: EvidenceConfig
    vlm: VlmConfig = VlmConfig()


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
