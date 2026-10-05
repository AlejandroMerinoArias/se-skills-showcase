---
name: se-build
description: Use when se_check.py --route prints ready_to_build or implementing, or when the active increment's validated and allocated requirements need an implementation plan, code and tests
---

# se-build

A thin layer over the superpowers build skills. They do the planning and the coding; this
skill adds the four things they don't know about: **the scope gate, the trace, the
criticality rules, and problem reports**.

**REQUIRED SUB-SKILL:** `superpowers:writing-plans` to write the plan, then
`superpowers:subagent-driven-development` or `superpowers:executing-plans` to run it. Follow
them fully; everything below is added to them.

## Step 1 — the scope gate (before any plan)

```bash
python "${CLAUDE_PLUGIN_ROOT}/scripts/se_check.py" se --route
```

Build only when it prints `ready_to_build` or `implementing`. The scope is the active
increment's requirements.

**A requirement with an unresolved `open_items` entry, or named in the `blocks` of an open
item, never enters a plan.** While the router prints `experiments_open`, `se:experiment` runs
first; building resumes when it prints `ready_to_build` or `implementing` again.

| Rationalization | Reality |
|---|---|
| "I can design around the open value (event-driven, injected callable)." | Then the code encodes a guess about a fact nobody has measured. When the value arrives, the design may be wrong. Measure first; it is usually minutes. |
| "The requirement text has no timing clause, so the item doesn't matter." | The item's `blocks` says it does. Whoever wrote the block knew why. |
| "The user said skip anything that isn't coding." | The trace is how the code gets verified. Without it this increment can never be closed. |

## Step 2 — the plan carries requirement IDs

Every plan task names the requirement IDs it implements, **with their texts**, so the
implementer reads the requirement and not a paraphrase:

```markdown
### Task 3: navigator clearance hold
Implements: SYS-F-002 — "While the robot is moving, the system shall keep at least 0.3 m
between the robot and any person."
```

Every test carries a `VERIFIES:` annotation, which `se_trace.py` reads:

```python
# VERIFIES: SYS-F-002
def test_holds_position_when_person_within_clearance():
    ...
```

```cpp
// VERIFIES: ITEM-D-001
TEST(Navigator, StopsWhenPersonInside096m) { ... }
```

A test with no annotation verifies nothing, as far as the matrix is concerned.

## Step 3 — criticality sets the rigor

Read `models` from `se/se-config.yaml`. A task inherits the **highest** criticality of the
requirements it implements.

| | CRIT-A | CRIT-B | CRIT-C |
|---|---|---|---|
| Implementer model | `models.crit_a` | `models.crit_b` | `models.crit_c` |
| Reviews | spec compliance + code quality, both on `models.crit_a` | one | one, light |
| Before `implemented` | **the user approves** | — | — |

## Step 4 — after each task

```bash
python "${CLAUDE_PLUGIN_ROOT}/scripts/se_trace.py" se --tests <test-dir>
```

Then set `status: implemented` on **each requirement whose task has passed**, as it passes,
not all at the end. The router's stall detector measures progress through those status
changes, so a long build that never moves a status looks stuck.

**A CRIT-A requirement is the exception:** it becomes `implemented` only after the user
approves the double-reviewed change. Until then it stays `validated`. With the user away,
record the approval request as a `customer_question` item owned by the increment
(`blocks:` naming the requirement), and continue with the non-CRIT-A work. When the router
brings the answer back as `items_unapplied`: approved → set the requirement `implemented`;
objections → they become fix tasks. Then set the item `applied`, and `closed` once
`se_check.py se` exits 0.

## Step 5 — problem reports, never silent edits

Implementation often discovers that a requirement is wrong, missing or impossible. **Never
edit requirement text from here.** Instead:

- an unknown fact → a new `experiment` item with `blocks:` set;
- a design choice that must change, or a validated requirement that is contradicted → record
  the evidence as an `experiment` item (`answered`, with its evidence file) and run
  `se_check.py se --mark-suspect <ID>` on the affected requirements. The router then sends the
  project to `se:change-management`, which revisits the D-nn.

## Exit

The increment's buildable requirements are all `implemented`, `se_trace.py` has run, and
`se_check.py se` exits 0. Then hand off to `se:verification`.

The same flow serves a warehouse robot and a trading bot. Only the test harness differs:
simulator runs for one, seeded backtests for the other.

## Red flags — stop

- Code for a requirement whose open item is still open.
- A test without `VERIFIES:`.
- Requirement text edited during a build.
- Every status flipped at once at the end.
- A CRIT-A requirement set to `implemented` without the user's approval.
