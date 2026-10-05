# Results

One run, 2026-09-28 to 2026-10-05, one continuous session, Claude Opus 5.5 (with a little Claude
Sonnet 5 on some turns), se-skills 0.5.0. This is a single case study: there is no control run and
no repeated trial, so nothing here is a comparative claim. Every number below names the file it
came from and the command (or line) that reproduces it. Commands are given to run from this
directory (`examples/uav-cave/`) against the files published alongside this page; sources that are
not part of this repository (the full run transcript and its metrics file) are named but not linked.

## Outcome — acceptance series 3

The customer's five success criteria (brief section 5), checked over three consecutive simulation
runs, the gate for requirement `SYS-P-005`.

| Metric | Value | Source | Command / line |
|---|---|---|---|
| Runs in the series | 3 | [se/evidence/I5-acceptance-3.md](se/evidence/I5-acceptance-3.md) | "Raw results" table |
| Run 1 — back at entrance / map coverage / sim tests | 1529 s / 94.1% / 11 of 12 | [se/evidence/I5-acceptance-3.md](se/evidence/I5-acceptance-3.md) | row `20261004-022644` |
| Run 2 — back at entrance / map coverage / sim tests | 1556 s / 92.5% / 12 of 12 | [se/evidence/I5-acceptance-3.md](se/evidence/I5-acceptance-3.md) | row `20261004-025909` |
| Run 3 — back at entrance / map coverage / sim tests | 1695 s / 91.3% / 12 of 12 | [se/evidence/I5-acceptance-3.md](se/evidence/I5-acceptance-3.md) | row `20261004-033151` |
| Runs meeting all five criteria | 2 of 3 (runs 2 and 3) | [se/evidence/I5-acceptance-3.md](se/evidence/I5-acceptance-3.md) | "## Verdict" |
| Largest tracking deviation from set-point, the three runs | 0.54 m, 0.48 m, 0.57 m | [se/evidence/I5-acceptance-3.md](se/evidence/I5-acceptance-3.md) | "Contact" paragraph |

Mission times above are seconds elapsed since the UAV first reached the cave entrance.

## Outcome — final validation

A fourth, independent set of runs on the delivered build, after the acceptance series above.

| Metric | Value | Source | Command / line |
|---|---|---|---|
| Nominal run — back at entrance / map coverage | 1511 s / 92.9% | [se/evidence/final-validation.md](se/evidence/final-validation.md) | row `20261005-164436 nominal` |
| Unit tests | 255 tests, 0 failures | [se/evidence/final-validation.md](se/evidence/final-validation.md) | "Results" bullet |
| Combined test cases (unit + 3 final sim runs) | 353 cases, 0 failures | [se/evidence/final-validation.md](se/evidence/final-validation.md) | "Results" bullet |
| CONOPS use cases demonstrated | 6 of 6 | [se/evidence/final-validation.md](se/evidence/final-validation.md) | "## CONOPS use cases" |
| Strict traceability gate | clean: 71 PASS, 24 EVIDENCE, 8 NESTED, 2 retired; no unverified requirement | [se/evidence/final-validation.md](se/evidence/final-validation.md) | "## Strict gate" |
| Open items remaining | 0 (all 93 closed) | [se/evidence/final-validation.md](se/evidence/final-validation.md) | "## Open items" |

## Process

| Metric | Value | Source | Command |
|---|---|---|---|
| Increments | 6 (I0–I5) | [se/increments.yaml](se/increments.yaml) | `grep -c "^- id: I" se/increments.yaml` |
| Increments verified | 5 | [se/increments.yaml](se/increments.yaml) | `grep -c "status: verified" se/increments.yaml` |
| Increments failed, then re-planned | 1 (I4; its unmet requirements moved into I5, which verified) | [se/increments.yaml](se/increments.yaml) | `grep -c "status: failed" se/increments.yaml`, and the `I4`/`I5` entries |
| Requirements, total | 105 | [se/requirements.yaml](se/requirements.yaml) | `grep -c "^- id:" se/requirements.yaml` |
| Requirements, system level (SYS-) | 51 | [se/requirements.yaml](se/requirements.yaml) | `grep -c "^- id: SYS-" se/requirements.yaml` |
| Requirements, item level (ITEM-) | 54 | [se/requirements.yaml](se/requirements.yaml) | `grep -c "^- id: ITEM-" se/requirements.yaml` |
| Requirements by criticality A / B / C | 50 / 45 / 10 | [se/requirements.yaml](se/requirements.yaml) | `grep -c "criticality: A" se/requirements.yaml` (and B, C) |
| Requirements by status | 94 verified, 8 implemented, 3 retired (the 8 implemented are the 8 `NESTED` parents in [generated/matrix.md](se/generated/matrix.md), carried by their verified children) | [se/requirements.yaml](se/requirements.yaml) | `grep -c "status: verified" se/requirements.yaml` (and implemented, retired) |
| Open items, total | 93 | [se/open-items.yaml](se/open-items.yaml) | `grep -c "^- id:" se/open-items.yaml` |
| Open items by kind | 47 experiments, 45 customer questions, 1 design decision | [se/open-items.yaml](se/open-items.yaml) | `grep -c "kind: experiment" se/open-items.yaml` (and customer_question, design_decision) |
| Open items by status | 93 closed, 0 open | [se/open-items.yaml](se/open-items.yaml) | `grep -c "status: closed" se/open-items.yaml` |

