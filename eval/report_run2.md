# Acceptance report

Generated 2026-10-17 21:41 — 42 videos via http://localhost:8080; tuned half: even

| # | Criterion | Result | Detail |
|---|---|---|---|
| 1 | 42/42 done, 0 failed, 0 timeouts | FAIL | done 41/42; failed/timeout: X-14:timeout |
| 2-4 | schema, JPEG, evidence ±5s, Russian description with clause | PASS | all responses valid |
| 5 | 401 without / with wrong X-API-Key | PASS | no key=401, wrong key=401, wrong key GET=401 |
| 6 | max processing ≤ 120s | FAIL | p50 27s, max 331s (X-14), X-47 98s |
| 7 | burst of 5 longest within 300s each | FAIL | X-14: done in 224s (ok); X-39: timeout in 330s (FAIL); X-4: timeout in 332s (FAIL); X-47: timeout in 332s (FAIL); X-5: timeout in 332s (FAIL) |
| 8 | recall on implemented types ≥ 12/14 | FAIL | 3/4 (judged set), all: 12/16 |
| 9 | clean FP ≤ 2, visitor-type FP = 0 | FAIL | FP: X-39, X-43; visitor-type: X-39 |
| 10 | must-pass list | FAIL | missed: X-32; false: - |
| 11 | timecode ≥70% within ±2s and ≥90% within ±5s | FAIL | ±2s 50%, ±5s 92% (all); judged: ±2s 67%, ±5s 67% |
| 12 | type accuracy ≥ 80% | PASS | type 100%, family 100% (all); judged type 100% |
| 13 | non-implemented violations listed | PASS | 6 listed below |
| 14 | track diagnostics logged per video | PASS | missing for: - |
| 15 | no confident mid-room track dropped on X-4/X-18/X-30 | PASS | ok |

## Metrics

### All videos

- videos: 42; implemented-type violations: 16, detected: 12 (recall 12/16)
- clean videos: 20; false positives: 2 (X-39, X-43); visitor-type FP: X-39
- timecode within ±2s: 50%, within ±5s: 92%
- type accuracy: 100%, family accuracy: 100%

| video | label | predicted | signed timecode error |
|---|---|---|---|
| X-4 | cash_exposed_to_visitor@57.0 | cash_exposed_to_visitor@60.11 | +3.1s |
| X-11 | workstation_unlocked@18.0 | workstation_unlocked@18.07 | +0.1s |
| X-15 | valuables_left_unattended@15.0 | valuables_left_unattended@16.05 | +1.1s |
| X-18 | unauthorized_entry@20.0 | - |  |
| X-20 | safe_left_open@5.0 | safe_left_open@5.0 | +0.0s |
| X-22 | workstation_unlocked@14.0 | workstation_unlocked@14.07 | +0.1s |
| X-24 | valuables_left_unattended@8.0 | valuables_left_unattended@9.0 | +1.0s |
| X-26 | valuables_left_unattended@9.0 | valuables_left_unattended@13.04 | +4.0s |
| X-28 | workstation_unlocked@7.0 | workstation_unlocked@10.08 | +3.1s |
| X-30 | unauthorized_entry@13.0 | - |  |
| X-32 | cash_room_door_open@5.0 | - |  |
| X-33 | cash_room_door_open@6.0 | - |  |
| X-38 | cash_exposed_to_visitor@33.0 | cash_exposed_to_visitor@29.03, cash_exposed_to_visitor@55.06 | -4.0s |
| X-40 | personal_items_at_workplace@17.0 | personal_items_at_workplace@19.08 | +2.1s |
| X-46 | food_drink_at_workplace@11.0 | food_drink_at_workplace@10.03 | -1.0s |
| X-47 | cash_exposed_to_visitor@68.0 | cash_exposed_to_visitor@60.11 | -7.9s |

### Odd video numbers

- videos: 21; implemented-type violations: 4, detected: 3 (recall 3/4)
- clean videos: 14; false positives: 2 (X-39, X-43); visitor-type FP: X-39
- timecode within ±2s: 67%, within ±5s: 67%
- type accuracy: 100%, family accuracy: 100%

