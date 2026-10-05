# I2 — Inspection and demonstration evidence

Covers the I2 requirements whose method of verification is inspection or demonstration: SYS-C-002, SYS-C-009,
ITEM-D-015 and SYS-S-001. The code state is the `i2-exploration` branch after the I2 addendum and its review fixes
(commits up to `e78703e`).

Runs used:
- `wsl.exe bash tools/run_mission_twice.sh 2 --timeout-min 20`: nominal runs `build_results/runs/20260929-151351`
  and `20260929-151957`, 25/25 simulation tests each;
- `wsl.exe bash tools/run_mission.sh --timeout-min 15 --stall-after 60 --tests test_i2_failure`: stall run
  `20260929-150838`, 8/8.

The per-run numbers come from `tools/probes/i2_run_summary.py`, which reads the truth and the reference geometry for
scoring only.

Signed off by the customer on 2026-09-29 (I2 verification gate).

## SYS-C-002: after the entrance event, every flight goal except the entrance comes from data sensed this run (inspection)

| Check | Where | Finding |
|---|---|---|
| Paths flown after the entrance | `cave_mission/state_machine.py` | After APPROACH, `_pending` is set only in `on_explore_result`, which takes the planner's exploration path, and in `on_return_plan`, which takes the planner's path to `cfg.entrance`. The one exception is the flight-timeout hold: the one-point path at the current estimated position. |
| Where exploration goals come from | `cave_navigation/explorer.cpp` | Goals are the centres of frontier bins of the `NavMap`: free cells with an unknown neighbour, beyond the entrance plane, not under observed open sky. |
| What the map is built from | `cave_navigation/path_planner_node.cpp` | The `NavMap` is filled only from `/realsense/depth/image` via TF at the image stamp (world→body from the state estimate). Nothing is loaded from a file. |
| Configured coordinates | `path_planner_node.cpp:101-102`, `mission_node.py` | Only the entrance point E and `approach_from`, which is the last predefined route point before E and defines the entrance plane. The cave interior holds no coordinates. |
| Reading files | `grep open(/ifstream/load` in `cave_navigation`, `cave_mission` | The only file access is output writing (`outputs.py`, `nav_map.bt`, `navigation.csv`). |
| Test-only inputs | `tools/sim_tests/monitor.py` | The four stand-in lanterns are published by the scoring harness, not by the stack. I3 replaces them with detection. |

Supporting tests, all passing:
- `test_exploration_goals_lie_beyond_the_entrance_plane_inside_the_cave` (ITEM-D-013);
- `test_every_path_flown_in_explore_came_from_the_planner` (ITEM-D-014).

In the nominal runs the explorer produced 13 and 12 exploration goals and flew 170–178 m into the cave, a
region no predefined point describes.

Result: PASS.

## SYS-C-009 and ITEM-D-015: four separate ROS nodes in separate packages (inspection)

| Node (executable) | Package | Started by `mission.launch.py` (launch log of 20260929-151957) |
|---|---|---|
| `mission_node`: mission state machine | `cave_mission` | `[mission_node-9]: process started` |
| `cave_mapper`: depth → voxel map | `cave_perception` | `[cave_mapper-6]: process started` |
| `path_planner`: path planning (A*, frontier exploration) | `cave_navigation` | `[path_planner-8]: process started` |
| `trajectory_node`: trajectory planning (trapezoid profile) | `cave_planning` | `[trajectory_node-7]: process started` |

Each is its own process, and they talk only over ROS topics and services:
- `/planning/path`;
- `/navigation/explore` and `/navigation/plan_to`;
- `/perception/octomap`;
- `/mission/state`.

Result: PASS.

## SYS-S-001: the mission completes without touching the cave surface or terrain (demonstration)

| Run | Outcome | Closest approach of the true path to the reference cave surface | Max tracking error (contact detector E-08 fires above 1.0 m) |
|---|---|---|---|
| 20260929-151351 | HOLD at the entrance | 1.0 m | 0.30 m |
| 20260929-151957 | HOLD at the entrance | 1.25 m | 0.31 m |
| 20260929-150838 (stall) | FAILED as injected | 2.0 m | 0.31 m |

The simulation test `test_uav_never_came_within_half_a_metre_of_the_cave_surface` passed in both nominal runs. It
checks every fifth truth sample against the reference surface at 0.5 m, and the tracking error against 1.0 m.

Result: PASS for these runs.

Limits:
- The reference geometry (E-06) has the cave but no outside terrain; for the outside route, contact is covered by the
  tracking-error detector and by E-03 (9/9 flights clean).
- Two nominal runs: SYS-P-005's 2-of-3 acceptance runs with real lanterns are an I4 activity.
- The closest approach of 1.0 m is at the planner's clearance floor (ITEM-D-016). This is expected in narrow passages.
