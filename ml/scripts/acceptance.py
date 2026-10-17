"""Acceptance check against the public Spring API on the labelled dataset.

  python scripts/acceptance.py --labels ~/Downloads/labels_typed_v2.xlsx --videos-dir ~/Downloads/open/videos \
      --base-url http://localhost:8080 --api-key KEY --diagnostics-dir ../data/ml/diagnostics --out ../eval

Writes <out>/results.csv, <out>/report.md, <out>/failures/<video>/ and, with --warped-dir, the robustness section.
No per-video logic: every video goes through the same code path; ids are used only to join predictions with labels.
"""
from __future__ import annotations

import argparse
import base64
import csv
import hashlib
import json
import re
import statistics
import time
from dataclasses import dataclass, field
from pathlib import Path

import cv2
import httpx

from scripts.evaluate import (
    API_KEY_HEADER,
    IMPLEMENTED_TYPES,
    STATUS_DONE,
    STATUS_PROCESSING,
    VERDICT_VIOLATION,
    VISITOR_TYPES,
    Label,
    find_video,
    read_labels,
)

RULES_PATH = Path(__file__).resolve().parent.parent / "rules" / "rules.json"
VERDICTS = {"violation", "no_violation"}
JOB_KEYS = {"job_id", "status", "verdict", "violations"}
VIOLATION_KEYS = {"type", "timecode_sec", "description", "evidence_frames"}
FRAME_KEYS = {"timestamp_sec", "image_base64"}
JPEG_MAGIC = b"\xff\xd8\xff"
EVIDENCE_TOLERANCE_SEC = 5.0
CITATION_RE = re.compile(r"Нормативный источник: .+п\. ?\d+.*\.$")
CYRILLIC_RE = re.compile(r"[А-Яа-яЁё]")
MIN_CYRILLIC_RATIO = 0.5
MAX_PROCESSING_SEC = 120.0
BURST_SIZE = 5
BURST_LIMIT_SEC = 300.0
RECALL_MIN = 12
CLEAN_FP_MAX = 2
TIMECODE_TIGHT_SEC, TIMECODE_TIGHT_RATIO = 2.0, 0.70
TIMECODE_LOOSE_SEC, TIMECODE_LOOSE_RATIO = 5.0, 0.90
TYPE_ACCURACY_MIN = 0.80
MUST_DETECT = ["X-11", "X-15", "X-20", "X-22", "X-32"]
MUST_CLEAN = ["X-12", "X-23", "X-25", "X-31", "X-3", "X-5"]
VISITOR_CHECK_VIDEOS = ["X-4", "X-18", "X-30"]
DROPPED_CONFIDENCE_MIN = 0.6
MID_ROOM_X_MIN, MID_ROOM_MARGIN = 0.2, 0.1
POLL_SEC = 2.0
JOB_TIMEOUT_SEC = 330.0


@dataclass
class VideoResult:
    label: Label
    path: Path
    status: str
    body: dict
    elapsed_sec: float
    schema_errors: list[str] = field(default_factory=list)
    diagnostics: dict | None = None

    @property
    def violations(self) -> list[dict]:
        return self.body.get("violations") or []

    @property
    def predicted(self) -> bool:
        return self.body.get("verdict") == VERDICT_VIOLATION

    def predicted_type_ids(self, name_to_id: dict[str, str]) -> list[str]:
        return [name_to_id.get(v["type"], v["type"]) for v in self.violations]

    def best_timecode_error(self) -> float | None:
        if self.label.timecode is None or not self.violations:
            return None
        return min((v["timecode_sec"] - self.label.timecode for v in self.violations), key=abs)


class Catalog:
    def __init__(self, path: Path = RULES_PATH):
        raw = json.loads(path.read_text(encoding="utf-8"))
        self.name_to_id = {t["name_ru"]: t["type_id"] for t in raw["types"]}
        self.family = {t["type_id"]: t["family"] for t in raw["types"]}


# ---------------------------------------------------------------- API helpers

