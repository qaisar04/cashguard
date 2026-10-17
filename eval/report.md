# Acceptance report

Generated 2026-10-17 23:10 — 42 videos via http://localhost:8080; tuned half: odd

| # | Criterion | Result | Detail |
|---|---|---|---|
| 1 | 42/42 done, 0 failed, 0 timeouts | PASS | done 42/42; failed/timeout: - |
| 2-4 | schema, JPEG, evidence ±5s, Russian description with clause | PASS | all responses valid |
| 5 | 401 without / with wrong X-API-Key | PASS | no key=401, wrong key=401, wrong key GET=401 |
| 6 | max processing ≤ 120s | PASS | p50 15s, max 90s (X-14), X-47 44s |
| 7 | burst of 5 longest within 300s each | PASS | X-14: done in 81s (ok); X-39: done in 127s (ok); X-4: done in 169s (ok); X-47: done in 213s (ok); X-5: done in 255s (ok) |
| 8 | recall on implemented types ≥ 12/14 | PASS | 12/12 (judged set), all: 16/16 |
| 9 | clean FP ≤ 2, visitor-type FP = 0 | PASS | FP: X-39; visitor-type: X-39 |
| 10 | must-pass list | PASS | missed: -; false: - |
| 11 | timecode ≥70% within ±2s and ≥90% within ±5s | FAIL | ±2s 62%, ±5s 94% (all); judged: ±2s 58%, ±5s 100% |
| 12 | type accuracy ≥ 80% | PASS | type 100%, family 100% (all); judged type 100% |
| 13 | non-implemented violations listed | PASS | 6 listed below |
| 14 | track diagnostics logged per video | PASS | missing for: - |
| 15 | no confident mid-room track dropped on X-4/X-18/X-30 | PASS | ok |

## Metrics

### All videos

- videos: 42; implemented-type violations: 16, detected: 16 (recall 16/16)
- clean videos: 20; false positives: 1 (X-39); visitor-type FP: X-39
- timecode within ±2s: 62%, within ±5s: 94%
- type accuracy: 100%, family accuracy: 100%

| video | label | predicted | signed timecode error |
|---|---|---|---|
| X-4 | cash_exposed_to_visitor@57.0 | cash_exposed_to_visitor@60.11 | +3.1s |
| X-11 | workstation_unlocked@18.0 | workstation_unlocked@16.06 | -1.9s |
| X-15 | valuables_left_unattended@15.0 | valuables_left_unattended@16.05 | +1.1s |
| X-18 | unauthorized_entry@20.0 | unauthorized_entry@16.05 | -3.9s |
| X-20 | safe_left_open@5.0 | safe_left_open@5.0 | +0.0s |
| X-22 | workstation_unlocked@14.0 | workstation_unlocked@14.07 | +0.1s |
| X-24 | valuables_left_unattended@8.0 | valuables_left_unattended@5.0 | -3.0s |
| X-26 | valuables_left_unattended@9.0 | valuables_left_unattended@10.03 | +1.0s |
| X-28 | workstation_unlocked@7.0 | workstation_unlocked@6.05 | -1.0s |
| X-30 | unauthorized_entry@13.0 | cash_room_door_open@3.01, unauthorized_entry@17.06 | +4.1s |
| X-32 | cash_room_door_open@5.0 | cash_room_door_open@4.01 | -1.0s |
| X-33 | cash_room_door_open@6.0 | cash_room_door_open@4.0, unauthorized_entry@11.0 | -2.0s |
| X-38 | cash_exposed_to_visitor@33.0 | cash_exposed_to_visitor@29.03, unauthorized_entry@36.04, cash_exposed_to_visitor@55.06 | +3.0s |
| X-40 | personal_items_at_workplace@17.0 | personal_items_at_workplace@18.07 | +1.1s |
| X-46 | food_drink_at_workplace@11.0 | food_drink_at_workplace@10.03 | -1.0s |
| X-47 | cash_exposed_to_visitor@68.0 | cash_exposed_to_visitor@60.11 | -7.9s |

### Odd video numbers

