# Architecture

## Sketch

ROS 2 Jazzy workspace (`ros2_ws/src`), built in WSL `~/ws_k7`. The provided packages (`simulation`,
`controller_pkg`, `mav_msgs`, `mav_planning_msgs`, `unity_sim`) are kept; the provided
`state_estimate_corruptor_node` and Unity binary stay unmodified (SYS-C-003).

| Module (package) | Responsibility |
|---|---|
| `simulation` (provided) | Unity binary, TCP bridge, state-estimate corruptor, rotor-command bridge. |
| `controller_pkg` (provided) | Geometric position controller: desired state → rotor speeds. |
| `cave_bringup` | The single top-level launch file, parameters, TF tree rooted at the *estimated* body pose. |
| `cave_mission` | Mission state machine: take-off, waypoint approach, entrance event, explore, return, hover; run-end handling. |
| `cave_perception` | Depth image → point cloud → global voxel map; periodic and final map file output. |
| `cave_lanterns` | Lantern detection in camera images, 3D localisation, de-duplication, publishing (the lantern file is written by `cave_mission`, D-09). |
| `cave_exploration` | Chooses the next exploration goal from the voxel map (no prior cave knowledge). |
| `cave_planning` | Path planner (collision-free path in the voxel map) and trajectory planner (smooth time-parametrised trajectory for the controller). |
| `tools/` | `run_tests.sh`, `run_mission.sh`, offline scoring (the only place truth data may be read). |
| docs | `README.md`, `docs/documentation.md`. |

### Interfaces between modules

| From → To | Interface |
|---|---|
| corruptor → all | `/current_state_est` (`nav_msgs/Odometry`), TF `world → body` |
| perception → exploration, planning | voxel map topic (OctoMap binary) |
| lanterns → mission | lantern list topic (positions, count) |
| mission → exploration | "explore" / "stop" mode; exploration → mission: goal or "no frontier" |
| mission/exploration → path planner | goal pose request (service or action) |
| path planner → trajectory planner | path (`nav_msgs/Path`) |
| trajectory planner → controller | `trajectory_msgs/MultiDOFJointTrajectory` desired state |
| mission → log / topic | entrance-reached event |

## Decisions

### D-01 — Return immediately after the fourth lantern

**Decision:** When the fourth distinct cave lantern is reported, the mission switches straight to
the return leg; it does not continue exploring to improve the map.

**Rationale:** Brief 1.1 asks for the lanterns "as fast as possible", and 5.5 caps the mission
at 30 min. Brief 5.3 leaves the map-quality judgement to us. SYS-P-004 judges coverage only along
the flown path, so extra exploration buys nothing measurable and costs time. (This item was first
raised as customer question Q-05; review round 1 re-triaged it as a design decision.)
Reverses if: verification shows SYS-P-004 coverage below threshold with immediate return.

### D-02 — One ROS package per module; C++ for high-rate nodes, Python for mission logic and tools

Alternatives: a single monolithic package; all-Python. Why: brief 3.1 grades package/node
separation; C++ keeps depth-to-voxel and planning within the control loop's rate budget.
Python makes the state machine and the scoring tools quick to change.
Reverses if: a Python node measurably cannot keep up with its input rate (it moves to C++).

### D-03 — OctoMap as the voxel-grid representation

Alternatives: voxblox/nvblox (TSDF mesh), a custom dense grid. Why: suggested by the course
material, available for ROS 2 Jazzy as binary packages, gives both a map topic and a `.bt` file
viewable in the free `octovis` viewer (SYS-I-002), and supports the collision checks the planner needs.
Reverses if: E-02 shows `octomap_server` is unavailable or too slow on Jazzy.

### D-04 — The TF tree for sensors hangs from the estimated body frame