def check_auth(client: httpx.Client, base_url: str, video: Path) -> tuple[bool, str]:
    with video.open("rb") as f:
        no_key = client.post(f"{base_url}/api/v1/analyze", files={"file": (video.name, f, "video/quicktime")}, headers={API_KEY_HEADER: ""})
    with video.open("rb") as f:
        wrong = client.post(f"{base_url}/api/v1/analyze", files={"file": (video.name, f, "video/quicktime")}, headers={API_KEY_HEADER: "wrong-key"})
    bad_get = client.get(f"{base_url}/api/v1/jobs/none", headers={API_KEY_HEADER: "wrong-key"})
    ok = no_key.status_code == 401 and wrong.status_code == 401 and bad_get.status_code == 401
    return ok, f"no key={no_key.status_code}, wrong key={wrong.status_code}, wrong key GET={bad_get.status_code}"


def submit(client: httpx.Client, base_url: str, video: Path) -> str:
    with video.open("rb") as f:
        res = client.post(f"{base_url}/api/v1/analyze", files={"file": (video.name, f, "video/quicktime")})
    res.raise_for_status()
    return res.json()["job_id"]


def wait(client: httpx.Client, base_url: str, job_id: str, started: float) -> tuple[str, dict, float]:
    while time.time() - started < JOB_TIMEOUT_SEC:
        body = client.get(f"{base_url}/api/v1/jobs/{job_id}").json()
        if body.get("status") != STATUS_PROCESSING:
            return body.get("status", "unknown"), body, time.time() - started
        time.sleep(POLL_SEC)
    return "timeout", {}, time.time() - started


def run_video(client: httpx.Client, base_url: str, label: Label, video: Path) -> VideoResult:
    started = time.time()
    job_id = submit(client, base_url, video)
    status, body, elapsed = wait(client, base_url, job_id, started)
    return VideoResult(label=label, path=video, status=status, body=body, elapsed_sec=elapsed)


# ---------------------------------------------------------------- checks

def validate_schema(body: dict) -> list[str]:
    errors: list[str] = []
    if set(body) != JOB_KEYS:
        errors.append(f"job keys {sorted(body)} != {sorted(JOB_KEYS)}")
    if body.get("verdict") not in VERDICTS:
        errors.append(f"verdict={body.get('verdict')!r}")
    violations = body.get("violations")
    if not isinstance(violations, list):
        errors.append("violations is not a list")
        return errors
    if (body.get("verdict") == VERDICT_VIOLATION) != bool(violations):
        errors.append("verdict does not match violations emptiness")
    for i, v in enumerate(violations):
        errors.extend(f"violation[{i}]: {e}" for e in _validate_violation(v))
    return errors


def _validate_violation(v: dict) -> list[str]:
    errors: list[str] = []
    if set(v) != VIOLATION_KEYS:
        errors.append(f"keys {sorted(v)} != {sorted(VIOLATION_KEYS)}")
    frames = v.get("evidence_frames") or []
    if not 1 <= len(frames) <= 3:
        errors.append(f"{len(frames)} evidence frames")
    for frame in frames:
        if set(frame) != FRAME_KEYS:
            errors.append(f"frame keys {sorted(frame)}")
            continue
        try:
            raw = base64.b64decode(frame["image_base64"], validate=True)
            if not raw.startswith(JPEG_MAGIC):
                errors.append("image is not JPEG")
        except Exception:  # noqa: BLE001 - any decode failure is a contract failure
            errors.append("image_base64 does not decode")
        if abs(float(frame["timestamp_sec"]) - float(v["timecode_sec"])) > EVIDENCE_TOLERANCE_SEC:
            errors.append(f"evidence ts {frame['timestamp_sec']} is >{EVIDENCE_TOLERANCE_SEC}s from {v['timecode_sec']}")
    description = str(v.get("description", ""))
    letters = [c for c in description if c.isalpha()]
    if not letters or len(CYRILLIC_RE.findall(description)) / len(letters) < MIN_CYRILLIC_RATIO:
        errors.append("description is not in Russian")
    if not CITATION_RE.search(description.strip()):
        errors.append("description does not end with a normative reference with a clause")
    return errors


def dropped_mid_room_tracks(result: VideoResult) -> list[dict]:
    if not result.diagnostics:
        return []
    out = []
    for t in result.diagnostics["meta"]["tracks"]:
        x, y = t["mean_center"]
        mid_room = x > MID_ROOM_X_MIN and MID_ROOM_MARGIN < y < 1 - MID_ROOM_MARGIN
        if not t["counted"] and t["mean_score"] > DROPPED_CONFIDENCE_MIN and mid_room:
            out.append(t)
    return out


# ---------------------------------------------------------------- metrics

