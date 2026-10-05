# Motivation

## The problem: an agent on a long engineering project

AI coding agents are good at bounded tasks: fix this function, add this endpoint, write a test for
this case. A heavy engineering project is a different kind of task. It runs for days, it involves
hardware or a simulator whose behaviour nobody has measured yet, and it ends with an acceptance test
that someone other than the developer defines. On a project like that, an agent left to its own
habits tends to fail in one of two ways.

- **One-shot specification.** The agent reads the brief, decides what the system is, and builds
  it. Every assumption it made on the first day is frozen into the code. When the simulator
  disagrees with an assumption, the disagreement shows up as a failing run late in the project,
  with no record of which assumption was wrong or which parts of the design depended on it.
- **Drift.** The agent works in many short steps, each locally sensible. After a few days nobody
  can say which requirement a given piece of code serves, whether the acceptance criteria are still
  the ones the customer gave, or which changes were agreed and which simply happened.

Both are familiar to anyone who has worked on a student satellite or a UAV team. They are not
specific to AI; they are what happens to any engineering effort without a process. The difference
is that an agent produces code at a high rate, so it reaches the point where the missing
process hurts much sooner.

## What systems engineering adds

Systems engineering is the discipline aerospace uses to keep large, long projects coherent. The
parts that matter here are standard material in any systems-engineering course:

- **Requirements with acceptance criteria.** Each requirement is a single, verifiable statement
  with an identifier, written to the quality criteria of INCOSE (the International Council on Systems
  Engineering): necessary, unambiguous, verifiable, singular, and so on. Here it is also written in
  EARS form (Easy Approach to Requirements Syntax), a small set of sentence templates such as
  "When ..., the system shall ...". Each one also
  carries a criticality level that sets how much review it gets.
- **Verification methods.** Every requirement states how it will be shown to be met: test,
  analysis, inspection or demonstration. "Done" then has a definition other than "the code runs".
- **Traceability.** Requirements form a tree from mission need to design-level statements, and
  every leaf points to the test or evidence that verifies it. A generated matrix shows, for each
  requirement, whether that evidence passed.
- **Change control.** When a requirement changes, everything downstream of it (child requirements,
  design decisions, tests) is marked suspect and re-examined, and only that subtree is re-examined.
- **The V-model.** Decomposition on the left side (needs, system requirements, design), integration
  and verification on the right side, with each level of the right verifying the matching level of
  the left.

An agent can do all of this. The hard part is making it do it consistently, at reasonable cost, and
without the process becoming the work.

## Why it must be adapted for an agent

Taking a textbook systems-engineering process and handing it to an agent does not work as it
stands. The first version of this project tried that and stalled; the full story is in
[v1-lesson.md](v1-lesson.md). Three differences between a human team and an agent explain most of
what had to change.

**Documents cost differently.** For a human team, a document is written once and read occasionally.
For an agent, every document is re-read on every task, because the agent starts each task with no
memory beyond what is on disk. A requirements file that grows with every review round is read in
full, again and again, and eventually crowds out the work itself. In v1 the run's artifacts grew to
about 1.8 MB before any code existed ([results.md](../examples/uav-cave/results.md), "v1, for
contrast"). The adapted method therefore keeps history in git rather than in the artifacts, caps the
size of rationales and of the concept of operations, and lets scripts warn when an artifact
outgrows its budget.

**Someone must decide who answers which question.** A human engineer who does not know the
latency of a sensor goes and measures it. An agent that does not know tends to ask, and in a
systems-engineering frame the obvious person to ask is the customer. But the customer does not know
the sensor latency either; only the system does. The adapted method sorts every unknown into one of
three kinds before anything is asked: a **customer question** (only the customer can know it: a
mission need, a priority, an acceptance criterion), an **experiment** (running the system or the
simulator, or reading the provided code, can answer it), or a **design decision** (a choice between
ways of meeting a need, which the agent makes and records). Only the first kind reaches the
customer.

**Context is limited, and so is patience.** An agent's working context holds a bounded amount of
text, and a review performed by an agent will always find one more thing to improve. A process with
no stopping rule therefore never stops. The adapted method bounds every loop: reviews cover only
what changed since the last gate, a review phase has at most two rounds, customer questions are
budgeted per gate and in total, and a script detects when the pipeline is making no progress and
hands the decision to the user.

## What this repository tries to show

The repository presents se-skills, a set of Claude Code skills (instruction files that Claude
Code, Anthropic's coding agent, loads when a task matches them) and helper scripts that implement
the adapted method, and one case study in which the method carried an autonomous UAV mission in a
simulated cave from a one-page brief to a delivery that passed its final validation and met the
customer's acceptance rule of 2 successful simulator runs out of 3. It is an experimental proof of concept,
not a supported tool: there is one case study, no baseline run of the same brief without the
method, and the author of the method was also the customer. Those limits are set out in
[limitations.md](limitations.md).

The numbers from the case study, each with its source file, are in
[results.md](../examples/uav-cave/results.md). How the pipeline works, with excerpts from the
case-study artifacts, is in [how-it-works.md](how-it-works.md). How the skills themselves were
tested is in [testing-the-skills.md](testing-the-skills.md), and who did what is in
[how-this-was-built.md](how-this-was-built.md).