Alternatives: keep the provided static chain from `/true_body`. Why: SYS-C-001 forbids the true
pose; the provided chain attaches cameras to the truth. Our bringup publishes camera extrinsics
relative to `body` (from the corruptor's `world → body` TF) and does not launch the truth-attached static transforms.
Reverses if: never (imposed constraint).

### D-05 — Cave entrance point and approach route

**Decision:** The cave entrance point is E = ⟨x, y, z⟩ m in the `world` frame (ROS; state-estimate
frame). The predefined approach route is: take off to ⟨x, y, z⟩, then ⟨x, y, z⟩, then E, flown in
straight segments.
Alternatives: a mouth point at y ⟨…⟩ (blocked: the UAV hit rock at x ⟨…⟩, flight e03_f1); a point deeper
in the gallery (it is no longer "at the mouth" as the brief asks).
Why: E sits in the rock arch that opens into the gallery. The route was flown 9 times (3 runs × 3) with 0.00 m
arrival error and no contact (evidence/E-03.md), and the gallery beyond was flown to x ⟨…⟩.
Reverses if: a mission run shows contact on the approach, or the mapping shows E outside the cave opening.

## I1 — Walking skeleton: launch, approach, entrance event, map, output files

### Allocation

| Requirement | Modules |
|---|---|
| SYS-F-001 | cave_mission, cave_planning |
| SYS-F-002, SYS-F-003, SYS-S-002 | cave_mission |
| SYS-F-007, SYS-F-011, SYS-P-003 | cave_perception |
| SYS-F-008, SYS-F-014 | cave_mission (lantern file writer; the list stays empty until I3) |
| SYS-F-009, SYS-F-015, SYS-I-002 | cave_perception (map_writer) |
| SYS-C-001, SYS-C-003, SYS-C-004, SYS-C-005 | cave_bringup, simulation (install rule only) |

### Decisions

D-06 — Mission state machine in Python (rclpy), states WAIT_SENSORS → TAKEOFF → APPROACH → EXPLORE → RETURN → HOLD.
The mission "starts" when a state estimate and a depth image have both arrived. In I1, EXPLORE is a timed hover.
The transition logic is a plain class, separate from the ROS node.
Alternatives: SMACH/FlexBE, behaviour trees. Why: six states with linear transitions do not justify a framework,
and a plain class is unit-testable without ROS. Reverses if: I2 exploration needs concurrent behaviours.

D-07 — Trajectory planner: a path (`nav_msgs/Path` on `/planning/path`) becomes straight segments with a
trapezoidal speed profile (v_max 5 m/s, a_max 2 m/s²), yaw along the direction of travel, streamed as
single-point `MultiDOFJointTrajectory` (position, velocity, acceleration) at 50 Hz on `/command/trajectory`.
Alternatives: minimum-snap polynomials (mav_trajectory_generation). Why: the provided controller tracked
streamed set-points to 0.26 m in E-03, and the polynomial library has no Jazzy release. Reverses if: tracking
error in the cave exceeds 1.0 m (E-08 detector).
**Speed superseded by D-15:** v_max is 3 m/s mission-wide from I2 on; the 5 m/s bound of ITEM-D-003 still holds.

D-08 — Perception: `depth_image_proc/point_cloud_xyz_node` (16UC1 mm → metres, zeros dropped) feeding
`octomap_server_node` at 0.25 m resolution, sensor max range 20 m, map frame `world`.
Alternatives: 0.5 m (lighter), voxblox. Why: 0.25 m meets SYS-P-003's 0.5 m threshold with margin, and passages
are ≥ 22 m wide (E-06), so the map stays small; 20 m keeps ray-casting cost bounded at 5 Hz.
Reverses if: octomap insertion falls behind the 5 Hz depth stream (more than 10 % of clouds dropped).
**Reversed by E-13** (octomap_server inserted only 26–48 % of clouds in flight); the octomap_server part is
superseded by D-12. The depth_image_proc part and the 0.25 m / 20 m values stand.

D-09 — Outputs go to `<output_dir>/<run-stamp>/`, where `output_dir` is a launch argument defaulting to
`cave_mission_output` in the user's home directory, plus a `latest` symlink. The files are
`lanterns.csv` (header `id,x,y,z`), `cave_map.bt` (OctoMap binary, octovis) and `cave_map.ply` (occupied voxel
centres; MeshLab/CloudCompare). Each is rewritten atomically (write a temp file, then rename), both periodically and on SIGINT.
Alternatives: a single fixed directory. Why: a failed run never overwrites an earlier run's files, and the
atomic rename means a crash never leaves a half-written file. Reverses if: never.
Timer periods sit below the requirement bounds: lanterns every 8 s (bound 10 s) and maps every 25 s (bound 30 s),
because executor load delays each write past its nominal period. Both files are also written when the mission
enters HOLD (mission completion), and again on SIGINT.

D-10 — The single launch file `cave_bringup/launch/mission.launch.py` starts Unity with `GALLIUM_DRIVER=d3d12`
only when the WSL GPU device node exists (WSLg), plus the provided bridge nodes and corruptor (same
parameters), the controller and the mission stack. The simulation package gets an install rule for
`unity_sim` (a bridge build adjustment; the binary itself is unchanged).
Alternatives: require the user to export the variable. Why: E-02 shows the cameras drop to 1.6 Hz without it,
and auto-detection leaves native Ubuntu untouched. Reverses if: the check misfires on a native Ubuntu host (E-11).

D-11 — One-off mission events (the entrance-reached instant) are published with transient-local durability
(depth 1), carrying the event time as `builtin_interfaces/Time`, and are also written to the log.
Alternatives: a volatile topic, or a service the scorer polls. Why: the event fires once. A subscriber that starts
later (the scoring tool, RViz, `ros2 topic echo`) still receives it, and no extra interface is needed.
Reverses if: a consumer cannot use transient-local QoS.

D-12 — Our own mapping node `cave_perception/cave_mapper` (C++, OctoMap library) replaces octomap_server.
It subscribes to the depth image and camera info, looks up `world → camera` at the image stamp (100 ms
timeout), back-projects every 2nd pixel in each direction (19 200 rays), and inserts them with
`OcTree::insertPointCloud` (0.25 m, max range 20 m). It publishes the map (`octomap_msgs/Octomap`, binary)
at 1 Hz on `/perception/octomap`, counts clouds received vs inserted, and logs insertion time. The periodic
and final `.bt`/`.ply` writing (D-09) lives in the same node, so there is no second copy of the map.
Alternatives: tune octomap_server (queue depth, latch off; still 36–48 % in E-13); voxblox (no Jazzy
release). Why: insertion is under our control and measurable, and a single node owns both the map and its files.
Reverses if: the node's own counters show fewer than 90 % of clouds inserted in a gallery flight.
**Amended during I1 build (final review, evidence in the I1 sim runs):** a stride of 2 took 177–360 ms per
insertion in the gallery, and frames were silently dropped before reaching the node. Now: stride 4 (4 800 rays),
lazy insertion, and a multi-threaded executor with separate callback groups for insertion, publishing and
writing. The tree is guarded by a mutex, and files are written from a snapshot copied under the lock. The depth
subscription is reliable with a queue of 20. The map is published every 5 s (the full-tree refresh plus
serialisation held the lock for up to about 0.7 s). Result: every published depth frame was inserted
(389/387 and 390/388 in two runs; the harness counts published frames independently).
Reverses if: an independent count shows a published depth frame not inserted, or I2's larger map pushes the
publish lock beyond the 20-frame queue (about 4 s).

## I2 — Autonomous exploration, collision-free planning, return

### Allocation

| Requirement | Modules |
|---|---|
| SYS-C-002 | cave_navigation (explorer: frontier goals), cave_mission (EXPLORE loop) |
| SYS-C-009 | all packages (node structure) |
| SYS-F-006 | cave_mission (lantern-count trigger), cave_navigation (path to entrance) |
| SYS-S-001 | cave_navigation (clearance-checked paths), cave_planning (speed), cave_mission |
| SYS-S-003 | cave_navigation (goal blacklisting), cave_mission (hold while no path) |
| SYS-F-016, SYS-F-018, SYS-F-020, SYS-F-021 | cave_mission (no-movement watchdog, FAILED state, report, lantern file) |
| SYS-F-017 | cave_mission (exit on FAILED), cave_bringup (launch shutdown when the mission node exits) |
| SYS-F-019 | cave_perception (cave_mapper writes the map files on FAILED) |

### Decisions

D-13 — Frontier exploration on a navigation map owned by the path planner. The new C++ package
`cave_navigation` contains the node `path_planner`. It builds its own OctoMap at 0.5 m from the depth
stream, using the same projection code as `cave_mapper`, and it offers two services.
`/navigation/plan_to` plans a path to a given point (it is used for the return to the entrance).
`/navigation/explore` picks the best frontier and returns a path to it, or reports that no frontier is left.
A frontier is a known-free voxel that has an unknown neighbour. Frontiers are clustered, and each cluster is
scored as path length minus 2 × cluster size, where the path length is the A* distance.
Only frontiers beyond the entrance plane qualify: the plane passes through E, with its normal along the final
approach leg ⟨x, y, z⟩ → E. That plane comes from the predefined approach route, not from cave knowledge.
Alternatives: sharing the 0.25 m deliverable map (it is published only every 5 s, so the planner would work
on stale data); sampling-based next-best-view planners. Why: the planner sees the map at sensor rate; a coarser
grid keeps A* fast over a cave about 800 m long; frontier exploration is the standard method for unknown
confined spaces (SubT literature). Reverses if: A* planning takes more than 2 s, or the UAV leaves through the mouth.

**Amended during I2 build (sim run 20260929-142259):** the depth term uses the horizontal distance from the entrance. With the 3D distance the explorer climbed into a ceiling chimney (z 37 m) that narrowed to 2 m once seen close up; the UAV could not leave it within the 1.5 m escape zone (D-17) and the mission failed after 120 s (D-18).

D-14 — Path planning by 26-connected A* over the 0.5 m navigation map. A cell is traversable when it is
known-free and at least 1.5 m from every occupied voxel. The 1.5 m clearance covers the UAV radius
(about 0.3 m), tracking error (0.46 m max in I1) and margin. Unknown space is never traversable. The goal is
the nearest traversable cell within 3 m of the target, and the path is shortened by line-of-sight checks.
**Amended by E-15:** if no path exists at 1.5 m clearance, the planner retries at 1.0 m. The mouth narrows to
1.15 m clearance on the line flown in E-03; 1.0 m still covers the UAV radius, tracking error and voxel
quantisation. The hard minimum is 1.0 m (ITEM-D-016).
**Amended during the I2 build (simulation and final review, evidence in `evidence/I2-build-ledger.md`):**
- **Clearance tiers:** 2.0, then 1.5, then 1.0 m.
- **Unknown cells** count as obstacles for clearance.
- **Occupied-voxel distance:** measured to the voxel centre, with the radius widened by res*sqrt(3)/2. Every point along a segment therefore keeps the clearance, not just the cell centres.
- **Start must be traversable:** the planner reports StartBlocked instead of using an escape zone. The planner then
  reports NoPath (proven) or Budget (inconclusive), and only NoPath excludes a goal.
- **Search:** weighted A* (heuristic x3), up to 20 000 expansions per explore candidate (D-48), 60 000 per return leg.
- **Goal endpoint:** the path ends exactly at the goal when the last segment is traversable.
- **Map:** a navigation-map hit/miss of 0.75/0.45 resists erosion by grazing rays.
- **Frontiers:** grouped in 4 m bins and scored by distance - 0.05*size - 1.5*distance-from-E. A frontier under observed open sky (no-return rays, kept in a separate sky map) is never a goal.
Alternatives: RRT*, planning through unknown space. Why: A* is deterministic and testable; staying in known-free
space is what makes "no contact" (SYS-S-001) achievable without a prior map. Reverses if: the cave has passages
narrower than 3 m that the mission must pass (the passages seen in E-06 are 22 m or more).

D-15 — Cave flight speed. The trajectory planner's `v_max` becomes 3 m/s everywhere (a_max stays 2 m/s²). At the
5 Hz depth rate the UAV moves 0.6 m between frames, well inside the 20 m range and the 1.5 m clearance.
Alternatives: 5 m/s on the approach and 2 m/s in the cave. Why: one value, and the approach costs only about
35 s more. Reverses if: the SYS-P-002 time budget (I4) needs a higher speed.
Amended 2026-10-01 (I4 re-plan, E-33): v_max is 4 m/s. Two 30 min runs at 4 m/s had no bump, and every
tracking/surface/bump test passed; moving speed rose from 2.17 to 2.39-2.41 m/s.

D-16 — Exploration loop in the mission node. EXPLORE calls `/navigation/explore`, sends the path, waits until the
estimate is within 1.0 m of the path's end (or 60 s have passed), then repeats. If the explorer finds no path to
its chosen frontier, it blacklists that goal (5 m radius) and the service tries the next one. When no reachable
frontier remains, the reply is "none" and the mission switches to RETURN. While a call is pending or no path
exists, the mission publishes no path, so the trajectory planner holds the last set-point. That is the hold of
SYS-S-003. When at least four lanterns are reported on `/perception/lanterns` (`geometry_msgs/PoseArray`,
produced by I3), the mission switches to RETURN (D-01) and plans back to E with `/navigation/plan_to`.
Alternatives: continuous replanning with blended trajectories. Why: the stop-plan-go loop keeps the I1 trajectory
planner (a new path is started only at rest) and is easy to test. Reverses if: I4 timing shows the stops cost
too much of the 30 min budget.
**Amended during the I2 build (final review):**
- **Plan start:** every plan starts at the end of the last committed path, which is where the trajectory planner continues. Planning from the current position would leave an unchecked connecting segment.
- **Flight timeout:** it scales with path length. On expiry the UAV holds at its current position and plans from there.
- **Planner reply:** one not received within 30 s is retried.

D-17 — Escape zone near a start that is closer than the clearance (revisits D-14 after E-16).
**Fact:** after arriving next to a frontier, the UAV often observes rock within 1 m that was unknown when
the path was planned. Its own position then fails the 1.0 m clearance. Without an allowance, 70–95 % of plans
failed at the start and the return never planned (evidence/E-16.md).
**Decision:**
- **Start clearance level:** when the start does not meet the requested clearance, the planner finds the largest
  level L in {0.75, 0.5, 0.25} m that the start does meet. L is 0 if the start meets none, but it must still be known-free.
- **Escape zone:** within 1.5 m of the start, A* accepts cells that meet level L, so the path never gets closer to
  an occupied or unknown voxel than the start already is.
- **Beyond it:** the full clearance applies.

Alternatives:
- keep "all points ≥ 1.0 m" and hold forever (the mission stalls);
- the earlier unconditional zone (it let escape cells touch walls; this was a final-review finding);
- replanning backwards along the flown path.

Why: the UAV is already at that position. Moving away without ever getting closer is the safest available
motion, and it is bounded to 1.5 m.
Reverses if: a simulation run shows contact inside an escape zone.
**Amended during I2 build:** the start level is the exact nearest-obstacle distance between cell centres (`NavMap::obstacleDistance`), not the levels {0.75, 0.5, 0.25} m: a discrete level could accept cells closer than the start. A start that is not known-free stays StartBlocked.
Amended 2026-09-30 (customer Q-25, E-28): the escape zone is 3 m. A UAV that arrived 0.87 m above a floor mapped only
on arrival, under unknown space, found no exit within 1.5 m; replayed on that map, 3 m frees it. The path still
never gets closer to any obstacle or unknown cell than the start.

D-18 — Declared failure and run end (SYS-F-016..021, customer Q-10/Q-11).
**Detection:** a pure-Python `StallWatchdog` in cave_mission samples the corrupted state estimate at 1 Hz. It runs from entry to TAKEOFF until the UAV first comes within 1.0 m of the entrance with four lanterns reported (the end of SYS-F-016's window; revised after E-17, see below). At each sample it compares the samples of the last 120 s with the sample taken
120 s earlier. When all of them lie within 1.0 m of it, the state machine enters the new terminal state FAILED.
Sampling at 1 Hz declares at most 1 s late and costs 121 samples; a window starting between samples is covered by
the neighbouring sample to within the 1 s × 3 m/s travel, which can only delay a declaration, never cause a false one.
**Report:**
- `/mission/state` = FAILED (latched);
- `/mission/failed` (`builtin_interfaces/Time`, latched, as D-11);
- a log line `MISSION_FAILED t=…`;
- an `events.csv` row;
- the lantern file is rewritten.
**Run end:**
- the cave mapper writes its map files on FAILED, as it does on HOLD, then publishes `/perception/final_written`
  (latched `std_msgs/String`);
- the mission node stops issuing paths, waits for that notice or at most 8 s, and exits;
- `mission.launch.py` registers an `OnProcessExit` handler on the mission node that emits the launch `Shutdown` event,
  so every process gets SIGINT and the usual SIGINT final writes run once more.

Alternatives:
- let a supervisor script watch the pose (it would live outside the single launch file);
- call `Shutdown` from the mission node through a launch service (no such API).

Why: the watchdog is unit-testable with synthetic poses; exiting through the launch's own event system ends
everything the launch file started, and files are on disk before shutdown starts.
Reverses if: a sim run shows the run end taking more than 15 s after the declaration.

**D-18 revisited after E-17 (review finding):** a watch scoped by state list (TAKEOFF..RETURN) left a HOLD reached
with fewer than four lanterns unwatched, and watched RETURN at the entrance with four lanterns; neither matches
SYS-F-016. The watch now ends at SYS-F-016's own end event, tracked by a latch in the state machine.
Alternatives: keep the state list and add HOLD-with-fewer-lanterns as a special case (two rules instead of one).
Why: the child then says exactly what the parent says. Reverses if: never.

## I3 — Lantern detection, localisation, de-duplication, publishing, lantern file

### Allocation

| Requirement | Modules |
|---|---|
| SYS-F-004, SYS-P-001, SYS-F-005, SYS-F-013, SYS-F-010 | cave_lanterns (new Python package, node `lantern_node`) |
| SYS-I-001 | cave_mission (lantern file writer, D-09) |

### Decisions

D-19 — Lantern detection and 3D localisation from the semantic and depth images.
**Facts:**
- lanterns appear only as exact (255,235,4) pixels, with nothing else in the semantic image (E-12);
- the semantic and depth cameras share pose and intrinsics (fx = 120, 320×240, E-01), so pixels correspond one to
  one;
- depth ends at 49.5 m.

**Decision:**
- **Pairing:** a new node `cave_lanterns/lantern_node` pairs each semantic image with the depth image of the
  nearest stamp (within 0.1 s).
- **Detection:** it takes the exact-colour mask and splits it into 4-connected blobs. A blob is an observation
  when at least 3 of its pixels have valid depth (non-zero, below 49.5 m) and its median range is at most 45 m.
  A blob that is farther away is ignored completely: it neither creates nor confirms a lantern.
- **Back-projection:** each blob's pixels are back-projected with their depth, using TF world→SemanticCamera at the
  image stamp (the estimated body frame, ITEM-D-001).
- **Accumulated points:** the node keeps up to 2000 world points per lantern. When the cap is reached, the
  points of the farthest observations are dropped first.
- **Estimate:** the median of x and the median of y, and the vertical mid-point of the 2nd–98th percentile z
  extent. This is the E-10 (not published) estimator. With the 45 m gate, its error against the E-10 (not published) truth was 0.43 m with near
  views and 1.5 m with only 40–45 m views (E-10 (not published) addendum).

Alternatives: the per-frame blob centroid, averaged over frames. It is biased low or high whenever part of the
4.5 m body is out of the image or occluded.

Why: the union of views converges on the whole visible body. E-10 (not published) measured the offset between this estimate and
the true centre on three runs.

Reverses if: a simulation run reports a lantern more than 1.5 m from its E-10 (not published) truth.
**Amended during I3 build (lantern_check runs, `tools/probes/lantern_replay.py`):**
- An observation keeps 10 points, not 300. With 300, a close hover that sees only the lantern's top evicted every full-body view under the 2000-point cap (1.9-2.9 m error); with 10, the error is 0.07-0.09 m, and at most 1.6 m at any moment while reported.
- TF is looked up at the image stamp, falling back to the newest transform when that is at most 0.1 s older. Images are stamped 15-30 ms after the newest TF.

D-20 — Association and confirmation.
**Association:** an observation is merged into the nearest lantern (reported or candidate) whose estimate lies
within 8 m of the observation's median point; otherwise it starts a new candidate. Two lanterns whose estimates
come within 8 m of each other are merged. The cave lanterns are more than 100 m apart (E-05 (not published)), and one
lantern seen as two blobs stays within its 4.5 m body.
**Confirmation:** a candidate is reported once it has at least 3 observations. That is 0.6 s at 5 Hz. E-12 saw no
false pixels, so this guards only against single-frame artefacts.
**Reporting:** a reported lantern is removed only by merging into another. The survivor is the earlier-reported lantern: it keeps its place in the order, and it pools both lanterns' observation counts and points (under the 2000-point cap, farthest observations dropped first). Estimates keep improving as observations arrive.
Alternatives: nearest-neighbour data association with covariance gating, which the evidence does not need.
Why: it is simple, and the gate sits far from both failure modes (8 m ≪ 100 m spacing, 8 m ≫ 4.5 m body).
Reverses if: two cave lanterns lie within 16 m of each other.

D-21 — Excluding the reference lantern.
Observations are accepted only while `/mission/state` is EXPLORE or RETURN, which is after the entrance event.
A lantern is reported only when its estimate lies beyond the entrance plane: the same plane as D-13, through E,
with its normal pointing from `approach_from` to E.
Alternatives: exclude a fixed radius around the start point; that would encode where the reference lantern is.
Why: the entrance is the one location the mission may know, and the reference lantern sits 245 m outside it.
Reverses if: a cave lantern lies outside the entrance plane.

D-22 — Publishing.
`/perception/lanterns` (`geometry_msgs/PoseArray`, frame `world`, reliable, depth 10) carries the reported lanterns
in order of first report. It is published at 1 Hz and immediately when a lantern is added. The mission node
already consumes it: the lantern file (D-09) and the four-lantern return (D-16).

D-23 — Altitude ceiling of 20 m above E for planning (after E-19 (not published)). **Rejected by the customer (Q-17): no fixed ceiling; replaced by D-24.**

D-24 — Only camera-revealable frontiers are exploration goals; vertical travel costs more (replaces D-23; E-19 (not published)).
**Mechanism (E-19 (not published)):**
- The forward camera (±45° vertical field of view) never observes the space straight above or below the UAV, so it
  stays unknown and forms a frontier just above the UAV.
- Choosing such a frontier lifts the UAV a little, reveals nothing above, and leaves a new frontier just above it.
- The climbing goals of run 20260929-171201 sat 0.5–1.5 m under unknown space. This creep led into the ceiling
  chimney (a35d69d) and out through a roof opening.

**Decision:**
- A frontier cell is eligible as an exploration goal only if at least one of its four horizontal neighbours
  (±x, ±y) is unknown. The UAV still flies up or down to reach such a frontier at any height.
- The goal score measures travel as the horizontal distance plus 3 × the height climbed, plus the height descended
  (amended 2026-09-30, customer Q-24, E-27: with descents also weighted 3 the UAV never came within 80 m of Lantern,
  85 m below the tunnels, in 8 runs; with 1 it reported it. The chimney creep of E-19 (not published) went up, not down).
- There is no altitude limit. The no-movement failure (D-18) remains the backstop.

Alternatives:
- a fixed 20 m ceiling (D-23, rejected by the customer);
- a sky-based "inside the cave" test: long galleries also give no-return rays, so it cannot separate outside from
  far.

Why: exploration then only targets unknown space that flying towards it will reveal, which stops the upward creep at
its cause.

Reverses if: a long run shows the UAV above the terrain or in contact again, or exploration can no longer reach a
lantern that lies behind a vertical-only frontier.

D-25 — Bump detection, in-flight path re-check and recovery (E-19 (not published); the customer chose option A, Q-18).
**Fact (run 20260929-192814):** at the gallery–Tunnel1 junction, the UAV came within 0.42 m of a MeshCollider that
the camera had seen only from its invisible back side. Its tracking error reached 0.85 m (clean flight: up to
0.35 m), and it stuck until the D-18 failure.

**Decision:**
- **Bump:** the trajectory node declares a bump when the estimate stays more than 0.5 m from the commanded set-point
  for 0.3 s. It then brakes from the current set-point at a_max (ITEM-D-003 holds) and starts the next path at the
  estimate. It publishes `/planning/bump`, the point 0.6 m from the UAV towards the set-point.
- **Obstacle marking:** the path planner marks the navigation cells within 0.5 m of that point as occupied.
- **In-flight re-check:** while a path is flown, the path planner re-checks its remaining part at 2 Hz. When an
  occupied cell lies within 0.5 m of it, it publishes `/navigation/path_blocked`, and the trajectory node brakes.
- **Recovery:** on either signal the mission node replans from the current position (SYS-S-003).

Alternatives: accept the residual risk (option B, not chosen).

Why: the state estimate is a reliable contact sensor, and newly mapped obstacles are no longer flown into. Surfaces
the camera cannot see can still be touched once.

Reverses if: bumps are declared in clean flight (false stops), or long runs still end stuck at a contact.

## I4 — Full-mission performance and delivery

### Allocation

| Requirement | Modules |
|---|---|
| SYS-P-002, SYS-P-005 | cave_navigation (explorer: D-26, D-27), cave_mission (D-28), cave_planning (D-30), whole stack (acceptance runs) |
| SYS-P-004 | cave_perception (map), tools/ (coverage analysis, D-29) |
| SYS-C-006 | repository `README.md` |
| SYS-C-007, SYS-C-008, SYS-C-010 | `docs/documentation.md` |
| SYS-F-022 | cave_bringup (launch argument `viz`), cave_viz |
| SYS-F-023..SYS-F-027 | cave_viz (node `mission_viewer`); cave_mission (goal topic) |
| SYS-F-028 | cave_perception (downsampled cave points), cave_viz |
| SYS-P-006 | cave_viz (render budget), whole stack (measured on and off) |

### Decisions

D-26 — Outdoor frontiers are not exploration goals (revises the D-13 sky test; E-20).
**Decision:** a frontier goal is dropped when the sky evidence (cells crossed by no-return depth rays) fills at least
15 % of a vertical cylinder above it (radius 8 m, from 5 m to 45 m up). This replaces the single-column test.
Outdoor points measured 0.19–0.27, gallery points 0.04–0.10 (E-20). The threshold and cylinder are generic sensor
parameters: the mission reads no cave data, and the truth was used only to label the probe samples.
Alternatives:
- require an observed ceiling: ceilings are often not observed above goals inside the cave (E-19 (not published));
- geometric bounds: prior knowledge.
Why: the UAV left the cave through the mouth in 3 of 18 runs and got stuck outside.
Reverses if: a run shows a cave frontier dropped as outdoor (lanterns not reached), or the UAV outdoors again.

D-27 — Nearest-first exploration: no bonus for distance from the entrance (revises D-13 scoring; E-18).
**Decision:** frontier goals are ranked by travel (horizontal + 3 × vertical, D-24) minus 0.05 × frontier size. The
depth bonus is removed.
Fact: the depth bonus sent the UAV west past the south branch to Lantern (2) and away from the descending branch
to Lantern, in 13 of 13 runs that reached the tunnels (E-18).
Alternatives: a smaller depth bonus (still biased against branches back towards the entrance).
Why: nearest-first finishes the branch it is in before moving on, so side branches are not skipped.
Reverses if: the UAV dithers near the mouth again (the I2 reason for the bonus); the D-24 and D-26 filters now
remove most of those frontiers.

D-28 — Request the next exploration goal before arriving (revises D-16; E-18).
**Decision:** when the path being flown has at most 4 m left, the mission node requests the next exploration
path from the committed path end. It releases the new path at once, so the trajectory planner queues it and starts
it when the current one ends (D-07), with no stop for planning.
Fact: explore planning takes 11–13 % of the exploration time, and the UAV is stationary for 26–30 % (E-21).
Alternatives: continuous replanning while flying, which needs trajectory blending (a larger change).
Why: it removes the planning wait at every goal. The flight itself is unchanged.
- **Remaining distance:** it is measured along the path, from the path point nearest the estimate.
- **A bump or block while the request is pending:** the reply is discarded and the mission replans from the current
  position (ITEM-D-034).
- **Four lanterns reported while a queued path is released:** the return starts at that path's end, the committed
  end (the D-16 rule), which costs at most one goal leg.

Reverses if: goals chained this way ignore frontiers observed during the last approach (the next goal is chosen
from a map up to 2 s old).
Amended 2026-09-30 (I4 re-plan): the request goes out 6 m before the path end, not 4 m. 10 m was tried and
rejected: with legs of about 12 m the explorer then planned from path ends the camera had not seen yet, and the UAV
zig-zagged at the hook for over 5 min (run 20260930-224423, watched live). At 2 m/s, with about 1.2 s of
planning, 7 of 18 replies to a 4 m request arrived after the UAV had stopped at the path end. Stopping at path ends
took 130-145 s per 30 min run (tools/probes/stationary.py). A path that arrives on a rounded corner is now joined at
the next straight stretch instead of waiting for rest.

D-29 — Map quality judgement (SYS-P-004, SYS-C-010).
**Decision:** an offline tool, scoring side only, takes the reference surface points (static-batched meshes, E-19 (not published))
within 5 m of the flown path inside the cave. It counts a point as mapped when an occupied voxel of the run's
`cave_map.ply` lies within 0.5 m. The documentation states the method and the result.
Why: this is exactly the SYS-P-004 criterion, from data every run already writes.

D-30 — Faster motion along paths (E-21).
**Fact:** moving speed is 1.64–1.76 m/s against v_max 3 m/s. Every segment is flown rest-to-rest, and the UAV turns in
place before each one.

**Decision:**
- **Rounded corners:** each intermediate path waypoint is rounded with a circular arc that departs at most 0.25 m
  from the planned polyline, which is inside the 1.0 m clearance of ITEM-D-016. The arc is flown at no more than
  √(a_max·r). The speed along the path is limited forwards and backwards by a_max, so the set-point acceleration
  never exceeds a_max. This is review round 2 finding N1: a hard corner at speed would jump the velocity.
- **Turning:** yaw turns in place only for a direction change of more than 90°. Otherwise yaw follows the direction
  of travel at the 60°/s rate limit while moving.

Alternatives: a higher v_max (limited by stopping distance in the D-25 braking).
Why: it removes most of the decelerations and turn-in-place stops. The set-point velocity stays within a_max
(ITEM-D-003).
Reverses if: tracking error in corners exceeds the 0.35 m of clean flight (E-19 (not published)), or contacts increase.
**Amended during I4 build (runs 20260930-010745, -014732):** the pace reached only 1.37 m/s. The goals are about
8.5 m apart and every path started and ended at rest.
- **Joining paths:** a path that arrives while the UAV flies straight is joined without stopping. A new profile
  starts from the current set-point and speed, through the rest of the current path into the new one, if it can
  still brake within a_max for everything ahead.
- **Protected corners:** corners within 2 m after the join (the new path's own start) stay unrounded, as for any path
  start (ITEM-D-040).
- **Longer legs:** the explorer's minimum goal distance becomes 12 m (was 6 m), so there are fewer, longer legs.

**I4 time budget (E-21):**
- **Tour:** about 2400 m (entrance to Lantern (3), the tunnel entrance, Lantern (2), the loop, Lantern, Lantern (1),
  then back to E).
- **Pace needed:** about 1.6 m/s to fit 1800 s, against 1.14–1.30 m/s measured.
- **Expected gains:** D-28 removes the planning waits (11–13 % of the time). D-30 raises the moving speed and removes
  the turn-in-place stops. D-27 avoids the 1100 s of dithering in the far corner.
- **Measurable target:** ITEM-D-039 (pace).

D-31 — Mission visualization: an OpenCV top-down viewer (SYS-F-022..028, SYS-P-006; customer Q-22).
**Decision:**
- **New package `cave_viz`, node `mission_viewer`.** It is Python and draws a top-down (x-y) image with OpenCV, in
  one window, redrawn every second.
- **What it draws:**
  - the cave points, shaded by height;
  - the path being flown (`/planning/path`);
  - the current flight goal (`/mission/goal`, a latched `PointStamped` of the released path's end, published by
    `mission_node`);
  - the reported lanterns (`/perception/lanterns`);
  - the UAV (`/current_state_est`) with its heading;
  - a status line.
- **Framing:** the view frames the bounding box of the cave points and of the markers beyond the entrance plane. It
  uses nothing but this run's data, and the approach route is not framed.
- **Cave points:** at each 25 s snapshot, `cave_mapper` publishes `/perception/cave_points` (`sensor_msgs/PointCloud2`).
  These are the occupied voxels beyond the entrance plane, reduced to one point per 1 m cell and capped at 150 000.
- **Launch:** `mission.launch.py` starts the node unless `viz:=false`. Without a display, the viewer logs and exits;
  it is not the mission node, so the run continues.

Alternatives:
- RViz2 (installed): it cannot frame the view on the mapped extent from a node, and it is a heavier 3-D renderer
  beside Unity;
- matplotlib: not installed, and sudo is not available on the development host.

Why: OpenCV is already a dependency (cave_lanterns). A 2-D image redrawn once a second with at most 150 000 points
costs little CPU next to the simulator.

Reverses if: SYS-P-006 fails (the camera rates drop), or the window does not open under WSLg.

D-32 — Lone map voxels are removed from the delivered map (E-23; ITEM-D-041).
**Decision:** before each snapshot is published and written, `cave_mapper` frees every finest-resolution occupied
voxel with no other occupied voxel within 1.0 m (`removeSpecks`, `map_io.cpp`). Pruned occupied blocks are never
removed. The path planner's navigation map is separate and unchanged.
Alternatives:
- require two hits before a voxel counts as occupied: it slows mapping of thin or distant surfaces for every voxel,
  to catch 0.01 % of them;
- leave the specks: they are not cave surface, so they lower map accuracy, and one of them made the SYS-S-001
  surface check (run's own map within 0.5 m) fail with the real surface more than 2 m away.
Why: a surface seen by a depth camera gives many neighbouring voxels; a lone voxel in open air is noise. Removing
0.01 % of the cells costs nothing in coverage (SYS-P-004 counts a reference point mapped if any voxel lies within
0.5 m).
Reverses if: a map coverage run (SYS-P-004) drops by more than 0.1 percentage point with the filter on, or a lone
voxel is shown to lie on a real surface (reference within 0.5 m) in more than 30 % of cases.

D-33 — Defer leftovers above the flown track (amends D-27; E-24; ITEM-D-042).
**Decision:** the path planner gives the explorer the flown track beyond the entrance, one point every 2 m. A
frontier goal that lies within 8 m horizontally of the track and more than 4 m above it, with no track point near
its own height, is ranked 150 m farther. Goals below the track are never deferred: in run 20260930-043943 the way
down at the western junction showed as frontiers 17-20 m below the flown track (E-24 addendum), and Lantern and
Lantern (1) both lie below the tunnels.
Fact: in run 20260930-023723 the UAV flew the tunnels at z 9-14 m. From 1200 s it followed frontier goals at z
18-25 m straight above its own track, 500 m back towards the entrance, and it never reached Lantern or Lantern (1)
(E-24).
Alternatives:
- defer every goal near the track: this also defers side-branch mouths at flight height, the D-27 problem;
- a fixed ceiling above the track: rejected by the customer (Q-17).
Why: a forward camera sees along a passage at its own height; what stays unknown straight above or below the track
is the part of the passage outside the vertical field of view. Above the track that is the ceiling; below it,
it can be the way down. The lanterns are seen from up to
45 m along the passage (D-19). The deferred goals stay eligible: they win when nothing new lies within 150 m.
Reverses if: runs with it find fewer lanterns within 1800 s than the three runs before it (1-2), or a lantern is
found only in a deferred leftover.

D-34 — A goal flown to excludes 6 m around it (was 2 m; E-26; ITEM-D-043).
**Decision:** once a goal is released for flight, no later goal within 6 m of it is offered. Frontier bins are 4 m,
so the old 2 m radius left the neighbouring bins of a reached goal eligible.
Fact: in three 30 min runs, goals within 6 m of an earlier goal took 7 %, 11 % and 29 % of the goal time. In run
20260930-052139 the goals alternated between two spots 13 m apart for more than 3 min at z 30 (E-26). Such a
frontier survived a visit, so the camera cannot reveal it from there.
Alternatives:
- count visits per bin and exclude after the second one: this still pays one wasted return per bin;
- a larger radius (8 m): 38 % of the goal time in the worst run lies within 8 m, but a real passage's next goal
  can then fall inside it after a short leg.
Why: in a passage that is being revealed, the next goal lies at least 12 m ahead (min_goal_distance), outside 6 m.
Reverses if: runs with it leave frontiers within 6 m of a reached goal that lead to an unexplored passage (a lantern
found only there, or the explorer reporting NONE_LEFT with the reference passage unmapped).

## I4 re-plan (customer Q-26)

D-35 — Outdoor views: open sky in the upward depth rows excludes the frontiers in view (E-31; ITEM-D-044).
**Decision:**
- For every depth image, the path planner takes the fraction of pixels looking more than 30 degrees up that have no
  return, or a range of at least 49.5 m.
- When the median over the last 10 images (2 s) is at least 0.4, and the camera is at least 10 m past the entrance
  plane, it records that view (camera position and yaw).
- A frontier goal within 45 m of a recorded camera, inside its 106 x 90 degree field of view, is outdoors and is not
  selected. D-26 stays as it is.

Fact: the D-26 sky cylinder above a goal fills only after the UAV has looked up from under it. The explorer therefore
followed the valley south of the mouth step by step; that took most of acceptance run 2 and three other runs (E-18,
I4-acceptance). A ceiling returns the upward rays; open sky does not.

Alternatives:
- sky evidence at the UAV's position: it flagged 39 % of roofed positions in the tall, skylit gallery (E-31);
- no ceiling observed above: 11 % of roofed positions flagged.

Why:
- 0 of 9508 cave frames beyond the mouth were flagged (run 20260930-201941);
- 99 % of valley frames were flagged, the first at the valley opening seen from the mouth (valley flight probe);
- the 10 m margin keeps the mouth itself, which sees the sky outside, from excluding the gallery.

Reverses if: a mission run records an outdoor view inside the cave (OUTDOOR_VIEW log with a roof above), or a run
still detours into the valley.

D-37 — Passage following: passage regions first, the one passed most recently first (E-36 probe; ITEM-D-045).
**Decision:**
- The explorer groups its frontier bins into 26-connected regions (as D-36). A region of at least 6 bins is a
  passage region.
- Each passage region gets an anchor: the sequence number of the most recent flown-track point within d_min + 5 m of
  it, where d_min is its distance to the nearest track point.
- Goals in passage regions are tried first, the most recent anchor first (anchors within 5 track points count as
  equal, then the nearer goal). Pockets, ceiling leftovers (D-33) and goals more than 10 m above the UAV come after,
  nearest-first.
- Switch `passage_mode` (default off until E-36 decides).

Fact: speed and re-flown track are not the loss (3600-4000 m flown against a 2600 m lantern tour, 4-10 % re-flown).
The loss is pockets in the first gallery (470-700 s) and branches left half explored when another frontier is nearer
(E-32, acceptance runs, E-27).

Alternatives:
- heading term (E-29) and region-size bonus or tier (E-32, E-34): no gain in lanterns;
- choosing the better branch at a fork: needs knowledge of the cave the mission must not use.

Why: depth-first along the passage the UAV is in finishes a branch before the next; backtracking goes to the branch
opening passed most recently, so no branch is left for last by distance alone. Safety is unchanged: every path comes
from the same planner and clearance rules.

Reverses if: a lantern is missed because its alcove was a pocket never revisited, or the passage order strands the
UAV far from the entrance at the time cap more often than the default does.

Outcome (E-36): not adopted; `passage_mode` stays off. Mean 2.67 lanterns against 2.75. A long region beside the UAV
always holds the most recent anchor, so the order followed the gallery's wall band back to the mouth in one run.

## I5 — Mission completion and safety

Allocation: SYS-S-001 to cave_navigation, cave_planning and cave_perception; SYS-P-002 to cave_navigation,
cave_planning, cave_mission and cave_lanterns; SYS-P-004 to cave_perception and cave_navigation; SYS-P-005 to the
whole stack (cave_bringup).

D-38 — Outdoor zone: frontier goals within 20 m (horizontal) of an outdoor view's camera are outdoors (ITEM-D-046).
**Decision:** in addition to D-26 and D-35, a frontier goal within `outdoor_zone` (20 m, horizontal) of the camera
position of any recorded outdoor view (D-35) is outdoors, whichever way the camera looked. Path planner parameter
`outdoor_zone` (0 = off).

Fact: in acceptance run 20261002-192153 the UAV recorded 711 outdoor views and still explored the valley for 1700 s;
the D-35 cone with its line-of-sight guard covered few of the valley frontiers it went to. The camera of an outdoor
view is itself under open sky.

Alternatives: a larger D-35 range or cone (the frontiers were behind terrain or out of the cone); a ceiling test at
the goal (rejected in E-31: 1 of 5 good views had a mapped ceiling).

Why: replay of 14 runs (`tools/probes/outdoor_radius.py`): 20 m excludes 105 of 125 valley goals of that run,
including the first steps into the valley (9 m and 18 m from views taken seconds before), and 0-20 goals per other
run, near or above the mouth.

Reverses if: an E-39 run misses a cave frontier needed for a lantern because of the zone, or still enters the valley.

Amended 2026-10-03 (E-40 run 3 second retry, 20261003-004654): outdoor views taken in the tall mouth opening
(10-12 m past the plane, looking up) put the whole start of the gallery in the zone; with no other frontier yet
the explorer reported none left after 62 s and the mission returned with no lantern. Zone goals now come after
every other goal instead of being excluded (pending customer approval, Q-33).

D-39 — Enclosed start: a search exhausted in under 3000 cells tries 0.75 m clearance and excludes no goal (ITEM-D-047).
**Decision:** when every fallback clearance (2.0, 1.5, 1.0 m) ends in NoPath after fewer than 3000 expansions, the
start is shut in by the clearance, not cut off: the planner tries 0.75 m once more, and the explorer moves on to the
next goal without excluding the failed one.

Fact: in E-39 run 1 (20261002-210447) the UAV flew into a pocket of the first gallery at 1.0 m; with its mouth mapped
more closely every plan failed after 560-2000 expansions, 8 goals per request were excluded as unreachable, and the
mission failed for no movement. From that start a 0.75 m path exists whose points stay 1.12 m or more from every
non-free cell centre (`tools/probes/clearance_try.cpp`); clearances count half a cell diagonal (0.43 m) of margin.

Alternatives: 0.75 m in the general fallback list (narrow passages everywhere would be flown with less margin);
retracing the flown track (the track's cells may since have been mapped closer).

Why: only shut-in starts use it; 0.75 m plus the 0.43 m cell margin keeps more than the 0.5 m surface criterion.

Reverses if: a run shows a contact or a tracking failure on a 0.75 m path.

D-40 — Mouth band: once the UAV has been 50 m past the entrance plane, no goal less than 15 m past it (ITEM-D-048).
**Decision:** after the flown track has reached 50 m past the entrance plane, frontier goals less than 15 m past the
plane are not selected. Path planner parameter `mouth_band` (0 = off).

Fact: E-39 run 1 (20261002-213323), with D-38, came back to the mouth after 900 s and chased frontiers on the cliff
north of it (up to 37 m high, 21 m from the nearest outdoor view; outdoor views are only taken 10 m past the plane).
Acceptance run 20261002-192153 entered the valley through goals by the mouth at 162 s.

Alternatives: a larger outdoor zone (D-38: more cave goals lost in the skylit first gallery); outdoor views from
the mouth itself (the mouth sees the sky outside and would exclude the gallery, D-35).

Why: replay of 15 runs (`tools/probes/mouth_band.py`): such goals came only in the 4 runs that went outside
(4-18 each, the valley run's first at 162 s), none in the other 11. Only the entrance plane, a mission input, is used.

Reverses if: a run needs a frontier within 15 m of the entrance plane for a lantern or for the map.

D-41 — Flight dynamics: acceleration limit 4 m/s^2 (was 2) and turn rate 120 deg/s (was 60) (ITEM-D-003, E-40).
**Decision:** the trajectory planner limits acceleration to 4 m/s^2 and turns at up to 120 deg/s; v_max stays 4 m/s.

Fact: in acceptance run 20261002-200007 the set-point was at v_max 18 % of the time, below 2 m/s 52 %, with about
190 stops; flying the same distance at v_max would have saved 924 s. Each stop costs a brake and a re-acceleration.

Alternatives: 3 m/s^2 and 90 deg/s (E-40 run 1: safe, 4562 m flown); fewer stops by joining paths (still open).

Why: E-40 runs 20261002-225841 (3, 90) and 20261002-233927 (4, 120): no bump, tracking error at most 0.61 and
0.55 m (limit 1.0 m), every safety test passes; distance flown 4562 and 5149 m against 3691-3915 m, time at v_max
29 % and 40 %.

Reverses if: a run shows a tracking error above 1.0 m or a contact attributable to the higher acceleration.

D-42 — Partial approach: a goal that runs out of budget is approached as far as the map allows (ITEM-D-049).
**Decision:** when the plan to a frontier goal runs out of budget, the planner returns the path to the expanded cell
with full clearance nearest the goal. When that cell is at least 3 m from the start and at least 3 m nearer the
goal, the explorer returns it as the path; the goal is neither set aside nor counted as flown to (D-34).

Fact: in E-40 run 2 (20261002-233927) the frontier 10 m ahead in the tunnel to Lantern (1) ran out of budget at
891 s; it was set aside for 20 calls, the UAV stepped back east and turned round 58 m from the lantern, losing about
7 min. On the final map the same plan succeeds in 21 expansions: the way was not yet mapped.

Alternatives: shorter budget cooldown (the UAV still leaves); a larger budget (10-30 s per failure, E-37).

Why: flying closer lets the camera map the way, as a person would walk up to look.

Reverses if: runs show repeated partial approaches to the same goal without progress.

Amended 2026-10-03 (E-40 run 3, 20261003-002404, stopped after 3 min): approaches towards goals above the UAV flew
it into the unseen gallery ceiling, four bumps in 30 s at the partial ends. Only level approaches now: neither the
goal nor the partial end more than 2 m above the start (the case that motivated D-42 was level).
Amended again (E-40 run 3 retry, 20261003-003136, stopped at 700 s): partial approaches alternated between two
ends 13 m apart for 40 s; a partial approach may not end within 3 m of where an earlier one started or ended.

D-43 — Return along the flown track in legs of up to 40 m (ITEM-D-050).
**Decision:** a return plan to a goal more than 40 m away goes to the earliest point of the flown track within 40 m
(earlier than the one nearest the UAV) that a plan reaches; the mission flies each leg and asks for the next, until
the entrance is within 40 m and is planned directly. The direct plan stays as the fallback.

Fact: E-41 run 1 (20261003-015728) reported all four lanterns at 1136 s, then 19 return plans of about 900 m to the
entrance ran out of budget (400000 expansions, 4-5 s each) and the mission failed for no movement at 1261 s.

Alternatives: a larger budget (the plan through 900 m of winding cave at 0.5 m cells is not bounded); a waypoint
graph of the track (more code for the same effect).

Why: the track is known free and connects to the entrance; legs of 40 m plan in well under a second, and jumping to
the earliest reachable point skips the track's loops and dead-end excursions.

Reverses if: a run's return takes longer than flying the track directly would, or a leg cannot be found.

D-44 — Navigation-map depth range 35 m (was 20 m); the sky evidence keeps 20 m.
**Decision:** the path planner inserts depth returns up to 35 m into the navigation map. The cave map (cave_mapper)
and the no-return sky evidence (D-26) keep 20 m.

Fact: with 20 m the far walls of the wide first gallery stay unknown from most of it; runs spent 10-26 min there
(20261003-005719: no lantern in 26 min).

Alternatives: exploration-order rules (E-29, E-32, E-34, E-36: no gain).

Why: E-41 runs 20261003-015728 and -022451 reported all four lanterns (at 1136 s and 1893 s), for the first time;
the best of 15 earlier runs with 20 m had three. No bump in run 2, all safety tests and coverage passed. Cost:
explore planning 26 % of the exploration (17-21 % with 20 m).

Reverses if: planning time stalls the UAV (requests over 10 s) or the mapping falls behind the depth stream.

D-38 and D-40 amended again (E-41 run 3, 20261003-030430, stopped by the customer at about 1770 s): with zone goals
only tried last (Q-33), the UAV left the first gallery at 1476-1516 s through its south side, 15-21 m past the
entrance plane, and explored the valley; new valley frontiers beyond 20 m of the views kept coming first. Now: the
zone excludes again, but only views taken after the track had reached 50 m past the plane count (the views through
the mouth at the start, 20261003-004654, have none); the mouth band is 25 m (replay of 17 runs: 2-6 goals near the
gallery start in four runs that stayed inside, 37 in the valley run). A mapped ceiling over the goal does not
separate inside from outside (`tools/probes/mapped_roof.cpp`: 18 of 33 valley goals had one). Pending Q-34.

D-38 amended a third time (E-42 run 1, 20261003-034057, stopped at 80 s): before being 50 m in, the UAV went from
the mouth into the valley opening; its views there did not count. A view now also counts when its camera is at
least 25 m (horizontal) from the entrance point: the valley views are 45-50 m from it (97-99 % of all valley-run
views at least 20 m), the views inside the tall mouth 10-15 m (one of nine at 24 m, above the mouth). Pending Q-35.

D-38 zone radius 30 m (was 20 m), E-43 run 1 (20261003-053354, stopped at about 90 s): from the valley opening the
UAV took goals 20-25 m ahead of its latest view, just outside the 20 m zone, and walked into the valley one goal at a
time. Replay of 20 runs with the current view gating (`tools/probes/zone_replay.py`): outdoor goals excluded at
20/30/35/45 m - 110/126/129/131 of 136 (acceptance run 2), 6/30/32/32 of 33 (20261003-030430), 1/6/6/6 of 7 (this
run); cave goals excluded in the runs that stayed inside 0-2 / 0-6 / 0-9 / 0-14 per run. Pending Q-36.

D-45 — Close hits stay occupied in the navigation map (ITEM-D-051).
**Decision:** every cell holding a depth return measured within 10 m of the camera stays occupied for the rest of the
mission (kept apart from the OcTree, like the bump marks); the UAV's own cell is cleared from it at each request.
Path planner parameter `sticky_range` (0 = off).

Fact: runs 20261003-034624 (393 s) and -053936 (1983 s) passed 0.47 m from a cave-map surface where the navigation
map had no non-free cell within 2.5-3 m; tracking error 0.15 m. The surfaces are small features in one 0.5 m cell,
cleared by later rays passing through the rest of the cell. Overall, 0.0-0.2 % of cave-map surface points near the
track have no navigation-map cell within 0.5 m (`tools/probes/carved.py`).

Alternatives: weaker misses (already 0.45 against 0.75 hits); planning on the 0.25 m cave map (four times the cells).

Why: a surface seen from close range is real; keeping it costs one hash per close return.

Reverses if: depth noise near the camera leaves obstacles that block passages (stalls at a free passage).

D-46 — Lantern merge radius 15 m (was 8 m) (ITEM-D-028, pending Q-38).
**Decision:** observations within 15 m of a lantern's estimate join it; lanterns within 15 m merge.

Fact: in E-44 run 1 (20261003-062459) the camera came within 3.4 m of the deep Lantern; its pixels took the depth of
the wall 14 m behind it, the observation lay 11 m from the reported lantern, and a fifth lantern was reported, which
also made the mission return with three real lanterns. The lanterns are 100 m or more apart (E-05 (not published)).

Reverses if: two real lanterns lie within 15 m of each other.

D-47 — Descents weighted 0.5 in the explorer ranking (was 1; ITEM-D-031, customer Q-39).
Fact: after Lantern (1) the UAV went back east along the tunnels (level frontiers) in three runs and reached the
descent to the deepest lantern at 1800-2060 s; with 0.5 (E-44 run 1, 20261003-062459) it took the descent right after
Lantern (1) and reported that lantern at 750 s. Reverses if: the acceptance runs show it diving into dead-end
descents at the cost of a lantern.

D-42 amended (E-46): a partial approach keeps the widest fallback clearance that gave one (was the last, 1.0 m).
Fact: since the partial approaches and the 35 m map (runs 20261003-022451 to -065535) the share of paths at 2.0 m
fell from 55-70 % to 34-43 % and the cave-map points within 1.5 m of the track rose from 288-764 to 1496-2642 per
run (`tools/probes/phantom_count.py`); three of four close passes were near small isolated clusters (no reference
cave surface within 2 m - small objects outside the batched reference, or depth artefacts) 0.2-1.0 m from the track
(`tools/probes/phantom_check.py`, `near_surface_context.py`); the fourth was a wall seen late (braking stop).

D-45 amended (E-46 run 2): a start shut in by close hits releases them. When the explorer or a plan reports the start
blocked, the path planner drops the sticky hits within 5 m of the UAV (escape radius 3 m + widest clearance 2 m) that
the depth map now sees free, and plans once more; bump marks and cells still occupied stay.
Fact: run 20261003-125758 braked at 553 s on a hit 1.2 m from the UAV at the hook ⟨x, y, z⟩; every later request
was start-blocked and the mission failed after 120 s without movement. The saved navigation map has only free cells
within 3 m and the cave map no point within 4 m (`tools/probes/cell_states.cpp`).
Reverses if: released cells turn out to be real surfaces (a bump or close pass right after a release).

D-48 — An exploration candidate is searched with at most 20 000 expansions per clearance (was 60 000); return legs
keep 60 000. Explorer parameter `candidate_max_expansions`.
Alternatives: keep 60 000 and allow more time per request; a reachability flood before ranking (one large search per
request, slower than the failures it saves). Why: run 20261003-131633 (E-46 run 3) came back to the first gallery
after L3; every nearby candidate there ran out of budget at each clearance (about 10 s each, one per request) and the
UAV held for 120 s until the mission failed. In 14 runs, 1739 of 1741 successful candidate plans needed at most 20 000
expansions (1674 at most 1000); a failure now costs about a third as long.
Reverses if: goals reachable only beyond 20 000 expansions are missed where the run needs them (a passage left
unexplored while its frontier ran out of budget).

D-49 — An exploration goal whose path is blocked twice by a newly mapped obstacle is set aside for 20 calls, like a
goal whose plan ran out of budget. Explorer parameter `blocked_limit` (2).
Alternatives: ignore new obstacles right beside the UAV in the blocked-path check (would also skip braking for a wall
seen late at speed); widen the planning clearance in tight passages (the passage is genuinely narrow). Why: run
20261003-143243 (E-46 run 5) held by the western junction from 1880 s to the 40 min limit: in a passage with walls
0.7-1.4 m from the track each path to the same goal was blocked within 1-5 s by a wall seen again beside the UAV, and
the replan took the same way (one goal six times in 30 s); the descent to the deep lantern, starting 30 m east, was
never tried before 2284 s.
Reverses if: a goal the run needs is set aside after two blocks and the UAV does not come back to it.

D-45 amended again (E-46 run 6): "shut in" also covers an explore request whose every goal tried failed only because
the start's region was exhausted (D-39 enclosed start). Run 20261003-152153 held 120 s at ⟨x, y, z⟩ in the
first gallery: every goal failed after 300-1800 expansions at every clearance down to 0.75 m, though the saved
navigation map (without the kept hits) is free around the UAV except a few cells 1 m above it.

D-50 — The outdoor rules (sky cylinder D-26, outdoor views D-35, outdoor zone D-38) apply only to goals less than
300 m past the entrance plane (Q-41). Explorer parameter `outdoor_max_depth`. The mouth band (D-40) is unchanged.
Alternatives: a tighter sky test (fraction, height) everywhere (tall chambers and the valley give the same no-return
evidence); per-goal roof evidence from the map (a chamber roof beyond camera range is never seen). Why: with the end-of-run
maps of runs 20261003-134059, -143243 and -153251 the sky test rules out the spots of L1 (2 of 3 runs), L2 (2 of 3),
the deepest lantern (1 of 3) and points of the descent to it (`tools/probes/sky_check.cpp`); run -153251 also logged
an outdoor view at the western junction, 750 m past the plane. In 120 runs the true track was never unroofed more than
234 m past the plane (x ⟨…⟩; reference cave mesh), so 300 m keeps a 66 m margin.
Reverses if: a run goes outdoors more than 250 m past the entrance plane.

D-51 — Opening-first goal order (E-48 probe until adopted; spec docs/superpowers/specs/2026-10-03-opening-tier-design.md).
A frontier bin is open when at least half of up to 4 sampled frontier cells have no occupied cell within 2 m;
26-connected open bins with at least 1000 frontier cells, centroid at least 100 m past the entrance plane and at most
10 m above the nearest flown-track point form an opening. With `opening_tier` on, goals in openings are tried first,
then all others, each group nearest-first as before; every other filter is unchanged.
Alternatives: passage anchoring (E-36), passed-track and lantern penalties (E-43, E-45), all rejected; a global
coverage tour over subspaces (TARE, Cao et al., RSS 2021) - kept for later if D-51 is not enough. Why: nearest-first
spent 26-56 % of exploring time beside old track (`goal_novelty.py`, runs 20261003-134059 to -164224) while the
south-branch entrance and the descent waited; on saved maps large open windows near track height are exactly those
unexplored branches (`openings.cpp`); like GBPlanner's high-gain frontier vertices (Dang et al., Team CERBERUS),
openings stand for volumetric gain and scraps for none.
Reverses if: three runs with the tier find on average no more lanterns than runs 4-8 (2.6) or a safety test fails anew.

D-51 amended (revision 2, after E-48 run 1): an opening is a single frontier bin - at least half of up to 4 sampled
cells open at 1 m, at most 5 % occupied in the 1 m discs one cell beyond them, at least 8 m from the nearest flown-track
point, at most 10 m above it, at least 100 m past the entrance plane; no window size. Chosen on 5094 frontier bins of
five runs labelled with the union of 114 runs' maps (`union_map.cpp`, `frontier_labels.cpp`, `label_stats.py`):
precision 72 %, recall 68 % for "a way on" (at least 2000 never-seen union free cells beyond); the revision-1 window
rule never saw the narrow tunnels towards L1 (run 20261003-174110).

D-51 adopted (E-48): `opening_tier` on by default (ITEM-D-052). Runs 20261003-185202 and -193212 with the revision-2
rule: all four lanterns and back at the entrance in 1931 s and 1651 s; none of the seven E-46 runs before them
(20261003-125758 to -164224, nearest-first) returned with four lanterns within the 40 min limit.

D-45 retired (Q-42, E-50): kept close hits are off by default (`sticky_range` 0; the option and the release remain for
probes). With them on, the UAV was boxed in until the mission failed in E-46 runs 2 and 6 and acceptance series 1
run 3; in E-50 runs 20261003-220107 and -223701 without them there was no stall, both missions completed, and every
close pass since 20261003-204832 was at depth-noise points with no reference surface within 1 m.

D-51 amended: openings start 300 m past the entrance plane (was 100 m). E-48 run 2 (960-1080 s) and E-50 run 2
(20261003-223701, 1080-1200 s) went back to first-gallery pockets 135-265 m past the plane before the descent; the
hook (about 375 m) and everything beyond keep the tier. Reverses if: a run leaves a gallery passage with a lantern
unexplored.

D-52 — Turn rate back to 60 deg/s (D-41 had raised it to 120 deg/s; a_max stays 4 m/s^2). Fact: depth-noise points
within 1.5 m of the track (`tools/probes/phantom_count.py`): 0-2 in the five runs before D-41, more than 0 in 10 of 11
runs after it (8-234), 0 in run 20261003-231614 at 60 deg/s - which passed every sim test (four lanterns by 832 s,
back at 1170 s) and lost 352 s against flying its distance at 4 m/s (426 s in the 120 deg/s run -220107). Every close
pass since 20261003-204832 was at such points. Cause presumed: depth images projected with a pose a few degrees off
while turning fast. Reverses if: noise points near the track return at 60 deg/s.

D-51 amended again: openings count from 100 m past the entrance plane until the flown track has been 400 m past it,
from 300 m after (`opening_min_depth`, `opening_min_depth_deep`, `opening_deep_after`). From 300 m throughout, the
first pass wandered the first gallery nearest-first (34-45 % of the coverage band there) and coverage fell to 85-89 %
(evidence/I5-acceptance-2.md); from 100 m throughout, gallery pockets drew the UAV back later.

Final validation cleanup (2026-10-04): the probe options of experiments that were not adopted are removed with their
tests and launch/run_mission options - heading weight (E-29), region bonus and region tiers (E-32, D-36), passage
mode (D-37, ITEM-D-045 retired), passed-track penalty (E-43), lantern penalty (E-45, with the path planner's lantern
subscription) and far-hit counting (E-46). They were off by default and verified no requirement. Kept close hits
(D-45, ITEM-D-051 retired) stay as an option because the start-shut-in release in the path planner still uses them.

D-53 — Homing from outdoors (ITEM-D-053). While the UAV is less than 300 m past the entrance plane and inside the
outdoor zone of a counted outdoor view (D-38), exploration goals are tried nearest the entrance first; all filters
stay. Explorer parameter `outdoor_homing`. Alternatives: a larger zone (would bar the gallery mouth: the side opening
into the valley lies 20-40 m from it); dropping the D-38 counting conditions (views through the tall mouth would bar
the way in). Why: final-validation run 20261004-143626 explored the mouth for 60 s, left through its side opening and
followed the valley frontier goal by goal - each goal just beyond 30 m of the latest view - for 400 s, then returned
with no lantern. Reverses if: homing pulls the UAV out of a cave passage near the mouth.
