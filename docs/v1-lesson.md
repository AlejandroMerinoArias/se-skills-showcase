# The v1 lesson

se-skills v2, the version published in this repository, exists because v1 did not converge. This
page describes v1's design, what happened when it ran on the UAV cave mission, why it stalled, and
the rule in v2 that each failure produced. It is a design lesson, not a controlled comparison: v1
and v2 are different pipelines, run at different times under different rules, and neither is a
baseline for the other. The v1 figures below are the ones in the "v1, for contrast" table of
[results.md](../examples/uav-cave/results.md).

## v1's design: specify fully, then build

v1 was a direct translation of the classical V-model into ten Claude Code skills, totalling 30,746
words of skill text. Its phases followed the left side of the V from the top down: tailoring,
requirements capture, optional domain research, requirements validation against the INCOSE
criteria with a human gate, architecture with allocation of requirements to modules and derived
item-level requirements, then plans, implementation and verification. Two of the skills were
adapted copies of general-purpose planning and implementation skills from the superpowers plugin.

Much of v1 was sound, and v2 keeps it: immutable requirement identifiers, the parent tree from
system to item level, criticality levels A, B and C, a method of verification on every requirement,
`VERIFIES:` annotations that link tests to requirements, the suspect cascade for change control,
and the principle that everything a script can check, a script checks. The requirements v1 wrote
were, on reading, of good quality. The process around them was the problem.

The implicit assumption was that the whole requirement tree, down to the item level, should be
derived and validated before any code was written or any experiment run. That is how the V-model is
often drawn, and on a project where the physics is known in advance it is a reasonable reading.

## The run

v1 ran on the same mission later used for v2: an autonomous quadrotor that must find four lanterns
in a simulated cave, map it, and return to the entrance within 30 minutes (see
[mission.md](../examples/uav-cave/mission.md)). The author acted as the customer.

The run went through 23 phase rounds. It produced 118 requirements (74 at system level and 44 at
item level), and it asked the customer 41 questions. Its artifacts grew to about 1.8 MB: the
requirements file alone reached 622 KB and the concept of operations 731 KB. It wrote no lines of
implementation code and no tests, and it never ran the simulator. The run was closed as "did not
converge"; the pipeline never left the upper half of the V.

## The diagnosis

Three causes explain most of the stall.

**The customer was asked what experiments should answer.** Because the whole tree had to be
specified before anything ran, every unknown fact about the simulator, such as sensor ranges, frame
rates, the behaviour of the provided controller, or how the position estimate is corrupted, had to
be settled on paper. The only party the pipeline could ask was the customer, who did not know
either. The customer's own feedback at the close of the run was that too many questions should
have been answered by experimenting with the simulator rather than by the client.

**One-shot specification.** Deriving everything before running anything meant that every design
decision rested on assumptions nobody could check yet. Each review round therefore had plenty to
question, and each answer opened new derived requirements to review.

**No budgets and no stopping rule.** Reviews re-examined the whole requirement set every round,
with no cap on the number of rounds and no distinction between a finding that blocks progress and a
wording suggestion. An agent reviewer always finds something. The artifacts kept the full history
of every round inside the YAML and used the concept of operations as a running log, so each fresh
agent had to read hundreds of kilobytes before it could start, and agents ran out of context
partway through their phase.

## v1 failure, v2 rule

| v1 failure | v2 rule |
|---|---|
| The whole tree was specified before anything ran. | **Increments.** Work proceeds in small increments, each its own small V: design slice, build, verify, close. Increment 0 is characterization only: no product code, just the experiments that later increments depend on. |
| The customer was asked what the simulator could answer. | **Triage into Q-, E- and D- items.** Every unknown becomes exactly one entry in `open-items.yaml`: a customer question (Q-), an experiment (E-) or a design decision (D-). Only Q- items reach the customer. Experiments are run by the pipeline; design decisions are made by it and recorded with a rationale and a "reverses if" condition. |
| Questions accumulated without limit. | **Question caps:** by default 5 customer questions per gate and 15 in total, and a phase that wants more must show why each extra question is neither an experiment nor a design decision. |
| Reviews re-read everything, with no round limit. | **Diff-only review with a 2-round cap.** A script lists the requirements that changed since the last gate; only those are reviewed. Round 1 may raise blocking and advisory findings, later rounds blocking only, and after round 2 each remaining blocking finding leaves through a fixed exit: an experiment, a customer escalation, or an accepted risk with a one-line note. |
| Artifacts grew until agents could not read them. | **Size budgets.** History lives in git, not in the requirements file. Rationales are capped at about 400 characters, the concept of operations at about 15 KB, and scripts emit a `BLOAT` warning when a limit is exceeded. |
| The pipeline could circle without anyone noticing. | **Stall detector.** Each dispatch is logged with a fingerprint of the artifacts; if the state and the artifacts stop changing, or an increment uses up its dispatch budget, the router stops and hands the choice (continue, cut scope, accept the risk) to the user. |

The budgets above are the defaults written into the case study's
[se-config.yaml](../examples/uav-cave/se/se-config.yaml). How each rule works in practice is
described, with excerpts, in [how-it-works.md](how-it-works.md).

v2 also cut the skill text: the eight v2 skills total 5,813 words, against 30,746 for v1's ten
([results.md](../examples/uav-cave/results.md)). Two forked skills became a thin layer over the
superpowers plugin instead, so v2 follows its updates rather than carrying copies.

## What changed in practice

On the same mission, v2 closed six increments, ran 47 experiments and reached a final validation
with all 93 open items closed ([results.md](../examples/uav-cave/results.md)). That is a
description of one run of a redesigned pipeline, not evidence that v2 is better than v1 or than
working without either: there is no baseline yet. What the contrast does show is that the specific
failure modes observed in v1 (a customer flooded with technical questions, unbounded review, and
artifacts that outgrew the agent's context) did not stop the v2 run. Whether the v2 rules carry
over to other projects is open; see [limitations.md](limitations.md).
