# Reading guide — UAV cave mission

This folder holds the systems-engineering artifacts from one run of se-skills against the UAV cave
mission described in [mission.md](mission.md): CONOPS, requirements, open items, increments,
architecture, evidence and a generated traceability matrix, curated and redacted for publication
(the rules and the excluded files are listed in [REDACTIONS.md](REDACTIONS.md)). The numbers behind
the run — duration, counts, test results — are in [results.md](results.md), each with the source
file and the command or line it comes from. The mission code itself (the ROS 2 packages, their
tests, the launch files) is private and available on request; it is not part of this repository.

## Reading order

Read `se/` in this order:

1. **[CONOPS.md](se/CONOPS.md)** — the mission as the pipeline framed it before any design:
   purpose, use cases, environment, interfaces. Start here for the vocabulary the rest of the files
   use.
2. **[requirements.yaml](se/requirements.yaml)** — 105 requirements, system and item level, each
   with an EARS-style sentence, a criticality, a status and the test or inspection that verifies it.
   Look at how a requirement's `rationale` field carries its own history.
3. **[open-items.yaml](se/open-items.yaml)** — the method's core: every unknown the pipeline found,
   sorted into a customer question (`Q-`), an experiment (`E-`) or a design decision (`D-`), each
   closed with an answer and, where there is one, a link to its evidence. Read a few end to end to
   see an answer change a requirement or a design decision downstream.
4. **[increments.yaml](se/increments.yaml)** — the six increments the mission was built in (I0–I5),
   each its own small V: a goal, the requirements it carries, its exit evidence. I4 is marked
   `failed`; its unmet requirements moved into I5, which verified. The `failure_cause` and
   `moved_out` fields say why and where.
5. **[architecture.md](se/architecture.md)** — the design decisions behind each increment, grouped
   the same way; its "I4 re-plan" section is the pipeline redesigning after I4's failure.
6. **[evidence/](se/evidence/)** — the write-ups behind the experiments and the increment
   inspections and acceptance runs that `open-items.yaml` and `requirements.yaml` point to:
   question, command, raw results, verdict, limits. Only a selection is published; evidence that
   would give away the course challenge's answers is marked "(not published)" where it is cited.
7. **[generated/matrix.md](se/generated/matrix.md)** — the full requirement-to-verification matrix,
   generated from `requirements.yaml`: every requirement with its increment, criticality, method
   and result (`PASS`, `EVIDENCE`, `NESTED`, or `UNVERIFIED` for two retired requirements). This is
   the traceability closure the other files build toward.

Two smaller files are worth a glance after the above: `se/se-config.yaml` (the run's tailoring —
full mode, which model handled which criticality, the review and question budgets) and
`se/review-log.yaml` (blocking and advisory counts per review round, phase by phase).

## Three anchors

- **A customer question, open-items.yaml `Q-25`.** The planner's path-escape zone near a blocked
  start was capped at 1.5 m; after a run stalled with the nearest clear cell about 3.5 m away, the
  pipeline asked the customer to widen it to 3 m, with the replay that justified it. The customer
  approved.
- **An experiment with its evidence, open-items.yaml `E-12`.** Whether the cave lanterns still
  render as pure, exact-colour pixels in the dark, and from what range, decided whether a simple
  colour mask could detect them at all. The full write-up — per-run pixel counts, a detection-range
  table by distance band, and the limits — is [evidence/E-12.md](se/evidence/E-12.md).
- **A requirement changed through change management, requirements.yaml `ITEM-D-016`.** The approved
  answer to Q-25 is folded directly into the requirement text, which now reads "...except points
  within 3.0 m of a start that is itself closer than 1.0 m..."; its `rationale` field names the
  question and the experiment behind the number.

## Figures

[figures/mission-view.png](figures/mission-view.png) — the mission's live view near the end of a
run: the cave outline, the UAV, the lanterns found so far, the current goal and the flown path.
[figures/timeline.png](figures/timeline.png) — commanded speed across one run, by phase (approach,
explore, return), with each lantern report marked on the time axis.