| video | label | predicted | signed timecode error |
|---|---|---|---|
| X-11 | workstation_unlocked@18.0 | workstation_unlocked@18.07 | +0.1s |
| X-15 | valuables_left_unattended@15.0 | valuables_left_unattended@16.05 | +1.1s |
| X-33 | cash_room_door_open@6.0 | - |  |
| X-47 | cash_exposed_to_visitor@68.0 | cash_exposed_to_visitor@60.11 | -7.9s |

### Even video numbers

- videos: 21; implemented-type violations: 12, detected: 9 (recall 9/12)
- clean videos: 6; false positives: 0 (-); visitor-type FP: -
- timecode within ±2s: 44%, within ±5s: 100%
- type accuracy: 100%, family accuracy: 100%

| video | label | predicted | signed timecode error |
|---|---|---|---|
| X-4 | cash_exposed_to_visitor@57.0 | cash_exposed_to_visitor@60.11 | +3.1s |
| X-18 | unauthorized_entry@20.0 | - |  |
| X-20 | safe_left_open@5.0 | safe_left_open@5.0 | +0.0s |
| X-22 | workstation_unlocked@14.0 | workstation_unlocked@14.07 | +0.1s |
| X-24 | valuables_left_unattended@8.0 | valuables_left_unattended@9.0 | +1.0s |
| X-26 | valuables_left_unattended@9.0 | valuables_left_unattended@13.04 | +4.0s |
| X-28 | workstation_unlocked@7.0 | workstation_unlocked@10.08 | +3.1s |
| X-30 | unauthorized_entry@13.0 | - |  |
| X-32 | cash_room_door_open@5.0 | - |  |
| X-38 | cash_exposed_to_visitor@33.0 | cash_exposed_to_visitor@29.03, cash_exposed_to_visitor@55.06 | -4.0s |
| X-40 | personal_items_at_workplace@17.0 | personal_items_at_workplace@19.08 | +2.1s |
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
| X-1 | 5 | 0 | 3 | #2 0.79, #4 0.86, #5 0.76 |
| X-2 | 5 | 0 | 3 | #2 0.79, #4 0.83, #5 0.70 |
| X-3 | 6 | 0 | 4 | #2 0.83, #4 0.86, #5 0.72, #6 0.76 |
| X-4 | 15 | 0 | 11 | #2 0.80, #4 0.83, #5 0.77, #6 0.74, #7 0.73, #8 0.75, #10 0.92, #11 0.79, #13 0.88, #14 0.72, #15 0.82 |
| X-5 | 22 | 0 | 16 | #3 0.81, #5 0.79, #6 0.83, #7 0.83, #8 0.77, #9 0.73, #10 0.84, #11 0.81, #12 0.81, #13 0.75, #14 0.75, #15 0.79, #16 0.82, #17 0.89, #20 0.79, #22 0.84 |
| X-8 | 3 | 0 | 1 | #2 0.81 |
| X-10 | 1 | 0 | 0 | - |
| X-11 | 5 | 0 | 2 | #2 0.72, #3 0.71 |
| X-12 | 4 | 0 | 1 | #2 0.72 |
| X-13 | 16 | 0 | 14 | #2 0.77, #3 0.81, #4 0.73, #5 0.74, #6 0.70, #7 0.76, #8 0.78, #9 0.83, #10 0.79, #11 0.73, #12 0.82, #13 0.77, #14 0.73, #15 0.71 |
| X-14 | 16 | 0 | 15 | #2 0.79, #3 0.73, #4 0.70, #5 0.75, #6 0.76, #7 0.74, #8 0.74, #9 0.76, #10 0.76, #11 0.70, #12 0.76, #13 0.76, #14 0.77, #15 0.78, #16 0.79 |
| X-15 | 4 | 0 | 2 | #2 0.76, #3 0.72 |
| X-16 | 7 | 0 | 4 | #2 0.81, #4 0.75, #5 0.81, #6 0.88 |
| X-17 | 5 | 0 | 3 | #2 0.74, #4 0.90, #5 0.73 |
| X-18 | 7 | 0 | 3 | #2 0.82, #5 0.82, #6 0.86 |
| X-19 | 15 | 0 | 10 | #2 0.84, #4 0.83, #5 0.84, #6 0.73, #7 0.83, #8 0.81, #9 0.92, #10 0.78, #12 0.84, #15 0.85 |
| X-20 | 2 | 0 | 1 | #2 0.75 |
| X-21 | 1 | 0 | 0 | - |
| X-22 | 2 | 0 | 1 | #2 0.76 |
| X-23 | 4 | 0 | 2 | #2 0.87, #3 0.77 |
| X-24 | 4 | 0 | 1 | #3 0.83 |
| X-25 | 8 | 0 | 4 | #4 0.73, #5 0.78, #6 0.83, #7 0.74 |
| X-26 | 3 | 0 | 1 | #3 0.80 |
| X-27 | 4 | 0 | 2 | #2 0.78, #3 0.84 |
| X-28 | 2 | 0 | 1 | #2 0.85 |
| X-29 | 3 | 0 | 2 | #2 0.75, #3 0.79 |
| X-30 | 3 | 0 | 1 | #3 0.93 |
| X-31 | 3 | 0 | 2 | #2 0.70, #3 0.76 |
| X-32 | 1 | 0 | 0 | - |
| X-33 | 4 | 0 | 1 | #1 0.86, #2 0.84 |
| X-34 | 7 | 0 | 4 | #4 0.80, #5 0.71, #6 0.73, #7 0.75 |
| X-35 | 10 | 0 | 6 | #4 0.86, #5 0.75, #6 0.70, #7 0.74, #8 0.93, #9 0.80 |
| X-37 | 4 | 0 | 1 | #4 0.89 |
| X-38 | 15 | 0 | 7 | #4 0.83, #5 0.77, #9 0.79, #10 0.73, #11 0.74, #12 0.76, #13 0.80 |
| X-39 | 12 | 0 | 5 | #2 0.89, #4 0.81, #6 0.76, #9 0.71, #10 0.71, #11 0.71 |
| X-40 | 4 | 0 | 2 | #3 0.76, #4 0.85 |
| X-43 | 6 | 0 | 5 | #2 0.70, #3 0.75, #4 0.72, #5 0.73, #6 0.70 |
| X-44 | 1 | 0 | 0 | - |
| X-45 | 3 | 0 | 2 | #2 0.81, #3 0.70 |
| X-46 | 1 | 0 | 0 | - |
| X-47 | 15 | 0 | 11 | #2 0.80, #4 0.83, #5 0.77, #6 0.74, #7 0.73, #8 0.75, #10 0.92, #11 0.79, #13 0.88, #14 0.72, #15 0.82 |
| X-48 | 22 | 0 | 16 | #3 0.81, #5 0.79, #6 0.83, #7 0.83, #8 0.77, #9 0.73, #10 0.84, #11 0.81, #12 0.81, #13 0.75, #14 0.75, #15 0.79, #16 0.82, #17 0.89, #20 0.79, #22 0.84 |

