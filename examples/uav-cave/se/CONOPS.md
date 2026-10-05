# CONOPS — UAV Cave Mission

## Purpose

A simulated quadrotor autonomously searches a cave for four lanterns, reports where they are,
builds a 3D voxel/mesh model of the cave, and returns to the cave entrance. The mission is
judged in a provided Unity simulation (see `BRIEF.md` §5): all four lanterns within 2 m,
entrance reached, map delivered, return to entrance, and at most 30 min from first reaching
the entrance to being back with all four lanterns reported.

## Use cases

1. **Launch.** The operator starts the whole system (simulation, bridge, controller, mission
   stack) with one launch command on the customer's Ubuntu machine.
2. **Approach.** The UAV takes off at the start area (where a reference lantern stands) and
   flies a predefined waypoint route to a cave-entrance point chosen by the team. The instant
   it first reaches that point is published and logged. The 30-minute mission clock starts then.
3. **Explore and detect.** Inside the cave the UAV has no prior knowledge of the cave or the lanterns.
   It chooses where to go from its own sensing only, builds a voxel map from depth images, and
   detects and localises lanterns from camera data.
4. **Return.** Once four distinct cave lanterns are reported, the UAV flies back to the entrance
   point and hovers (no landing).
5. **Outputs.** Every run, whether it succeeds or fails, ends with a lantern-poses file and a
   cave-representation file on disk.
6. **Hand-over.** The customer receives source code, a README with step-by-step install/launch
   instructions and the Ubuntu version, and a 4–6 page document describing each package and node
   and any external code used.

## Environment

- Unity simulation binary (`ros2_ws/src/unity_sim/⟨redacted⟩`): a wide open area with the
  UAV start point and a cave somewhere in the map. The binary, the cave and the state-estimate
  corruption must not be changed.
- Development and test host: Windows 11 + WSL2 Ubuntu 24.04, ROS 2 Jazzy, workspace `~/ws_k7`; Unity must render on the GPU (`GALLIUM_DRIVER=d3d12`).
- The system runs on wall-clock time (no `/clock`); cameras 320x240 (depth/semantic 5 Hz, RGB 10 Hz), state 50 Hz.
- Position comes from a corrupted state estimate (`state_estimate_corruptor_node`: white noise
  5 mm white noise; its drift branch never runs, see evidence/E-04.md). The true pose exists in the simulation but must not be used by
  the mission stack. It may be used only by offline test/scoring tools.
- The cave is dark and confined, so collisions end a run in practice.

## Interfaces

Provided (from the repository):

| Direction | Topic / artefact | Type | Notes |
|---|---|---|---|
| sim → stack | `/current_state_est` | `nav_msgs/Odometry` | corrupted state; frame `world`, child `body` |
| sim → stack | `/pose_est`, `/twist_est` | `PoseStamped`, `TwistStamped` | corrupted |
| sim → stack | `/realsense/depth/image`, `/realsense/depth/camera_info` | `Image`, `CameraInfo` | depth camera |
| sim → stack | `/realsense/rgb/{left,right}_image_raw` + info | `Image`, `CameraInfo` | stereo RGB |
| sim → stack | `/Quadrotor/Sensors/SemanticCamera/image_raw` | `Image` rgb8 | lanterns = (255,235,4) on black, 5 Hz |
| sim → stack | `/interpolate_imu/imu` | `Imu` | |
| stack → controller | desired state | `trajectory_msgs/MultiDOFJointTrajectory` | controller is a prebuilt `.so` wrapper |
| controller → sim | rotor speeds | `mav_msgs/Actuators` | via `w_to_unity` |
| forbidden to stack | `/true_pose`, `/true_twist`, TF from `/Quadrotor/TrueState` | | truth, scoring only |

Delivered by the system:

- Entrance-reached event (topic and log line with timestamp).
- Lantern positions: published, and written to a file at mission end.
- Cave representation: published, and written to a file at mission end.
- One top-level launch file.
