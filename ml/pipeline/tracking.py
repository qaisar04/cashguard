from __future__ import annotations

from dataclasses import dataclass, field
from statistics import mean

from app.settings import TrackingConfig
from pipeline.geometry import Box, Point, center, iou
from pipeline.observers.base import Observation
from pipeline.zones import Zones

ATTR_INSIDE = "inside"
INSIDE_LABEL = "inside"


@dataclass
class Track:
    id: int
    points: list[tuple[float, Box]] = field(default_factory=list)
    scores: list[float] = field(default_factory=list)
    inside_votes: list[bool] = field(default_factory=list)
    reflection: bool = False
    behind_glass: bool = False
    entered: bool = False
    inside: bool | None = None

    @property
    def first_ts(self) -> float:
        return self.points[0][0]

    @property
    def last_ts(self) -> float:
        return self.points[-1][0]

    @property
    def mean_score(self) -> float:
        return mean(self.scores) if self.scores else 1.0

    def box_at(self, ts: float) -> Box | None:
        for point_ts, box in self.points:
            if abs(point_ts - ts) < 1e-6:
                return box
        return None

    def counted(self) -> bool:
        """A person that may be treated as present in the room (not a reflection, not someone outside the glass).

        Geometry decides; the CLIP vote can only veto.
        """
        if self.reflection or self.behind_glass:
            return False
        return self.inside is not False


def track(observations: list[Observation], iou_threshold: float, max_missing_sec: float) -> list[Track]:
    """Greedy IoU tracker over per-timestamp boxes of one kind. Deterministic, no learned components."""
    by_ts: dict[float, list[Observation]] = {}
    for o in observations:
        by_ts.setdefault(o.ts, []).append(o)
    tracks: list[Track] = []
    active: list[Track] = []
    next_id = 1
    for ts in sorted(by_ts):
        active = [t for t in active if ts - t.last_ts <= max_missing_sec]
        unmatched = list(by_ts[ts])
        pairs = sorted(
            ((iou(t.points[-1][1], o.box), ti, oi) for ti, t in enumerate(active) for oi, o in enumerate(unmatched)),
            reverse=True,
        )
        used_tracks: set[int] = set()
        used_boxes: set[int] = set()
        for score, ti, oi in pairs:
            if score < iou_threshold or ti in used_tracks or oi in used_boxes:
                continue
            _append(active[ti], unmatched[oi])
            used_tracks.add(ti)
            used_boxes.add(oi)
        for oi, o in enumerate(unmatched):
            if oi in used_boxes:
                continue
            new = Track(id=next_id)
            _append(new, o)
            next_id += 1
            tracks.append(new)
            active.append(new)
    return tracks


def _append(t: Track, o: Observation) -> None:
    t.points.append((o.ts, o.box))
    t.scores.append(o.score)
    label = o.attrs.get(ATTR_INSIDE)
    if label is not None:
        t.inside_votes.append(label == INSIDE_LABEL)


def annotate_tracks(tracks: list[Track], zones: Zones, cfg: TrackingConfig) -> None:
    """Flags reflections, decides which tracks actually entered the room, and folds in CLIP inside/outside votes."""
    _flag_reflections(tracks, cfg)
    for t in tracks:
        t.behind_glass = _stays_behind_glass(t, zones, cfg)
        t.entered = not t.behind_glass and _born_at_entrance(t, zones, cfg)
        if t.inside_votes:
            t.inside = sum(t.inside_votes) / len(t.inside_votes) >= cfg.inside_vote_ratio


def _flag_reflections(tracks: list[Track], cfg: TrackingConfig) -> None:
    for i, a in enumerate(tracks):
        for b in tracks[i + 1 :]:
            if a.reflection or b.reflection:
                continue
            if not _velocities_correlated(a, b, cfg):
                continue
            weaker = _weaker(a, b)
            weaker.reflection = True


