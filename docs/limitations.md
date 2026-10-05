# Limitations

se-skills is an experimental proof of concept, in active development, not a supported tool. This
page sets out what the evidence in this repository does and does not support. The figures quoted
are from [results.md](../examples/uav-cave/results.md), which also has its own section on what the
numbers do not show.

## One case study

All the evidence for v2 comes from a single run on a single mission. There is no second v2 run to
show how much the outcome varies, and no run on a different kind of project. The mission is a
demanding one (autonomous flight in a simulated cave with a deliberately corrupted position
estimate), but it is one simulator, one team of one, and one set of acceptance criteria. Some of
the method's rules were also shaped by the v1 run on the same mission, so the case study is not
independent of the design it tests.

## No baseline yet

Nothing here shows that se-skills does better than an agent working without it, because that run
has not been made. The planned comparison gives the same one-page brief, the same model and the
same session budget to a second run that uses only the general-purpose superpowers skills
(brainstorming, planning, subagent-driven development) and no systems-engineering layer. The two
runs would then be compared on mission success over three consecutive simulator runs, on defects
caught before the simulator against defects found in it, on rework, on cost by model tier, and on
the number of questions put to the customer, with the sealed reference solution as a secondary
judge of requirement coverage.

The baseline is postponed. When it runs, it will run on newer versions of the agent and its
plugins than the v2 run did, and the comparison will have to state that. Until then, v1 is shown
only for contrast as a design lesson ([v1-lesson.md](v1-lesson.md)), not as a baseline.

## The author was the customer

Every customer answer, approval and acceptance call in the case study was made by the author of the
method. He tried to act as a customer would, answering needs and acceptance questions and leaving
design to the pipeline, but a real customer would ask different things, answer at different times
and be less familiar with what the pipeline expects. The customer-question and acceptance figures
reflect one person's judgment.

The question budgets were also not held. The default caps are 5 questions per gate and 15 in
total ([se-config.yaml](../examples/uav-cave/se/se-config.yaml)); the run asked 45 customer
questions. Most were requests to approve criticality-A design statements and changes, which the
method deliberately sends to the customer, but the cap is only a warning in the scripts, and the
run shows that it does not by itself keep the customer's load small.

## Cost and time

The run was expensive by the standards of an individual project. It was one continuous session of
about 42.2 active hours over about 167.2 hours of wall-clock time: roughly a week of a personal
computer running the agent and the simulator. Claude Opus 5.5 produced 2,730,445 output tokens and
read 1,515,415,560 tokens from cache, with a little Claude Sonnet 5 on top
([results.md](../examples/uav-cave/results.md), "Cost"). These totals cover the whole run,
including writing the mission code; they are not isolated to the systems-engineering overhead, and
without a baseline there is no way to say how much of the cost the method added or saved.

## Operator workload

The method moves work from the agent's guesses to the customer's decisions, and that work is real.
The customer had to answer questions at gates throughout the week, approve criticality-A design
statements and implementations, decide what to do when an increment failed, and judge acceptance
runs, which were watched live
([evidence/I5-acceptance-3.md](../examples/uav-cave/se/evidence/I5-acceptance-3.md), Command).
The host machine also needed attention: when the simulator's sensor output stalled periodically,
the agent traced the cause to the host rather than to its own software
([evidence/E-38.md](../examples/uav-cave/se/evidence/E-38.md)), and the fix, disabling a clock
service in the virtual machine, was applied by the operator
([evidence/final-validation.md](../examples/uav-cave/se/evidence/final-validation.md), "Defects
found during final validation"). A long autonomous run is not an
unattended one.

## The blinding hook's false positives

To keep the run blind, a hook restricted which files the agent could read. It worked, but it was
blunt: its blocks were all false positives or necessary denials, mostly text inside inline scripts
read as file paths, and a log file the simulator writes outside the project. None was an attempt to
reach the sealed material. Each block cost the agent a retry, and a hook like this would need to be
more precise before it could be used routinely.

## What the published material leaves out

The artifacts in [examples/uav-cave/se](../examples/uav-cave/se/) are a curated selection,
redacted so as not to give away the course challenge's answers
([REDACTIONS.md](../examples/uav-cave/REDACTIONS.md)). The mission code is private and available on
request. The defect categories in [results.md](../examples/uav-cave/results.md) come from how each
fix was tagged during the run, not from an independent audit.

## Next steps

- **Run the baseline** described above, on the same brief, and compare.
- **A second domain.** Apply the method to a project that is not a UAV mission, with a customer who
  is not its author.
- **A lighter mode for smaller projects.** Full mode is the default because the method targets
  heavy engineering projects. A lite mode exists in the scripts but was not tested in this run; a
  smaller project needs a version whose overhead matches its size.
- **Tighter question budgeting**, so that approvals of critical work are batched rather than asked
  one at a time.
