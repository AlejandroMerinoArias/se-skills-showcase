# I4 — Mission view demonstration (SYS-F-022..027)
## Question
Does the mission launch open the live view, and does the view show the cave from above (framed only on data beyond
the entrance plane, redrawn every second), the UAV, the lanterns, the goal and the path? Criterion: the window opens
with `ros2 launch cave_bringup mission.launch.py` and not with `viz:=false`; the snapshot the view saves shows each
element.
## Command
Acceptance runs 20260930-181921/-185730/-193539 (view on, default), E-22 runs with `viz:=false` (no viewer process);
screen capture during run 20260930-031543; the view's own snapshot `<run>/mission_view.png`.
## Raw results
- The window opened in every run with the view on. With `viz:=false`, no viewer process started (E-22 off runs).
- `I4-view-demo.png` (end of run 20260930-193539): top-down cave, height-shaded, framed on the cave beyond the entrance
  only; the UAV arrow; three reported lanterns; the goal cross; the path; the state, time, lantern count and point
  count, redrawn each second.
- A 150 000-point frame renders in under 0.2 s (`test_viewer.py`). Camera rates with the view on were 98 % of those
  with it off (E-22).
## Verdict
VERDICT: SYS-F-022..027 demonstrated in 17 runs; switch-off demonstrated in 3 runs.
## Limits
Shown on one host under WSLg. Snapshot every 10 s; the window itself redraws every second.
