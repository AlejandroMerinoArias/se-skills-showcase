# Redactions

The artifacts in `se/` are the v2 run's files, unchanged except for these rules:

1. Every world-frame coordinate triple is replaced by `⟨x, y, z⟩`, and single-axis world values by
   `x ⟨…⟩`. The entrance and the approach route are included, so one rule covers everything.
   Distances, timings and counts are unchanged.
2. References to evidence that is not published are marked "(not published)".
3. Local paths and course-owned material are not included.

Not published: E-05, E-10, E-19, and every other file derived from the simulator's scene files. They hold the
lanterns' reference positions and the cave geometry, which the test harness used only to score
runs; publishing them would give away the answers to a course challenge. Only a selection of the
run's evidence files is included.
