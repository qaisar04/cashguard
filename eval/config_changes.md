| # | when | change | reason | effect |
|---|---|---|---|---|
| 1 | 2026-10-17 17:05 | RT-DETR `group_thresholds.monitor: 0.45` (was the global 0.7) | X-22: after the cashier leaves, the tilted laptop scores 0.71–0.76 or is missed, so screen_state became `unknown` exactly when it matters; monitors have no "ghost" detections, so the person-oriented 0.7 is unnecessarily strict | X-22 (even) — to be judged on the odd half |