## Defects

Fix commits during the run, grouped by how the defect was found, as tagged in the run's own commit
history.

| Metric | Value | Source | Line |
|---|---|---|---|
| Fix commits, total | 72 | run metrics (metrics.json) | `history.fixes` (56 + 10 + 6) |
| ...found in simulation runs | 56 | run metrics (metrics.json) | `history.fixes.sim` |
| ...found in review | 10 | run metrics (metrics.json) | `history.fixes.review` |
| ...found another way | 6 | run metrics (metrics.json) | `history.fixes.other` |
| Rework lines (lines changed walking an artifact backward) | 611 | run metrics (metrics.json) | `history.rework_lines` |

## Cost

| Metric | Value | Source | Line |
|---|---|---|---|
| Sessions | 1 | run metrics (metrics.json) | `cost.sessions` |
| Active minutes | 2530.6 (about 42.2 hours) | run metrics (metrics.json) | `cost.active_minutes` |
| Wall-clock minutes (span of the one session) | 10030.3 (about 167.2 hours) | run metrics (metrics.json) | `cost.wall_minutes` |
| Commits | 283 | run metrics (metrics.json) | `history.commits` |
| Tokens, Claude Opus 5.5 | input 7,504; output 2,730,445; cache write 11,471,400; cache read 1,515,415,560 | run metrics (metrics.json) | `cost.per_model["claude-opus-5-5"]` |
| Tokens, Claude Sonnet 5 | input 70; output 440; cache write 542,803; cache read 2,794,830 | run metrics (metrics.json) | `cost.per_model["claude-sonnet-5"]` |

## v1, for contrast

v1 and v2 are two different pipeline designs run at two different times; this is not a controlled
comparison (see "What these numbers do not show" below).

| Metric | v1 | v2 (this run) | Source |
|---|---|---|---|
| Rounds / increments | 23 phase rounds, did not converge | 6 increments, all closed | v1 run log, closing entry; [se/increments.yaml](se/increments.yaml) |
| Requirements | 118 (74 system-level, 44 item-level; 99 validated, 10 draft, 9 retired) | 105 (51 system-level, 54 item-level; 94 verified, 8 implemented, 3 retired) | v1 run log, closing entry; [se/requirements.yaml](se/requirements.yaml) |
| Customer questions | 41 (Q1–Q41) | 45 | v1 run log, closing entry; [se/open-items.yaml](se/open-items.yaml) |
| Experiments run | 0 (the simulator was never run by the pipeline) | 47 | v1 run log, closing entry; [se/open-items.yaml](se/open-items.yaml) |
| Lines of implementation code / tests | 0 / 0 | out of this file's scope (the delivered mission passed 353 test cases, 0 failures, at final validation) | v1 run log, closing entry; [se/evidence/final-validation.md](se/evidence/final-validation.md) |
| Skill text | 10 skills, 30,746 words | 8 skills, 5,813 words | dev repo, `docs/specs/2026-09-27-se-skills-v2-design.md`; [plugin/skills/*/SKILL.md](../../plugin/skills/) (`wc -w plugin/skills/*/SKILL.md`, run from the repository root) |
| Run artifact size | `requirements.yaml` 622 KB + `CONOPS.md` 731 KB + run log 507 KB = 1,860 KB (about 1.8 MB) | not measured the same way (this run's `se/` is curated and redacted for publication, not a size-for-size match) | v1 run log, closing entry |

## What these numbers do not show

This is one run. There is no second v2 run to check for variance, and no run of the same brief
without se-skills, so there is no baseline for what either number would have been otherwise — v1 is
shown above for contrast, not as that baseline: it is a different, earlier pipeline design, run
under different rules (it was closed for not converging, before reaching a working mission). The
author was also the customer for every decision, answer and acceptance call recorded above, so the
customer-question and acceptance numbers reflect one person's judgment, not an independent client.
The defect categories (simulation, review, other) are read from how each fix's own commit was
tagged during the run, not from an independent audit. The cost and token figures are totals for the
whole run, which includes writing the mission code as well as the systems-engineering artifacts
above; they are not isolated to one or the other.