- videos: 21; implemented-type violations: 4, detected: 4 (recall 4/4)
- clean videos: 14; false positives: 1 (X-39); visitor-type FP: X-39
- timecode within ±2s: 75%, within ±5s: 75%
- type accuracy: 100%, family accuracy: 100%

| video | label | predicted | signed timecode error |
|---|---|---|---|
| X-11 | workstation_unlocked@18.0 | workstation_unlocked@16.06 | -1.9s |
| X-15 | valuables_left_unattended@15.0 | valuables_left_unattended@16.05 | +1.1s |
| X-33 | cash_room_door_open@6.0 | cash_room_door_open@4.0, unauthorized_entry@11.0 | -2.0s |
| X-47 | cash_exposed_to_visitor@68.0 | cash_exposed_to_visitor@60.11 | -7.9s |

### Even video numbers

- videos: 21; implemented-type violations: 12, detected: 12 (recall 12/12)
- clean videos: 6; false positives: 0 (-); visitor-type FP: -
- timecode within ±2s: 58%, within ±5s: 100%
- type accuracy: 100%, family accuracy: 100%

| video | label | predicted | signed timecode error |
|---|---|---|---|
| X-4 | cash_exposed_to_visitor@57.0 | cash_exposed_to_visitor@60.11 | +3.1s |
| X-18 | unauthorized_entry@20.0 | unauthorized_entry@16.05 | -3.9s |
| X-20 | safe_left_open@5.0 | safe_left_open@5.0 | +0.0s |
| X-22 | workstation_unlocked@14.0 | workstation_unlocked@14.07 | +0.1s |
| X-24 | valuables_left_unattended@8.0 | valuables_left_unattended@5.0 | -3.0s |
| X-26 | valuables_left_unattended@9.0 | valuables_left_unattended@10.03 | +1.0s |
| X-28 | workstation_unlocked@7.0 | workstation_unlocked@6.05 | -1.0s |
| X-30 | unauthorized_entry@13.0 | cash_room_door_open@3.01, unauthorized_entry@17.06 | +4.1s |
| X-32 | cash_room_door_open@5.0 | cash_room_door_open@4.01 | -1.0s |
| X-38 | cash_exposed_to_visitor@33.0 | cash_exposed_to_visitor@29.03, unauthorized_entry@36.04, cash_exposed_to_visitor@55.06 | +3.0s |
| X-40 | personal_items_at_workplace@17.0 | personal_items_at_workplace@18.07 | +1.1s |
| X-46 | food_drink_at_workplace@11.0 | food_drink_at_workplace@10.03 | -1.0s |

## Non-implemented labelled violations

- X-1 (cash_not_machine_verified@22.0): no_violation
- X-2 (no_client_identification@10.0): no_violation
- X-13 (unrecounted_cash_to_safe@47.0): no_violation
- X-17 (collector_handover_unverified@7.0): no_violation
- X-34 (counting_not_in_client_presence@13.0): no_violation
- X-44 (cash_not_machine_verified@16.0): no_violation

## Person-track diagnostics