@dataclass
class Metrics:
    n: int
    implemented: list[VideoResult]
    detected: list[VideoResult]
    clean: list[VideoResult]
    clean_fp: list[VideoResult]
    visitor_fp: list[VideoResult]
    other: list[VideoResult]
    tight_ratio: float
    loose_ratio: float
    type_accuracy: float
    family_accuracy: float


def compute(results: list[VideoResult], catalog: Catalog) -> Metrics:
    implemented = [r for r in results if r.label.violation and r.label.type_id in IMPLEMENTED_TYPES]
    detected = [r for r in implemented if r.predicted]
    clean = [r for r in results if not r.label.violation]
    clean_fp = [r for r in clean if r.predicted]
    visitor_fp = [r for r in clean if any(t in VISITOR_TYPES for t in r.predicted_type_ids(catalog.name_to_id))]
    other = [r for r in results if r.label.violation and r.label.type_id not in IMPLEMENTED_TYPES]
    errors = [abs(r.best_timecode_error()) for r in detected if r.best_timecode_error() is not None]
    tight = sum(1 for e in errors if e <= TIMECODE_TIGHT_SEC) / len(errors) if errors else 0.0
    loose = sum(1 for e in errors if e <= TIMECODE_LOOSE_SEC) / len(errors) if errors else 0.0
    type_hits = sum(1 for r in detected if r.label.type_id in r.predicted_type_ids(catalog.name_to_id))
    family_hits = sum(
        1 for r in detected
        if catalog.family.get(r.label.type_id) in {catalog.family.get(t) for t in r.predicted_type_ids(catalog.name_to_id)}
    )
    return Metrics(
        n=len(results), implemented=implemented, detected=detected, clean=clean, clean_fp=clean_fp, visitor_fp=visitor_fp,
        other=other, tight_ratio=tight, loose_ratio=loose,
        type_accuracy=type_hits / len(detected) if detected else 0.0,
        family_accuracy=family_hits / len(detected) if detected else 0.0,
    )


def video_number(video_id: str) -> int:
    return int(video_id.split("-")[1])


# ---------------------------------------------------------------- burst

def burst_test(client: httpx.Client, base_url: str, results: list[VideoResult]) -> tuple[bool, list[str]]:
    longest = sorted(results, key=lambda r: _duration(r.path), reverse=True)[:BURST_SIZE]
    submitted = []
    for r in longest:
        started = time.time()
        submitted.append((r, submit(client, base_url, r.path), started))
    lines: list[str] = []
    ok = True
    for r, job_id, started in submitted:
        status, _, elapsed = wait(client, base_url, job_id, started)
        done = status == STATUS_DONE and elapsed <= BURST_LIMIT_SEC
        ok &= done
        lines.append(f"{r.label.video_id}: {status} in {elapsed:.0f}s ({'ok' if done else 'FAIL'})")
    return ok, lines


def _duration(path: Path) -> float:
    cap = cv2.VideoCapture(str(path))
    try:
        fps = cap.get(cv2.CAP_PROP_FPS) or 1.0
        return cap.get(cv2.CAP_PROP_FRAME_COUNT) / fps
    finally:
        cap.release()


# ---------------------------------------------------------------- failures

def save_failure(r: VideoResult, out: Path, reason: str) -> None:
    folder = out / "failures" / r.label.video_id
    folder.mkdir(parents=True, exist_ok=True)
    predicted = r.violations[0]["timecode_sec"] if r.violations else None
    label_ts = r.label.timecode
    points = {"label": label_ts, "predicted": predicted}
    if label_ts is not None and predicted is not None:
        points["midpoint"] = (label_ts + predicted) / 2
    if label_ts is None and predicted is not None:
        points["midpoint"] = predicted + EVIDENCE_TOLERANCE_SEC
    cap = cv2.VideoCapture(str(r.path))
    for name, ts in points.items():
        if ts is None:
            continue
        cap.set(cv2.CAP_PROP_POS_MSEC, float(ts) * 1000)
        ok, frame = cap.read()
        if ok:
            cv2.imwrite(str(folder / f"{name}_{float(ts):.1f}s.jpg"), frame)
    cap.release()
    (folder / "reason.txt").write_text(reason + "\n", encoding="utf-8")


