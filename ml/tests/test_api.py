from __future__ import annotations

import base64
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.settings import OBSERVER_STUB, Settings
from app.state import state
from scripts.make_sample_video import write

API_KEY = "test-key"
FIXTURE = Path(__file__).parent / "fixtures" / "sample_observations.json"
POLL_TIMEOUT_SEC = 30


@pytest.fixture(scope="module")
def client(tmp_path_factory):
    data_dir = tmp_path_factory.mktemp("data")
    state.init(Settings(api_key=API_KEY, observer=OBSERVER_STUB, stub_fixture=FIXTURE, data_dir=data_dir))
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="module")
def sample_video(tmp_path_factory) -> Path:
    path = tmp_path_factory.mktemp("video") / "sample.mov"
    write(path, seconds=12)
    return path


def test_rejects_missing_api_key(client):
    assert client.post("/infer", json={"video_path": "x"}).status_code == 401


def test_infer_returns_events_with_evidence(client, sample_video):
    res = client.post("/infer", json={"video_path": str(sample_video)}, headers={"X-API-Key": API_KEY})
    assert res.status_code == 200, res.text
    body = res.json()
    types = {e["type_id"] for e in body["events"]}
    assert types == {"valuables_left_unattended"}  # workstation_unlocked in the same window is suppressed
    event = body["events"][0]
    assert event["timecode_sec"] == 6.0
    assert event["rule"]["url"].startswith("https://adilet.zan.kz")
    assert 1 <= len(event["evidence_frames"]) <= 3
    base64.b64decode(event["evidence_frames"][0]["image_base64"])
    assert body["meta"]["frames"] >= 12


def test_job_flow_matches_public_contract(client, sample_video):
    with sample_video.open("rb") as f:
        res = client.post("/api/v1/analyze", files={"file": ("v.mov", f, "video/quicktime")}, headers={"X-API-Key": API_KEY})
    assert res.status_code == 202, res.text
    job_id = res.json()["job_id"]
    deadline = time.time() + POLL_TIMEOUT_SEC
    while time.time() < deadline:
        body = client.get(f"/api/v1/jobs/{job_id}", headers={"X-API-Key": API_KEY}).json()
        if body["status"] != "processing":
            break
        time.sleep(0.2)
    assert body["status"] == "done", body
    assert body["verdict"] == "violation"
    assert set(body["violations"][0]) == {"type_id", "type", "timecode_sec", "description", "evidence_frames", "rule"}


def test_unknown_job_is_404(client):
    assert client.get("/api/v1/jobs/nope", headers={"X-API-Key": API_KEY}).status_code == 404


def test_analyze_rejects_wrong_extension(client):
    res = client.post("/api/v1/analyze", files={"file": ("v.txt", b"abc", "text/plain")}, headers={"X-API-Key": API_KEY})
    assert res.status_code == 400
