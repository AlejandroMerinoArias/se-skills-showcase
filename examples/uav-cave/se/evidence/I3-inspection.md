# I3 — Inspection and demonstration evidence

Covers the I3 requirements verified by inspection or demonstration: SYS-I-001 and SYS-F-010. It also summarises the
simulation evidence behind the test-verified I3 requirements. Code state: branch `i3-lanterns`.

Runs: `wsl.exe bash tools/run_mission.sh --timeout-min 15 --inject-lanterns -1 --tests "test_i3 or test_i2_failure or
surface or bump"`. These are real lantern detection runs with no stand-in lanterns. Two consecutive fully green
runs, 20260929-222735 and 20260929-224254, each passed 9/9 simulation tests.

Signed off by the customer on 2026-09-29 (I3 verification gate).

## SYS-I-001 — lantern positions as x, y, z in metres, world frame of the state estimate, one line per lantern (inspection)
`lanterns.csv` of run 20260929-224254:

```
id,x,y,z
0,-598.818,-8.484,4.533
1,-1044.103,-157.374,-37.184
```

The file has one header line, then one line per reported lantern: id, then x, y, z in metres with three
decimals. The frame is `world` of the corrupted state estimate. Positions come from TF world→camera, and the
world→body link comes from the estimate (ITEM-D-010). The mission node writes the file atomically every 8 s, at
HOLD, on a declared failure and at shutdown (D-09). The id column and header line are additions to the x, y, z the
requirement asks for.

Result: PASS.

## SYS-F-010 — current lantern estimates published on a ROS topic while the mission runs (demonstration)
`/perception/lanterns` carries a `geometry_msgs/PoseArray` in frame `world`, holding the reported lanterns in
order of first report (D-22).

| Run | Messages | Largest gap |
|---|---|---|
| 20260929-222735 | 902 | 1.32 s |
| 20260929-224254 | 902 | 1.01 s |

The simulation test `test_lanterns_published_at_least_once_per_second` (ITEM-D-030) passed in both runs.

Result: PASS.

## Detection and localisation in the two verifying runs (test-verified requirements, for context)
| Lantern | 20260929-222735 | 20260929-224254 | Truth (E-10 (not published)) |
|---|---|---|---|
| Lantern (3), gallery | ⟨x, y, z⟩: **0.14 m** | ⟨x, y, z⟩: **0.72 m** | ⟨x, y, z⟩ |
| Lantern (1), far tunnel system | ⟨x, y, z⟩: **0.30 m** | ⟨x, y, z⟩: **0.37 m** | ⟨x, y, z⟩ |

Neither run reported the start lantern, a duplicate or a false lantern. SYS-S-001 was judged on the surfaces the
camera mapped, from the entrance on, and SYS-S-004 on recovery after bumps. Both passed.

## Limits and carried risks (I4)
- Across the 9 long runs since D-25, 4 ended early or failed:
  - a stall on the approach (fixed);
  - a false lantern (fixed);
  - a corner trap beside the mouth (escape-zone limit, D-17);
  - the UAV left the cave through a side opening at y ⟨…⟩ m and got stuck outside (run 20260929-221536).
- These are mission-reliability risks for SYS-P-002/SYS-P-005 in I4.
- Only Lantern (3) and Lantern (1) have been found by exploration so far. Lantern (2) and Lantern are unverified,
  pending E-18 and the D-24 vertical-shaft question.
- On the approach, a small object that the depth camera sees but that has no collider drifts across the route. The
  approach relies on E-03 and on the tracking-error criterion.