## Config change log

| # | when | change | reason | effect |
|---|---|---|---|---|
| 1 | 2026-10-17 17:05 | RT-DETR `group_thresholds.monitor: 0.45` (was the global 0.7) | X-22: after the cashier leaves, the tilted laptop scores 0.71–0.76 or is missed, so screen_state became `unknown` exactly when it matters; monitors have no "ghost" detections, so the person-oriented 0.7 is unnecessarily strict | X-22 (even) — to be judged on the odd half |


## Failures (frames in failures/<video>/)

- X-1: MISS (not implemented type): label cash_not_machine_verified@22.0, predicted -
- X-2: MISS (not implemented type): label no_client_identification@10.0, predicted -
- X-13: MISS (not implemented type): label unrecounted_cash_to_safe@47.0, predicted -
- X-17: MISS (not implemented type): label collector_handover_unverified@7.0, predicted -
- X-18: MISS (implemented type): label unauthorized_entry@20.0, predicted -
- X-30: MISS (implemented type): label unauthorized_entry@13.0, predicted -
- X-32: MISS (implemented type): label cash_room_door_open@5.0, predicted -
- X-33: MISS (implemented type): label cash_room_door_open@6.0, predicted -
- X-34: MISS (not implemented type): label counting_not_in_client_presence@13.0, predicted -
- X-39: FALSE POSITIVE on clean clip: predicted unauthorized_entry@35.04, unauthorized_entry@50.06
- X-43: FALSE POSITIVE on clean clip: predicted valuables_left_unattended@19.05
- X-44: MISS (not implemented type): label cash_not_machine_verified@16.0, predicted -
- X-47: TIMECODE error -7.9s: label cash_exposed_to_visitor@68.0, predicted cash_exposed_to_visitor@60.11