def failure_reason(r: VideoResult, catalog: Catalog) -> str | None:
    predicted = ", ".join(f"{t}@{v['timecode_sec']}" for t, v in zip(r.predicted_type_ids(catalog.name_to_id), r.violations)) or "-"
    if r.label.violation and not r.predicted:
        kind = "implemented type" if r.label.type_id in IMPLEMENTED_TYPES else "not implemented type"
        return f"MISS ({kind}): label {r.label.type_id}@{r.label.timecode}, predicted {predicted}"
    if not r.label.violation and r.predicted:
        return f"FALSE POSITIVE on clean clip: predicted {predicted}"
    err = r.best_timecode_error()
    if err is not None and abs(err) > TIMECODE_LOOSE_SEC:
        return f"TIMECODE error {err:+.1f}s: label {r.label.type_id}@{r.label.timecode}, predicted {predicted}"
    return None


# ---------------------------------------------------------------- official labels (organiser file: verdict + timecode only)

OFFICIAL_VIOLATION_WORD = "нарушение"
OFFICIAL_CLEAN_PREFIX = "без"
OFFICIAL_TIMECODE_RE = re.compile(r"(\d+(?:[.,]\d+)?)")


def read_official_labels(path: Path) -> dict[str, tuple[bool, float | None]]:
    """open_labels.xlsx: `наименование файла | таймстемп ('22 секунда') | нарушение / без нарушения`."""
    from openpyxl import load_workbook

    ws = load_workbook(path, read_only=True, data_only=True).worksheets[0]
    labels: dict[str, tuple[bool, float | None]] = {}
    for row in list(ws.iter_rows(values_only=True))[1:]:
        if not row or row[0] is None:
            continue
        video_id = str(row[0]).strip().upper().replace("Х", "X")
        verdict_text = str(row[2] or "").strip().lower()
        violation = OFFICIAL_VIOLATION_WORD in verdict_text and not verdict_text.startswith(OFFICIAL_CLEAN_PREFIX)
        match = OFFICIAL_TIMECODE_RE.search(str(row[1] or ""))
        timecode = float(match.group(1).replace(",", ".")) if match and violation else None
        labels[video_id] = (violation, timecode)
    return labels


def official_block(results: list[VideoResult], official: dict[str, tuple[bool, float | None]]) -> str:
    rows = []
    tp = fp = fn = tn = 0
    errors: list[float] = []
    for r in results:
        key = r.label.video_id.upper()
        if key not in official:
            continue
        violation, timecode = official[key]
        predicted = r.predicted
        tp += violation and predicted
        fp += (not violation) and predicted
        fn += violation and not predicted
        tn += (not violation) and not predicted
        err = None
        if violation and predicted and timecode is not None and r.violations:
            err = min((v["timecode_sec"] - timecode for v in r.violations), key=abs)
            errors.append(abs(err))
        rows.append(f"| {r.label.video_id} | {'нарушение' if violation else '—'}{f' @{timecode:g}' if timecode is not None else ''} | "
                    f"{r.body.get('verdict') or r.status} | {'' if err is None else f'{err:+.1f}s'} |")
    n = tp + fp + fn + tn
    lines = ["## Official labels (organiser file: verdict + timecode only)", "",
             f"- videos matched: {n}; verdict accuracy {(tp + tn) / n:.0%}" if n else "- no videos matched",
             f"- violations: {tp + fn}, detected {tp} (recall {tp / (tp + fn):.0%}); clean: {fp + tn}, false positives {fp}" if n else "",
             (f"- timecode on detected violations: within ±2s {sum(e <= 2 for e in errors) / len(errors):.0%}, "
              f"within ±5s {sum(e <= 5 for e in errors) / len(errors):.0%}, MAE {sum(errors) / len(errors):.1f}s") if errors else "- timecode: n/a",
             "", "| video | official label | verdict | signed timecode error |", "|---|---|---|---|", *rows]
    return "\n".join(lines)


# ---------------------------------------------------------------- report

def pass_fail_table(rows: list[tuple[str, str, bool | None, str]]) -> str:
    lines = ["| # | Criterion | Result | Detail |", "|---|---|---|---|"]
    for num, name, ok, detail in rows:
        mark = "PASS" if ok else ("FAIL" if ok is False else "n/a")
        lines.append(f"| {num} | {name} | {mark} | {detail} |")
    return "\n".join(lines)


