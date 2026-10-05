---
name: se-verification
description: Use when se_check.py --route prints increment_unverified or final_validation, when implemented requirements need their verification established, or when deciding whether an increment or the whole system meets its requirements
---

# se-verification

Establishes, from evidence, whether each requirement of the active increment is met. It
then closes the increment, or puts the decision to the user when it is not met. At the end
it runs the final validation against the CONOPS.

## Step 1 — evidence per method of verification

| `moc` | Evidence |
|---|---|
| `test` | `python "${CLAUDE_PLUGIN_ROOT}/scripts/se_trace.py" se --tests <dir> --results <junit.xml>`: linked tests must pass. |
| simulator or runtime check | Either a test (a bounded `sim_command` run wrapped as a test that carries `VERIFIES:` and writes JUnit results, then as `test`), or `moc: demonstration` with an evidence file in `se:experiment`'s template. |
| `analysis`, `inspection`, `demonstration` | An evidence file in `se/evidence/`, referenced from `verified_by`. An inspection note is signed off by the user. |

**`status: verified` means the evidence passed.** A requirement whose evidence *failed*
stays `implemented`, and its `verified_by` stays as it was. A reference to failed evidence
reads as proof to every later reader.

Waivers are the **user's** decision only, recorded in `waiver` with a reason.

## Step 2 — close the increment, or hand it to the user

Every requirement of the increment is `verified` or waived: set the increment's
`status: verified` and `exit_evidence`. **I0** has no requirements and closes when all its
experiments are `closed`.

**Anything failed: stop and put the decision to the user.** Present:

1. the results, requirement by requirement, with the evidence file;
2. the two options:
   - **re-plan** the increment: back to `se:increment` with the failure as input;
   - **fail it and move on**: `status: failed` with a `failure_cause`, and the next increment
     becomes active.

Write nothing to `increments.yaml` until the user chooses. With the user unavailable, the
project waits: record the pending choice as a `customer_question` item owned by the increment,
and stop.

When the router brings the answer back as `items_unapplied`:
- **fail it:** set the increment `status: failed` with `failure_cause`, and the next increment
  `status: active`;
- **re-plan:** each failed derived child goes back to `draft`, and each failed top-level
  requirement keeps `validated` but loses `allocated_to`. The router then returns to
  `increment_design`, where `se:increment` redesigns with the run evidence as input.

Then set the item `applied`, and `closed` once `se_check.py se` exits 0.

| Rationalization | Reality |
|---|---|
| "The evidence clearly shows failure, so failing it is not a judgment call." | Whether it failed is evidence. What to do next — spend another round or cut the scope — is the user's call. |
| "Experiment-answerable questions don't wait for the customer." | That rule is about *facts*. Accepting a failure and moving on is a scope decision, not a fact. |
| "The customer isn't around, so I'll keep the project moving." | A project that moves past a failed safety requirement without its owner has not moved forward. |

Defects found while verifying are not `D-` items (those are design decisions). A defect goes
back to `se:increment` through the re-plan option, or into `se:change-management` if a
requirement itself is wrong.

## Step 3 — final validation (state `final_validation`)

1. Demonstrate each CONOPS use case end to end, for example a full pick order delivered in the
   warehouse simulator, or a 30-day backtest producing its report.
2. Run the strict gate:

   ```bash
   python "${CLAUDE_PLUGIN_ROOT}/scripts/se_trace.py" se --tests <dir> --results <junit.xml> --strict
   ```

3. List every item in `open-items.yaml` that is not `closed` or `accepted_risk`, including
   orphans owned by `setup` or by a finished increment. The user decides each one.
4. Record the result in `increments.yaml`:

   ```yaml
   final_validation:
     date: "2026-10-12"
     result: all use cases demonstrated; strict gate clean
     evidence: evidence/final-validation.md
   ```

## Red flags — stop

- `status: failed` written without the user's choice.
- `verified_by` pointing at evidence that failed.
- `verified` set on the strength of a green run whose tests carry no `VERIFIES:`.
- Final validation recorded with open items unlisted.
