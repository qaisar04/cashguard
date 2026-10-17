from __future__ import annotations

from dataclasses import replace

from pipeline.evidence import ROLE_CASHIER, ROLE_VISITOR, person_marks
from pipeline.seat import locate_seat
from pipeline.timeline import build_timeline
from pipeline.tracking import Track
from tests.helpers import AWAY, COUNTER, SEAT, box_at, zones

# Х-18 / Х-4 geometry: the laptop lies between the two; the client across the desk is within cashier_radius of it.
LAPTOP = (0.58, 0.45)
CASHIER_CHAIR = (0.49, 0.56)
CLIENT_SIDE = (0.38, 0.41)


def _zones():
    return replace(zones(cashier_ids=()), monitor=LAPTOP, seat=None)


def _track(track_id, where, start, end, **flags):
    return Track(track_id, [(float(t), box_at(where)) for t in range(start, end)], **flags)


def test_client_across_the_desk_is_closer_to_the_laptop_than_the_cashier():
    z = _zones()
    assert z.at_cashier_seat(CLIENT_SIDE) and z.at_cashier_seat(CASHIER_CHAIR)


def test_longest_dwell_track_is_the_cashier_and_the_seat_is_where_it_sits():
    z = _zones()
    seat = locate_seat([_track(1, CASHIER_CHAIR, 0, 20), _track(2, CLIENT_SIDE, 3, 20)], z)
    assert seat is not None and seat.cashier_ids == {1}
    assert seat.anchor == CASHIER_CHAIR


def test_track_coexisting_with_the_cashier_is_never_the_cashier_even_when_closer_to_the_laptop():
    z = _zones()
    seat = locate_seat([_track(1, CASHIER_CHAIR, 0, 20), _track(2, LAPTOP, 5, 15)], z)
    assert seat is not None and seat.cashier_ids == {1}


def test_retracked_cashier_sitting_at_the_seat_after_a_gap_is_the_cashier_again():
    z = _zones()
    back = (CASHIER_CHAIR[0] + 0.02, CASHIER_CHAIR[1] + 0.03)
    seat = locate_seat([_track(1, CASHIER_CHAIR, 0, 10), _track(2, AWAY, 10, 14), _track(3, back, 14, 20)], z)
    assert seat is not None and seat.cashier_ids == {1, 3}


def test_client_arriving_after_the_cashier_left_is_not_adopted_as_the_cashier():
    z = _zones()
    seat = locate_seat([_track(1, CASHIER_CHAIR, 0, 10), _track(2, CLIENT_SIDE, 12, 20)], z)
    assert seat is not None and seat.cashier_ids == {1}


def test_one_shared_frame_is_a_tracker_handoff_not_two_people():
    z = _zones()
    seat = locate_seat([_track(1, CASHIER_CHAIR, 0, 11), _track(2, CASHIER_CHAIR, 10, 20)], z)
    assert seat is not None and seat.cashier_ids == {1, 2}


def test_reflections_and_tracks_outside_never_become_the_cashier():
    z = _zones()
    seat = locate_seat([_track(1, CASHIER_CHAIR, 0, 20, reflection=True), _track(2, CLIENT_SIDE, 0, 5)], z)
    assert seat is not None and seat.cashier_ids == {2}


def test_no_seat_without_anybody_at_the_desk():
    z = _zones()
    assert locate_seat([_track(1, AWAY, 0, 20)], z) is None
    assert locate_seat([], z) is None


def test_timeline_roles_follow_the_track_not_the_distance_to_the_laptop():
    z = _zones()
    tracks = [_track(1, CASHIER_CHAIR, 0, 6), _track(2, CLIENT_SIDE, 2, 6, entered=True)]
    seat = locate_seat(tracks, z)
    z = z.with_seat(seat.anchor, seat.cashier_ids)
    tl = build_timeline([float(t) for t in range(6)], [], tracks, z)
    assert all(s.cashier_present for s in tl.states)
    assert [[p.track_id for p in s.visitors] for s in tl.states] == [[], [], [2], [2], [2], [2]]
    assert all(not p.at_seat for s in tl.states for p in s.visitors)


def test_cashier_away_from_the_seat_is_absent_but_still_not_a_visitor():
    z = zones()
    tracks = [Track(1, [(0.0, box_at(SEAT)), (1.0, box_at(AWAY)), (2.0, box_at(COUNTER))])]
    tl = build_timeline([0.0, 1.0, 2.0], [], tracks, z)
    assert [s.cashier_present for s in tl.states] == [True, False, False]
    assert all(s.visitors == [] for s in tl.states)


def test_evidence_labels_use_the_track_role():
    z = _zones()
    tracks = [_track(1, CASHIER_CHAIR, 0, 6), _track(2, CLIENT_SIDE, 2, 6)]
    seat = locate_seat(tracks, z)
    marks = person_marks(tracks, z.with_seat(seat.anchor, seat.cashier_ids))
    assert {m.track_id: m.label for m in marks[3.0]} == {1: ROLE_CASHIER, 2: ROLE_VISITOR}


def test_cashier_walking_out_past_the_seat_is_not_the_cashier_again():
    # Х-15: the cashier works standing next to the door; her re-tracked walk-out brushes the seat for two frames
    z = _zones()
    walk_out = Track(2, [(16.0, box_at((0.38, 0.47))), (17.0, box_at((0.47, 0.52))), (18.0, box_at((0.50, 0.53)))])
    seat = locate_seat([_track(1, CASHIER_CHAIR, 0, 15), walk_out], z)
    assert seat is not None and seat.cashier_ids == {1}


def test_seat_is_the_seated_position_not_the_median_of_standing_frames():
    # Х-24: 2 s seated at the laptop, then 6 s standing behind the desk (taller box, centre higher in the frame)
    z = _zones()
    seated = [(float(t), box_at(CASHIER_CHAIR, 0.07)) for t in range(2)]
    standing = [(float(t), (0.40, 0.25, 0.52, 0.49)) for t in range(2, 8)]
    seat = locate_seat([Track(1, seated + standing)], z)
    assert seat is not None and seat.anchor == CASHIER_CHAIR


def test_cashier_is_present_on_the_chair_or_standing_at_the_laptop_but_not_on_the_way_out():
    z = _zones()
    seat = locate_seat([_track(1, CASHIER_CHAIR, 0, 10)], z)
    z = z.with_seat(seat.anchor, seat.cashier_ids)
    standing_at_laptop = (0.52, 0.40)      # Х-14: 0.08 from the chair, 0.06 from the laptop
    walking_out = (0.36, 0.33)             # Х-26: 0.08-0.09 from the chair, 0.17+ from the laptop
    assert z.at_cashier_seat(CASHIER_CHAIR) and z.at_cashier_seat(standing_at_laptop)
    assert not z.at_cashier_seat(walking_out)