def metrics_block(title: str, m: Metrics, catalog: Catalog) -> str:
    lines = [f"### {title}", "",
             f"- videos: {m.n}; implemented-type violations: {len(m.implemented)}, detected: {len(m.detected)} "
             f"(recall {len(m.detected)}/{len(m.implemented)})",
             f"- clean videos: {len(m.clean)}; false positives: {len(m.clean_fp)} "
             f"({', '.join(r.label.video_id for r in m.clean_fp) or '-'}); visitor-type FP: "
             f"{', '.join(r.label.video_id for r in m.visitor_fp) or '-'}",
             f"- timecode within ±{TIMECODE_TIGHT_SEC:.0f}s: {m.tight_ratio:.0%}, within ±{TIMECODE_LOOSE_SEC:.0f}s: {m.loose_ratio:.0%}",
             f"- type accuracy: {m.type_accuracy:.0%}, family accuracy: {m.family_accuracy:.0%}", ""]
    lines += ["| video | label | predicted | signed timecode error |", "|---|---|---|---|"]
    for r in m.implemented:
        err = r.best_timecode_error()
        predicted = ", ".join(f"{t}@{v['timecode_sec']}" for t, v in zip(r.predicted_type_ids(catalog.name_to_id), r.violations)) or "-"
        lines.append(f"| {r.label.video_id} | {r.label.type_id}@{r.label.timecode} | {predicted} | {'' if err is None else f'{err:+.1f}s'} |")
    return "\n".join(lines)


def write_csv(results: list[VideoResult], catalog: Catalog, path: Path) -> None:
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["video_id", "gt_violation", "gt_timecode", "gt_type", "certainty", "status", "elapsed_sec", "verdict",
                    "predicted", "signed_timecode_error", "schema_errors", "tracks", "reflections", "behind_glass", "dropped_scores"])
        for r in results:
            tracks = (r.diagnostics or {}).get("meta", {}).get("tracks", [])
            w.writerow([
                r.label.video_id, int(r.label.violation), r.label.timecode, r.label.type_id, r.label.certainty, r.status,
                round(r.elapsed_sec, 1), r.body.get("verdict"),
                "; ".join(f"{t}@{v['timecode_sec']}" for t, v in zip(r.predicted_type_ids(catalog.name_to_id), r.violations)),
                r.best_timecode_error(), " | ".join(r.schema_errors), len(tracks),
                sum(1 for t in tracks if t["reflection"]), sum(1 for t in tracks if t["behind_glass"]),
                " ".join(f"{t['mean_score']:.2f}" for t in tracks if not t["counted"]),
            ])


