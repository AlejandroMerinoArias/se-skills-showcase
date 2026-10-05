# Testing the skills

## Why prompts need tests

A skill is a document that an agent reads and is expected to follow. It is, in effect, a
specification for the agent's behaviour, and like any specification it can be wrong in two ways:
it can fail to prevent the behaviour it was written against, or it can contain rules against
problems that never occur, which cost reading time on every task and dilute the rules that matter.
Reading a skill and finding it sensible says nothing about either. The only way to know whether a
skill changes what an agent does is to watch an agent work with and without it.

There is a second reason. Agents under pressure rationalize: told to "just get it done", an agent
produces a reasonable-sounding argument for skipping a step. A skill that does not answer that
specific argument is ignored exactly when it was needed, so the arguments have to be observed
before they can be countered.

## The method: RED, then GREEN

Each v2 skill was developed with a pressure-test method adapted from the superpowers plugin's own
guidance for writing skills.

1. **Write the scenario.** A short task, set in a fixture project (a small throwaway project
   prepared for the test), designed to provoke one
   specific failure, for example a review that has already used its two rounds and a user asking
   for a third.
2. **RED.** A subagent (a fresh agent instance started for one task) receives the scenario with no skill and no mention of systems
   engineering. Its answer is recorded verbatim, including the arguments it gives.
3. **Check the control.** If the baseline agent does not show the failure, there is nothing to fix:
   the scenario is dropped and the skill gets no rule for it. Writing guidance against a failure
   nobody observed is how skills fill up with counters to imagined problems.
4. **Write the skill** against the arguments actually recorded. Every rationalization in the
   baseline must have a counter in the skill, and every counter must trace either to a recorded
   sentence or to required content in the design.
5. **GREEN.** The same scenario, the same model, now with the skill. The agent must pass.
6. **Refactor**, at most twice, if GREEN shows a new loophole; a scenario still failing after that
   is reported rather than softened.

Scoring is on **artifacts on disk**, not on what the agent says. A pristine copy of the fixture is
kept and the agent's working copy is compared against it afterwards. A skill that hands the agent a
paragraph to recite makes its speech weak evidence; the files it wrote are not recitable.

The subject runs under a fixed wrapper, identical in RED and GREEN except for the sentence that
points to the skill. Each clause exists because its absence spoiled an earlier run: subjects
recognised an evaluation from their folder name, or loaded an older installed skill of the same
name. Such runs were discarded, recorded with the reason, and repeated.

## Unrelated domains keep the case study blind

None of the pressure tests uses a UAV, a cave or a simulator of one. The fixtures are a warehouse
picking robot, a trading backtest bot and a conveyor simulator. This was deliberate: the UAV
mission was reserved for the case study, and testing on it would have let details of the mission
leak into the skill text. A skill that only works in its own domain has learned the domain, not the
method. The skills
themselves use the warehouse robot and the trading bot as their worked examples, for the same
reason (see, for example, [se-increment](../plugin/skills/se-increment/SKILL.md)).

## Two failures the tests caught

**A design choice sent to the customer.** In the requirements scenario, a trading-bot project had
two unknowns: the slippage of the broker simulator, and the choice of strategy. The baseline agent
handled slippage well, by running the simulator. It then put the strategy to the customer as one
of the "business/risk calls that no amount of running the simulator settles", recorded no open
items, and wrote its open questions into the concept of operations as free text. Choosing how to meet a need
is a design decision, not a customer question. The skill's rationalization table now answers that
exact argument ("Strategy A or B is a business call, so I'll ask"), and the GREEN agent recorded the
strategy as a design decision with its reasons, measured the slippage as an experiment with an
evidence file, and asked the customer only about the drawdown limit and what to do on a breach, which only
the customer can know. The same scenario family caught a third review round being run "manually" and advisory
wording fixes being applied as if they were required changes; both are now red flags in
[se-requirements](../plugin/skills/se-requirements/SKILL.md).

**An experiment answered by eye.** In the experiment scenario, an agent had to find the settling
time of a simulated conveyor. The baseline agent ran the simulator once, read the printed speed and
wrote that it was "effectively settled" after roughly seven to eleven seconds. There was no stated
criterion, no raw data kept and no computed result, and the item went straight to closed without
the blocked requirement being revisited. The agent noticed it had run only once and left that to
the user. The [se-experiment](../plugin/skills/se-experiment/SKILL.md) skill now requires a saved,
bounded probe script, a criterion stated before the run, at least three runs where there is noise,
a computed `VERDICT:` line and an evidence file with fixed sections. The GREEN agent produced all of
them. The same structure is visible in the case study, for example in
[E-12](../examples/uav-cave/se/evidence/E-12.md).

The control check also did its job. In the change-management scenario the baseline agent, without
the skill, traced a measured fact back to the design decision it invalidated and handled it
correctly. The scenario was dropped, and that skill was written from its required content only,
with no rationalization table.

## Routing

A separate probe checked that the skills' one-line descriptions, which are what an agent sees when
choosing a skill, route ordinary messages such as "We don't know the sensor's real update rate yet"
to the right skill, including when competing general-purpose skills are listed beside them.

## The scripts' own tests

The scripts are ordinary code and are tested as such. The published plugin carries its pytest
suite in [plugin/scripts/tests](../plugin/scripts/tests/): 436 tests, which pass with
`python -m pytest scripts/tests` run from `plugin/`. They cover the schema, the checks, the
traceability matrix and the strict gate, the open-items lifecycle, the router's states, the stall
detector and the size budgets. A few tests also check the skill files themselves, for example that
the router's routing table names every state the router script can print.

## What this does not establish

Pressure tests show that a skill changes behaviour in the scenarios tested, with one subagent per
scenario and one model. They do not show that the skills hold over a week-long project; that is
what the case study is for, and it is a single run. See [limitations.md](limitations.md).
