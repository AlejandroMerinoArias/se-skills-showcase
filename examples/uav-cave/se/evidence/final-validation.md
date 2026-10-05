# Final validation — UAV cave mission

- **Code:** branch `i4-mission` at the commit recording this file; the sim runs below ran on the build of
  800c81c (the later commits change only sim scoring, SE records and test annotations).
- **Results:** `build_results/final_junit.xml` = unit tests (`tools/run_tests.sh`, 255 tests, 0 failures) merged
  with the three final sim runs (353 test cases, 0 failures).

## Final sim runs (2026-10-05)

| Run | Command | Outcome | Sim tests |
|---|---|---|---|
| 20261005-164436 nominal | `run_mission.sh --timeout-min 33 --inject-lanterns -1` | four real lanterns, last at 1133 s; back at the entrance (HOLD) at 1511 s; coverage 92.9 %; 8327 of 8328 depth images inserted, none failed after the first; map files written at HOLD and after SIGINT | 38 passed, 10 skipped (failure-run tests) |
| 20261005-163833 injected lanterns | `--timeout-min 15 --inject-lanterns 150` | four lanterns injected at 150 s, RETURN, HOLD at 243 s | 31 passed, 17 skipped |
| 20261005-163355 stall | `--timeout-min 10 --stall-after 60 --tests test_i2_failure` | `MISSION_FAILED ... reason=no movement for 120 s` at 191 s; lantern and map files written | 8 passed, 1 skipped |

Times are seconds after `ENTRANCE_REACHED`.

## CONOPS use cases

1. **Launch** — every run above starts the whole system with one command (`tools/run_mission.sh` → `ros2 launch
   cave_bringup mission.launch.py`); the launch file now also starts the simulator bridge with respawn.
2. **Approach** — `ENTRANCE_REACHED` logged once with its timestamp in all three runs at ⟨x, y, z⟩
   (`test_i1_mission.py`).
3. **Explore and detect** — nominal run: exploration from onboard sensing only (no-truth-source guard
   `test_no_truth_sources.py`), voxel map built from depth images, the four cave lanterns reported within 2 m and
   the start lantern never reported (`test_i3_lanterns.py`, `test_i4_mission.py`).
4. **Return** — nominal and injected-lantern runs: RETURN after the fourth lantern, hover at the entrance;
   nominal run within 1800 s (`test_i4_mission.py::test_four_lanterns_reported_and_back_at_the_entrance_within_1800_s`).
5. **Outputs** — lantern file and map files (`cave_map.bt`, `cave_map.ply`) written at completion and after SIGINT
   (nominal, injected) and on failure (stall run) (`test_i1_mission.py`, `test_i2_failure.py`).
6. **Hand-over** — `README.md` (Ubuntu 24.04 / ROS 2 Jazzy install and launch steps, WSL clock note) and
   `docs/documentation.md` (packages, nodes, external code, results) brought up to the delivered system.

The 2-of-3 acceptance requirement (SYS-P-005) rests on acceptance series 3 (`I5-acceptance-3.md`); the nominal
run here is a fourth full mission on the final build and met every criterion.

## Strict gate

`se_trace.py se --tests . --results build_results/final_junit.xml --strict` exits 0: no unannotated tests, no
failing or unrun linked tests, no unverified requirement. Matrix: 71 PASS, 24 EVIDENCE, 8 NESTED (parents verified
through their verified children), 2 retired (SYS-F-012, ITEM-D-045).

Set to verified at this gate, their linked tests passing in `final_junit.xml`: ITEM-D-017, ITEM-D-026, ITEM-D-028,
ITEM-D-037, ITEM-D-044 (changed in I5 under Q-41), ITEM-D-053, ITEM-D-054, SYS-F-029.

## Defects found during final validation

| Found in | Defect | Fix |
|---|---|---|
| acceptance runs 20261004-033151, -022644 | set-point acceleration 4.016-4.042 m/s² at straight-to-arc joins; sim tests still held I1 limits | streamer clamps to a_max; sim tests brought to the requirements (ed27f4c) |
| E-38 / E-51 | `/true_pose` stamps rewound every 32 s: WSL clock stepped by systemd-timesyncd | timesyncd disabled; README note (dbdcdc9) |
| run 20261004-143626 | UAV left the mouth and explored the outdoor valley goal by goal | D-53 homing to the entrance inside the outdoor zone (Q-44, f3076e9) |
| run 20261004-151458 | simulator bridge died at start; run stuck in WAIT_SENSORS | launch starts the bridge with respawn (506be97); no sensors for 120 s is a failed mission (Q-45, 9baf32c) |
| runs 20261004-155028, 20261005-151031, -155634 | full-cave final map write did not finish before the run ended; pruning slowed insertion | mapper given 40 s after SIGINT, run_mission waits 60 s, TF buffer 60 s, depth queue 100 (1319934, b1df38d reverted, 800c81c) |
| acceptance run 20261004-022644, run 20261005-155634 | 0.5 m proximity check failed on a small non-colliding object by the mouth (no contact) | check leaves out detached clusters of at most 30 cells (Q-46, 8635ce1) |

## Open items

All 93 items in `open-items.yaml` are closed; none is open or carried as accepted risk.

## Carried risks

- **Timing margin:** returns at 1511-1695 s across the final and acceptance runs, against 1800 s.
- **Coverage margin:** 91-94 % against 90 %.
- **End-of-run map write:** the HOLD write of a full cave took 32 s in the nominal run and the after-SIGINT write
  about 30 s; the run waits up to 60 s, the mapper is killed after 40 s.
- **CRIT-A review:** developer review only in I5 (Q-43).
