# Mission

A simulated quadrotor takes off next to a reference lantern, in open ground, and flies a predefined
waypoint route to a cave entrance I chose when I set the mission up. The instant it first reaches
that point starts a 30-minute clock: from there on, the UAV gets no outside help. It picks where to
fly next from its own sensing alone — depth and stereo cameras, a semantic camera that marks the
lanterns by colour, and a position estimate that the simulator deliberately corrupts with noise. The
true, uncorrupted pose exists in the simulator, but the mission stack is never allowed to read it;
it may only be used, offline, by the tools that score a run afterward.

Inside the cave the UAV has no prior map and no prior lantern positions. It explores until it has
found and reported all four lanterns, each within 2 m of its real position, while building a 3D
representation of the cave as it goes. Every run — whether it finishes cleanly or not — ends with
the lantern positions and the cave representation written to disk, so a run that fails partway still
leaves something to inspect. Once the fourth lantern is reported, the UAV turns back and has to be
hovering at the entrance again within 30 minutes of the clock starting. Through all of this the
simulator itself — the cave geometry, the lantern models, the way the position estimate is corrupted
— is left exactly as given; nothing in the mission stack is allowed to touch it.

The scenario is the Sub-Terrain Challenge of the Autonomous Systems course at the Technical
University of Munich (winter semester 2025). The simulator, the ROS bridge and the controller are
the chair's and are not included.

I had already solved this challenge once, with a team, as part of the course itself. For the run
documented in this folder I deliberately did not look back at that earlier solution — not the code,
not the design decisions we had made, not even my own memory of the specific numbers we had settled
on. The point of this run was to test a systems-engineering workflow for an AI coding agent,
se-skills, against a real, already-graded problem, so the mission had to be built from the brief
alone, under the same rules and in the same simulator, as if for the first time.