# ---------------------------------------------------------------- main

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--labels", type=Path, required=True)
    parser.add_argument("--videos-dir", type=Path, required=True)
    parser.add_argument("--base-url", default="http://localhost:8080")
    parser.add_argument("--api-key", required=True)
    parser.add_argument("--diagnostics-dir", type=Path, required=True, help="ML service data_dir/diagnostics")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--sheet", type=int, default=0)
    parser.add_argument("--warped-dir", type=Path, default=None, help="videos produced by scripts/warp_videos.py (criterion 16)")
    parser.add_argument("--skip-burst", action="store_true")
    parser.add_argument("--tuned-half", choices=["odd", "even", "none"], default="none",
                        help="which half thresholds were tuned on; criteria are judged on the other half as well")
    parser.add_argument("--config-log", type=Path, default=None, help="markdown log of config changes to embed")
    parser.add_argument("--official-labels", type=Path, default=None, help="organiser's open_labels.xlsx (verdict + timecode only)")
    args = parser.parse_args()

    catalog = Catalog()
    args.out.mkdir(parents=True, exist_ok=True)
    labels = read_labels(args.labels, args.sheet)
    videos = {l.video_id: find_video(args.videos_dir, l.video_id) for l in labels}
    missing = [v for v, p in videos.items() if p is None]
    if missing:
        raise SystemExit(f"videos not found: {missing}")

    results: list[VideoResult] = []
    with httpx.Client(headers={API_KEY_HEADER: args.api_key}, timeout=120) as client:
        auth_ok, auth_detail = check_auth(client, args.base_url, videos[labels[0].video_id])
        for label in labels:
            r = run_video(client, args.base_url, label, videos[label.video_id])
            if r.status == STATUS_DONE:
                r.schema_errors = validate_schema(r.body)
            sha = hashlib.sha256(r.path.read_bytes()).hexdigest()
            diag = args.diagnostics_dir / f"{sha}.json"
            r.diagnostics = json.loads(diag.read_text(encoding="utf-8")) if diag.is_file() else None
            results.append(r)
            print(f"{label.video_id}: {r.status} {r.elapsed_sec:.0f}s verdict={r.body.get('verdict')} "
                  f"{'; '.join(f'{t}@{v['timecode_sec']}' for t, v in zip(r.predicted_type_ids(catalog.name_to_id), r.violations)) or '-'}"
                  f"{'  SCHEMA: ' + ' | '.join(r.schema_errors) if r.schema_errors else ''}", flush=True)
        burst_ok, burst_lines = (None, ["skipped"]) if args.skip_burst else burst_test(client, args.base_url, results)

        warped_results: list[VideoResult] = []
        if args.warped_dir:
            for label in labels:
                path = find_video(args.warped_dir, label.video_id)
                if path is None:
                    continue
                warped_results.append(run_video(client, args.base_url, label, path))
                print(f"warped {label.video_id}: {warped_results[-1].status} verdict={warped_results[-1].body.get('verdict')}", flush=True)

    write_csv(results, catalog, args.out / "results.csv")
    m = compute(results, catalog)
    halves = {
        "odd": compute([r for r in results if video_number(r.label.video_id) % 2 == 1], catalog),
        "even": compute([r for r in results if video_number(r.label.video_id) % 2 == 0], catalog),
    }
    judged = m if args.tuned_half == "none" else halves["even" if args.tuned_half == "odd" else "odd"]

    done = [r for r in results if r.status == STATUS_DONE]
    schema_bad = [r for r in done if r.schema_errors]
    elapsed = sorted(r.elapsed_sec for r in results)
    p50 = statistics.median(elapsed) if elapsed else 0.0
    slowest = max(results, key=lambda r: r.elapsed_sec)
    x47 = next((r for r in results if r.label.video_id == "X-47"), None)
    by_id = {r.label.video_id: r for r in results}
    must_detect_bad = [v for v in MUST_DETECT if v in by_id and not by_id[v].predicted]
    must_clean_bad = [v for v in MUST_CLEAN if v in by_id and by_id[v].predicted]
    dropped_failures = {v: dropped_mid_room_tracks(by_id[v]) for v in VISITOR_CHECK_VIDEOS if v in by_id}
    dropped_bad = {v: t for v, t in dropped_failures.items() if t}
    diag_missing = [r.label.video_id for r in results if r.diagnostics is None]

    rows = [
        ("1", "42/42 done, 0 failed, 0 timeouts", len(done) == len(results) and len(results) >= 42,
         f"done {len(done)}/{len(results)}; failed/timeout: {', '.join(r.label.video_id + ':' + r.status for r in results if r.status != STATUS_DONE) or '-'}"),
        ("2-4", "schema, JPEG, evidence ±5s, Russian description with clause", not schema_bad and bool(done),
         "; ".join(f"{r.label.video_id}: {' | '.join(r.schema_errors)}" for r in schema_bad) or "all responses valid"),
        ("5", "401 without / with wrong X-API-Key", auth_ok, auth_detail),
        ("6", f"max processing ≤ {MAX_PROCESSING_SEC:.0f}s", slowest.elapsed_sec <= MAX_PROCESSING_SEC,
         f"p50 {p50:.0f}s, max {slowest.elapsed_sec:.0f}s ({slowest.label.video_id}), X-47 {x47.elapsed_sec:.0f}s" if x47 else f"p50 {p50:.0f}s, max {slowest.elapsed_sec:.0f}s"),
        ("7", f"burst of {BURST_SIZE} longest within {BURST_LIMIT_SEC:.0f}s each", burst_ok, "; ".join(burst_lines)),
        ("8", f"recall on implemented types ≥ {RECALL_MIN}/14", len(judged.detected) >= RECALL_MIN,
         f"{len(judged.detected)}/{len(judged.implemented)} (judged set), all: {len(m.detected)}/{len(m.implemented)}"),
        ("9", f"clean FP ≤ {CLEAN_FP_MAX}, visitor-type FP = 0", len(judged.clean_fp) <= CLEAN_FP_MAX and not judged.visitor_fp,
         f"FP: {', '.join(r.label.video_id for r in m.clean_fp) or '-'}; visitor-type: {', '.join(r.label.video_id for r in m.visitor_fp) or '-'}"),
        ("10", "must-pass list", not must_detect_bad and not must_clean_bad,
         f"missed: {', '.join(must_detect_bad) or '-'}; false: {', '.join(must_clean_bad) or '-'}"),
        ("11", f"timecode ≥{TIMECODE_TIGHT_RATIO:.0%} within ±{TIMECODE_TIGHT_SEC:.0f}s and ≥{TIMECODE_LOOSE_RATIO:.0%} within ±{TIMECODE_LOOSE_SEC:.0f}s",
         judged.tight_ratio >= TIMECODE_TIGHT_RATIO and judged.loose_ratio >= TIMECODE_LOOSE_RATIO,
         f"±2s {m.tight_ratio:.0%}, ±5s {m.loose_ratio:.0%} (all); judged: ±2s {judged.tight_ratio:.0%}, ±5s {judged.loose_ratio:.0%}"),
        ("12", f"type accuracy ≥ {TYPE_ACCURACY_MIN:.0%}", judged.type_accuracy >= TYPE_ACCURACY_MIN,
         f"type {m.type_accuracy:.0%}, family {m.family_accuracy:.0%} (all); judged type {judged.type_accuracy:.0%}"),
        ("13", "non-implemented violations listed", True, f"{len(m.other)} listed below"),
        ("14", "track diagnostics logged per video", not diag_missing, f"missing for: {', '.join(diag_missing) or '-'}"),
        ("15", "no confident mid-room track dropped on X-4/X-18/X-30", not dropped_bad and all(v in by_id for v in VISITOR_CHECK_VIDEOS),
         "; ".join(f"{v}: {len(t)} dropped (scores {', '.join(str(x['mean_score']) for x in t)})" for v, t in dropped_bad.items()) or "ok"),
    ]

    failures: list[str] = []
    for r in results:
        reason = failure_reason(r, catalog)
        if reason:
            save_failure(r, args.out, reason)
            failures.append(f"- {r.label.video_id}: {reason}")

    report = ["# Acceptance report", "", f"Generated {time.strftime('%Y-%m-%d %H:%M')} — {len(results)} videos via {args.base_url}; "
              f"tuned half: {args.tuned_half}", "", pass_fail_table(rows), "", "## Metrics", "",
              metrics_block("All videos", m, catalog), "", metrics_block("Odd video numbers", halves["odd"], catalog), "",
              metrics_block("Even video numbers", halves["even"], catalog), "", "## Non-implemented labelled violations", ""]
    for r in m.other:
        predicted = ", ".join(f"{t}@{v['timecode_sec']}" for t, v in zip(r.predicted_type_ids(catalog.name_to_id), r.violations)) or "no_violation"
        report.append(f"- {r.label.video_id} ({r.label.type_id}@{r.label.timecode}): {predicted}")
    report += ["", "## Person-track diagnostics", "", "| video | tracks | reflection | behind glass | dropped (score) |", "|---|---|---|---|---|"]
    for r in results:
        tracks = (r.diagnostics or {}).get("meta", {}).get("tracks", [])
        dropped = ", ".join(f"#{t['id']} {t['mean_score']:.2f}" for t in tracks if not t["counted"]) or "-"
        report.append(f"| {r.label.video_id} | {len(tracks)} | {sum(1 for t in tracks if t['reflection'])} | "
                      f"{sum(1 for t in tracks if t['behind_glass'])} | {dropped} |")
    if warped_results:
        wm = compute(warped_results, catalog)
        report += ["", "## Robustness (perspective-warped copies)", "",
                   f"- originals: recall {len(m.detected)}/{len(m.implemented)}, clean FP {len(m.clean_fp)}/{len(m.clean)}",
                   f"- warped: recall {len(wm.detected)}/{len(wm.implemented)}, clean FP {len(wm.clean_fp)}/{len(wm.clean)} "
                   f"({', '.join(r.label.video_id for r in wm.clean_fp) or '-'}); done {sum(1 for r in warped_results if r.status == STATUS_DONE)}/{len(warped_results)}"]
    if args.official_labels and args.official_labels.is_file():
        report += ["", official_block(results, read_official_labels(args.official_labels))]
    if args.config_log and args.config_log.is_file():
        report += ["", "## Config change log", "", args.config_log.read_text(encoding="utf-8")]
    report += ["", "## Failures (frames in failures/<video>/)", ""] + (failures or ["none"])
    (args.out / "report.md").write_text("\n".join(report) + "\n", encoding="utf-8")
    print("\n" + pass_fail_table(rows))
    print(f"\nreport -> {args.out / 'report.md'}")


if __name__ == "__main__":
    main()