def _velocities_correlated(a: Track, b: Track, cfg: TrackingConfig) -> bool:
    va, vb = _common_velocities(a, b)
    if len(va) < cfg.reflection_min_steps:
        return False
    moving = sum(abs(x) + abs(y) for x, y in va) > cfg.reflection_min_motion and sum(abs(x) + abs(y) for x, y in vb) > cfg.reflection_min_motion
    if not moving:
        return False
    corr_x = _abs_cosine([v[0] for v in va], [v[0] for v in vb])
    corr_y = _abs_cosine([v[1] for v in va], [v[1] for v in vb])
    return corr_x >= cfg.reflection_corr and corr_y >= cfg.reflection_corr and _similar_speed(va, vb)


def _common_velocities(a: Track, b: Track) -> tuple[list[Point], list[Point]]:
    pos_a = {ts: center(box) for ts, box in a.points}
    pos_b = {ts: center(box) for ts, box in b.points}
    common = sorted(set(pos_a) & set(pos_b))
    va: list[Point] = []
    vb: list[Point] = []
    for prev, cur in zip(common, common[1:]):
        va.append((pos_a[cur][0] - pos_a[prev][0], pos_a[cur][1] - pos_a[prev][1]))
        vb.append((pos_b[cur][0] - pos_b[prev][0], pos_b[cur][1] - pos_b[prev][1]))
    return va, vb


def _abs_cosine(xs: list[float], ys: list[float]) -> float:
    # uncentered so that steady, proportional motion (the typical mirror image) scores 1; sign is ignored (mirrored axis)
    sxx = sum(x * x for x in xs)
    syy = sum(y * y for y in ys)
    if sxx == 0 or syy == 0:
        return 0.0
    return abs(sum(x * y for x, y in zip(xs, ys))) / (sxx * syy) ** 0.5


SPEED_RATIO_MAX = 2.0


def _similar_speed(va: list[Point], vb: list[Point]) -> bool:
    sa = sum((x * x + y * y) ** 0.5 for x, y in va)
    sb = sum((x * x + y * y) ** 0.5 for x, y in vb)
    if sa == 0 or sb == 0:
        return False
    ratio = sa / sb
    return 1 / SPEED_RATIO_MAX <= ratio <= SPEED_RATIO_MAX


def _weaker(a: Track, b: Track) -> Track:
    # the reflection appears no earlier than its source; among equals keep the higher-confidence, larger track
    if a.first_ts != b.first_ts:
        return a if a.first_ts > b.first_ts else b
    if a.mean_score != b.mean_score:
        return a if a.mean_score < b.mean_score else b
    return a if _mean_area(a) < _mean_area(b) else b


def _mean_area(t: Track) -> float:
    return mean((b[2] - b[0]) * (b[3] - b[1]) for _, b in t.points)


def _stays_behind_glass(t: Track, zones: Zones, cfg: TrackingConfig) -> bool:
    """Reflections and people in the corridor live in the glass-wall strip / frame edge and never step out of it.

    A real visitor comes through the door and walks toward the desk; a track that materialises mid-room is a broken
    track of someone already inside, so only tracks confined to the glass strip are excluded.
    """
    centers = [center(b) for _, b in t.points]
    if any(zones.at_cashier_seat(c) for c in centers):
        return False  # the cashier's seat is inside the room even when the glazing behind it covers that area
    return all(zones.in_glass(c) or _near_edge(c, cfg.edge_margin) for c in centers)


def _born_at_entrance(t: Track, zones: Zones, cfg: TrackingConfig) -> bool:
    """Real entries start at the door or a frame edge; a track born mid-room is someone already inside, re-tracked."""
    born = center(t.points[0][1])
    return zones.in_door(born) or _near_edge(born, cfg.edge_margin)


def _near_edge(p: Point, margin: float) -> bool:
    return p[0] <= margin or p[1] <= margin or p[0] >= 1 - margin or p[1] >= 1 - margin