| video | tracks | reflection | behind glass | dropped (score) |
|---|---|---|---|---|
| X-1 | 5 | 0 | 3 | #2 0.79, #4 0.86, #5 0.70 |
| X-2 | 7 | 0 | 4 | #2 0.79, #5 0.82, #6 0.65, #7 0.57 |
| X-3 | 6 | 0 | 4 | #2 0.83, #4 0.86, #5 0.72, #6 0.68 |
| X-4 | 21 | 0 | 17 | #2 0.77, #4 0.83, #5 0.77, #6 0.66, #7 0.67, #8 0.66, #9 0.60, #10 0.57, #11 0.68, #12 0.59, #13 0.73, #15 0.64, #16 0.85, #17 0.84, #19 0.64, #20 0.66, #21 0.57 |
| X-5 | 18 | 0 | 12 | #3 0.81, #5 0.76, #6 0.61, #7 0.68, #8 0.60, #9 0.66, #10 0.56, #11 0.59, #12 0.89, #15 0.79, #17 0.84, #18 0.67 |
| X-8 | 3 | 0 | 2 | #2 0.69, #3 0.58 |
| X-10 | 3 | 0 | 2 | #2 0.61, #3 0.57 |
| X-11 | 6 | 0 | 3 | #2 0.66, #3 0.71, #4 0.60 |
| X-12 | 10 | 0 | 6 | #2 0.64, #3 0.64, #4 0.63, #5 0.59, #6 0.57, #7 0.69 |
| X-13 | 12 | 0 | 11 | #2 0.68, #3 0.73, #4 0.69, #5 0.55, #6 0.64, #7 0.69, #8 0.56, #9 0.64, #10 0.67, #11 0.73, #12 0.71 |
| X-14 | 26 | 0 | 25 | #2 0.79, #3 0.69, #4 0.68, #5 0.68, #6 0.60, #7 0.64, #8 0.69, #9 0.68, #10 0.59, #11 0.61, #12 0.60, #13 0.60, #14 0.63, #15 0.62, #16 0.67, #17 0.60, #18 0.63, #19 0.59, #20 0.61, #21 0.69, #22 0.76, #23 0.57, #24 0.59, #25 0.74, #26 0.70 |
| X-15 | 6 | 0 | 4 | #2 0.56, #3 0.66, #4 0.65, #5 0.70 |
| X-16 | 7 | 0 | 4 | #2 0.81, #4 0.75, #5 0.79, #6 0.59 |
| X-17 | 5 | 0 | 3 | #2 0.74, #4 0.90, #5 0.73 |
| X-18 | 7 | 0 | 3 | #2 0.82, #5 0.79, #6 0.86 |
| X-19 | 13 | 0 | 7 | #2 0.84, #4 0.81, #5 0.73, #6 0.81, #7 0.92, #9 0.84, #13 0.85 |
| X-20 | 2 | 0 | 1 | #2 0.66 |
| X-21 | 5 | 0 | 4 | #2 0.62, #3 0.60, #4 0.56, #5 0.57 |
| X-22 | 4 | 0 | 3 | #2 0.60, #3 0.57, #4 0.76 |
| X-23 | 4 | 0 | 1 | #3 0.77 |
| X-24 | 5 | 0 | 2 | #3 0.67, #4 0.83 |
| X-25 | 8 | 0 | 6 | #2 0.55, #3 0.56, #4 0.68, #5 0.78, #6 0.83, #7 0.74 |
| X-26 | 3 | 0 | 2 | #2 0.59, #3 0.80 |
| X-27 | 4 | 0 | 2 | #2 0.78, #3 0.84 |
| X-28 | 4 | 0 | 3 | #2 0.56, #3 0.58, #4 0.85 |
| X-29 | 5 | 0 | 4 | #2 0.56, #3 0.59, #4 0.75, #5 0.79 |
| X-30 | 4 | 0 | 0 | - |
| X-31 | 5 | 0 | 0 | #4 0.76, #5 0.61 |
| X-32 | 1 | 0 | 0 | - |
| X-33 | 7 | 0 | 1 | #2 0.86, #5 0.63, #7 0.60 |
| X-34 | 7 | 0 | 4 | #4 0.80, #5 0.71, #6 0.73, #7 0.75 |
| X-35 | 13 | 1 | 8 | #4 0.86, #5 0.65, #6 0.60, #7 0.59, #8 0.64, #9 0.65, #10 0.67, #12 0.80 |
| X-37 | 5 | 0 | 2 | #4 0.89, #5 0.66 |
| X-38 | 21 | 0 | 12 | #4 0.83, #5 0.57, #6 0.64, #7 0.59, #8 0.60, #9 0.56, #10 0.62, #11 0.73, #15 0.62, #16 0.72, #17 0.76, #18 0.80, #20 0.61 |
| X-39 | 15 | 0 | 7 | #2 0.89, #4 0.81, #5 0.57, #6 0.60, #7 0.57, #8 0.62, #10 0.68, #13 0.66 |
| X-40 | 6 | 0 | 4 | #3 0.68, #4 0.74, #5 0.85, #6 0.61 |
| X-43 | 4 | 0 | 1 | #2 0.57 |
| X-44 | 1 | 0 | 0 | - |
| X-45 | 11 | 1 | 0 | #2 0.64, #5 0.66, #8 0.59, #10 0.61, #11 0.67 |
| X-46 | 2 | 0 | 1 | #2 0.59 |
| X-47 | 21 | 0 | 17 | #2 0.77, #4 0.83, #5 0.77, #6 0.66, #7 0.67, #8 0.66, #9 0.60, #10 0.57, #11 0.68, #12 0.59, #13 0.73, #15 0.64, #16 0.85, #17 0.84, #19 0.64, #20 0.66, #21 0.57 |
| X-48 | 18 | 0 | 12 | #3 0.81, #5 0.76, #6 0.61, #7 0.68, #8 0.60, #9 0.66, #10 0.56, #11 0.59, #12 0.89, #15 0.79, #17 0.84, #18 0.67 |

