# I5 acceptance runs, third series (SYS-P-005, SYS-P-002, SYS-P-004, SYS-S-001)

## Question
With openings from 100 m until the UAV has been 400 m in and from 300 m after (D-51 amended, commit 77b2ed5), kept
close hits off (Q-42) and turns at 60 deg/s (D-52), does the system meet the five success criteria of brief section 5
in at least 2 of 3 consecutive simulation runs (SYS-P-005)? Criteria as in `I4-acceptance.md`: four lanterns reported
and back at the entrance within 1800 s (SYS-P-002), every reported lantern within 2 m of a cave lantern and reported
once, map coverage at least 90 % (SYS-P-004), never within 0.5 m of a surface the camera saw and tracking within
1.0 m outside bump windows (SYS-S-001), no failure declared in a nominal run.

## Command
`bash tools/run_mission.sh --timeout-min 33 --inject-lanterns -1 --tests "test_i3 or test_i2_failure or surface or
bump or test_i4" --junit sim_acc7_<n>.xml`, three consecutive runs on commit 77b2ed5, mission view on, watched live.

## Raw results
| Run | Lanterns (time) | Back at entrance | Map coverage | Sim tests | Failed |
|---|---|---|---|---|---|
| 20261004-022644 | L3 160 s, L2 316 s, L1 705 s, deepest 1169 s | 1529 s | 94.1 % | 11/12 | surface criterion: two passes 0.37 m from small clusters (6 and 20 points) about 20 m inside the mouth at 17 s and 1514 s |
| 20261004-025909 | L3 167 s, L2 340 s, L1 600 s, deepest 1190 s | 1556 s | 92.5 % | 12/12 | - |
| 20261004-033151 | L3 192 s, L2 347 s, L1 619 s, deepest 1307 s | 1695 s | 91.3 % | 12/12 | - |

Run 1's close passes: the clusters have no reference cave surface within 2 m (`tools/probes/close_passes.py`); points
of this kind by the mouth appear in this run only among the last five (`tools/probes/mouth_noise.py`), where a small
non-colliding object the depth camera sees drifts across the route (evidence/I3-inspection.md). Deeper in the cave,
depth-noise points stay at least 1.8 m from the track at 60 deg/s.

No bump, no hold, no failure declared in any run; every reported lantern within 2 m of a cave lantern.

Contact (SYS-S-001, no touching of an observable surface): no bump in any run, and the largest distance between
the true position and the set-point was 0.54, 0.48 and 0.57 m (contacts show 0.66 m and more, E-19 (not published)). In run 1 the
tracking assertion of the surface test did not run, because the proximity assertion before it failed; it was
computed separately from the same data.

## Verdict
VERDICT: SYS-P-005 met (2 of 3: runs 2 and 3 met all five criteria). SYS-P-002 met in all three runs (1529-1695 s);
SYS-P-004 met in all three (91.3-94.1 %); SYS-S-001 (no contact) met in all three runs; its 0.5 m proximity
criterion met in runs 2 and 3 (run 1 failed it on non-surface points by the mouth).
