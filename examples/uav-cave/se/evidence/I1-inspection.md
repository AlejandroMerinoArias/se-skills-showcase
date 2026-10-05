# I1 — Inspection and demonstration evidence
nSigned off by the customer on 2026-09-28 (I1 verification gate).

Covers the I1 requirements whose method of verification is inspection or demonstration:
SYS-C-003, SYS-C-005, SYS-F-011, ITEM-D-001, ITEM-D-010, ITEM-D-011. Code state: master @ da1eb9d.
Runs: `wsl.exe bash tools/run_mission.sh --timeout-min 10`, two consecutive runs after the review fix
pass (16/16 simulation tests each); last run `build_results/runs/20260928-221006`.

## SYS-C-003 — simulator, cave and state-estimate corruption unmodified (inspection)
| Check | Command | Result |
|---|---|---|
| Unity binary and data | `git diff --stat 43f40e9 HEAD -- ros2_ws/src/unity_sim` | 0 lines (unchanged since the course scaffold) |
| Unity launcher blob | `git hash-object ros2_ws/src/unity_sim/⟨redacted⟩` vs `git rev-parse 43f40e9:…` | identical `55eade3c…` |
| Corruptor source | `git hash-object …/state_estimate_corruptor_node.cpp` vs first commit `ce7f29a` | identical `610ee0be…` |
| Bridge sources and launch files | `git diff --stat ce7f29a HEAD -- ros2_ws/src/simulation/src ros2_ws/src/simulation/launch` | 0 lines |
| Controller | `git diff --stat 43f40e9 HEAD -- ros2_ws/src/controller_pkg` | 0 lines |
| Only change in `simulation` | `git diff ce7f29a HEAD -- ros2_ws/src/simulation` | +6 lines in `CMakeLists.txt`: install rules copying `unity_sim` next to the executables |
| Corruptor parameters | `cave_bringup/launch/mission.launch.py` | `drift_rw_factor 0.03`, `pos_white_sig 0.005`, `jump_seconds 20.0`, the same as `simulation.launch.py` |

Result: PASS.

## SYS-C-005 — builds and runs on Ubuntu 24.04 with ROS 2 Jazzy (demonstration)
- `wsl.exe bash tools/run_tests.sh`: `Summary: 7 packages finished`, 41 unit tests, 0 failures (Ubuntu 24.04.3 LTS, `/opt/ros/jazzy`, E-02).
- `tools/run_mission.sh`: the full mission (take-off → entrance → HOLD) completed in 4 consecutive runs, with the last two at 16/16 simulation tests.

Result: PASS on Ubuntu 24.04 (WSL2) with Jazzy. Limit: native (non-WSL) Ubuntu 24.04 has not been run.

## SYS-F-011 — the current voxel grid is published while the mission runs (demonstration)
- Topic `/perception/octomap` (`octomap_msgs/Octomap`, binary, transient local), published every 5 s (D-12).
- Last run: 16 messages over the mission, largest gap 6.4 s, last message 1.89 MB.
- `tools/sim_tests/test_i1_mission.py::test_voxel_map_published_while_running` PASS (at least 10 messages, gaps ≤ 7.5 s).

Result: PASS.

## ITEM-D-001 — camera transforms hang from `body`; no truth-attached transform is started (inspection)
- `cave_bringup/launch_helpers.py`: `BODY_FRAME = "body"`. `static_tf_arguments` sets `--frame-id body` for the four camera frames (`Quadrotor/Sensors/{DepthCamera,SemanticCamera,RGBCameraLeft,RGBCameraRight}`), with the optical rotation roll = −π/2, yaw = −π/2.
- `mission.launch.py` includes only `simulation/unity_ros.launch.py`. The `/true_body`-parented static transforms in the provided `simulation.launch.py` are not started.
- Unit test `test_camera_transforms_hang_from_estimated_body_frame` PASS.
- The code-quality review independently confirmed the optical-frame algebra (z forward, x right, y down).

Result: PASS.

## ITEM-D-010 — mission, planning and perception use only the corrupted estimate (inspection)
- `mission_node.py:49` and `trajectory_node.py:53` subscribe to `/current_state_est` only.
- `cave_mapper_node.cpp` takes the camera pose from TF `world → camera` (`lookupTransform`). The `world → body` link comes from the corruptor, and `body → camera` from ITEM-D-001.
- `grep -rnE "/true_pose|/true_twist|TrueState|true_body" ros2_ws/src/cave_*` (non-test sources) finds 0 hits. The guard test `test_no_cave_package_source_reads_a_truth_topic_or_frame` PASS.
- Truth is read only by `tools/sim_tests/monitor.py`, for scoring.

Result: PASS.

## ITEM-D-011 — OctoMap resolution 0.25 m (inspection)
- `mission.launch.py` passes `resolution: 0.25`; the node default is also 0.25.
- Launch log of the last run: `cave_mapper: resolution 0.25 m, max range 20.0 m, stride 4`.

Result: PASS (and SYS-P-003's 0.5 m threshold is met).