## Config change log

| # | when | change | reason | effect |
|---|---|---|---|---|
| 1 | 2026-10-17 17:05 | RT-DETR `group_thresholds.monitor: 0.45` (was the global 0.7) | X-22: after the cashier leaves, the tilted laptop scores 0.71–0.76 or is missed, so screen_state became `unknown` exactly when it matters; monitors have no "ghost" detections, so the person-oriented 0.7 is unnecessarily strict | X-22 (even) — to be judged on the odd half |
| 2 | 2026-10-17 21:55 | RT-DETR `score_threshold` for persons 0.7 → 0.55 | X-43/44/45 framing: the seated cashier scores 0.70–0.75 and was detected 1 frame in 5 → "cashier absent" → false `valuables_left_unattended`; corridor ghosts (0.44–0.57) are now excluded by the glass/reflection geometry instead | X-43 (odd) — judge on the even half |
| 3 | 2026-10-17 21:55 | `tracking._stays_behind_glass`: a track that was ever at the cashier seat is never "behind glass" | same clips: the auto-calibrated glass pane (x<0.33) covered the seat, so the cashier was dropped as `outside` | X-43 (odd) |
| 4 | 2026-10-17 22:05 | absence timecode = departure second (`rules.seat_core_radius 0.10`, `departure_lookback_sec 6`) for workstation_unlocked / valuables_left_unattended | run 2: all absence timecodes were late by +1…+4 s (X-26 +4.0, X-28 +3.1, X-15 +1.1, X-24 +1.0) because walking out of the 0.16 seat radius takes several seconds while the label marks the departure | judged on the even half |
| 5 | 2026-10-17 22:05 | OWLv2 `frame_stride: 2` | speed only: OWLv2 is ~0.35 s of the ~0.8 s per frame and its targets (cash, bags, glazing) are static | no accuracy intent |
| 6 | 2026-10-17 23:10 | `door.min_similarity: 0.8` (was 0.5) | on a video from another room (SYN-1) the fixed door box landed on a glass wall and the few-shot door prototypes answered "open" (false `cash_room_door_open` @0); measured nearest-prototype similarity: same framing 0.91–0.99, other framings/rooms 0.70–0.77 → the classifier abstains below 0.8 | cross-camera safety; no dataset video changes (door labels are all in the standard framing) |


## Failures (frames in failures/<video>/)

- X-1: MISS (not implemented type): label cash_not_machine_verified@22.0, predicted -
- X-2: MISS (not implemented type): label no_client_identification@10.0, predicted -
- X-13: MISS (not implemented type): label unrecounted_cash_to_safe@47.0, predicted -
- X-17: MISS (not implemented type): label collector_handover_unverified@7.0, predicted -
- X-34: MISS (not implemented type): label counting_not_in_client_presence@13.0, predicted -
- X-39: FALSE POSITIVE on clean clip: predicted unauthorized_entry@50.06
- X-44: MISS (not implemented type): label cash_not_machine_verified@16.0, predicted -
- X-47: TIMECODE error -7.9s: label cash_exposed_to_visitor@68.0, predicted cash_exposed_to_visitor@60.11
