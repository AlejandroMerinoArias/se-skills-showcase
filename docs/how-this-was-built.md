# How this was built

This project was built by one person working with an AI coding agent. Because the subject of the
project is precisely how an agent should be directed on an engineering task, it matters to state
clearly who did what.

## Roles

**Alejandro Merino Arias** (author, aerospace engineering student) designed the method and its
rules, wrote and ran v1, diagnosed why it stalled, set the direction of v2, designed the experiment
used to evaluate it, and made every customer decision in the case study. These pages were drafted
by Claude Code and read by him before publication.

**Claude Code** (Anthropic's coding agent, running Claude Opus 5.5) drafted the skill text, the
Python scripts and their tests, and these documentation pages, under that direction. In the case
study it also ran the pipeline itself: it wrote the systems-engineering artifacts, ran the
experiments in the simulator, and wrote all of the mission code. A small number of turns in the
run used Claude Sonnet 5 ([results.md](../examples/uav-cave/results.md)).

The division is the one the method itself assumes: the human owns needs, priorities, acceptance
and direction; the agent does the engineering work and records it so the human can check it.

## Decisions on the method

**Full mode is the default.** se-skills has a lighter mode with fewer artifacts. The author ruled
that full mode, with a concept of operations, an architecture and per-increment design, is the
default and lite mode is used only on explicit request, because the method targets heavy
engineering projects. It is written into the
[se-tailoring](../plugin/skills/se-tailoring/SKILL.md) skill ("Mode is `full` unless the user
explicitly asks for lite").

**Questions an experiment can answer never go to the customer.** This was the author's reading of
v1's stall (see [v1-lesson.md](v1-lesson.md)): as the customer of that run he had been asked, again
and again, things that only the simulator knew. He made it a rule rather than a preference, and it
became the triage of every unknown into customer question, experiment or design decision, and the
line in [se-experiment](../plugin/skills/se-experiment/SKILL.md): "The customer is never asked what
a run can measure."

**Bounded loops.** The round cap on reviews, the question budgets, the size budgets and the stall
detector all came out of the v1 diagnosis. Their default values are in the case study's
[se-config.yaml](../examples/uav-cave/se/se-config.yaml).

## The experiment design

The author designed the validation so that the case study would mean something even as a single
run.

- **A blind run.** He had solved the same course challenge earlier with a team. The pipeline did
  not see that solution: not its code, its design decisions or its numbers. As customer he also did
  not draw on it; [mission.md](../examples/uav-cave/mission.md) describes this in his own words.
- **A reference solution kept out of reach.** A reference solution, extracted from the earlier work, was sealed
  before the runs, to be opened only once, as the judge of a final comparison, so that the method could not
  be tuned to it. File access during the run was restricted by a hook, so the agent could not reach
  the reference or the earlier solution.
- **A planned baseline.** The design calls for a second run of the same brief, with the same model
  and budget, using only the general-purpose superpowers skills (brainstorming, planning,
  subagent-driven development) and no systems-engineering layer. That baseline is postponed; see
  [limitations.md](limitations.md).

## Decisions as the customer

In the run, the author answered every customer question and made every acceptance call. Three
examples show the kind of input that the method reserves for the customer.

**A 2-minute no-movement failure rule.** During the run he added a failure rule for a UAV that stops
making progress, recorded verbatim as the source of the system
requirement it produced
([requirements.yaml](../examples/uav-cave/se/requirements.yaml#L1148)):

> 'if the UAV does not move for more than 2 minutes, mission is considered automatically as failed'

The pipeline turned that into a precise, testable requirement (a 1.0 m window over any 120 s
stretch) and checked the reading with him through question Q-10
([open-items.yaml](../examples/uav-cave/se/open-items.yaml#L267-L279)) before building it.

**No fixed altitude ceiling.** After a long exploration run climbed high above the entrance and
touched the cave, the pipeline proposed a hard limit on height. He rejected it
([open-items.yaml](../examples/uav-cave/se/open-items.yaml#L420-L421)):

> 'Customer rejects a fixed ceiling and approves the revised ITEM-D-031: only camera-revealable
> (horizontal) frontiers, vertical travel weighted 3x.'

A fixed ceiling would have worked in this cave and broken in another; the revised rule addresses
the cause (the camera cannot see what lies above and below a steep climb).

**A live mission visualization.** He asked for a simple live view of the mission, which became six
system requirements, a demonstration
([evidence/I4-view-demo.md](../examples/uav-cave/se/evidence/I4-view-demo.md)) and the figure in
[figures/mission-view.png](../examples/uav-cave/figures/mission-view.png). The request as recorded
([requirements.yaml](../examples/uav-cave/se/requirements.yaml#L2024)):

> 'a simplified visualization of the current state of the mission ... launch at the same time as
> the simulation ... top vision of the entire cave (only the cave) ...'

These are customer decisions in the systems-engineering sense: needs and acceptance criteria. The
design that met them (the window length, the frontier weighting, the drawing of the map) was the
pipeline's, recorded as design decisions in
[architecture.md](../examples/uav-cave/se/architecture.md).

## What was not done by hand

The mission code, the tests, the experiments and the artifacts in
[examples/uav-cave/se](../examples/uav-cave/se/) were produced by the agent through the pipeline.
His input reached the run through the brief, answers to customer questions and approvals at
gates. The artifacts here are those files, curated and
redacted for publication as described in
[REDACTIONS.md](../examples/uav-cave/REDACTIONS.md).
