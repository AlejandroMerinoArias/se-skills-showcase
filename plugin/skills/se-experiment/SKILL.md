---
name: se-experiment
description: Use when se_check.py --route prints experiments_open, when an open item of kind experiment needs an answer, or when a fact about a simulator, runtime, dataset or third-party system is unknown and could be measured instead of asked
---

# se-experiment

Answers `experiment` items in `se/open-items.yaml` by **running the system and computing
the answer**. The customer is never asked what a run can measure.

## The item lifecycle

`open` → `answered` (the evidence exists) → `applied` (every requirement or decision
that referenced it is updated) → `closed`. Never jump straight to `closed`: an answer
that nobody applied leaves stale requirements behind it.

## Step 1 — pick the items

```bash
python "${CLAUDE_PLUGIN_ROOT}/scripts/se_check.py" se --route
```

Its reason line names the blocking items. Read each item's `text` and `blocks`, and
the requirements it blocks. The question you answer is the item's question, with
units and a stated criterion.

## Step 2 — write the probe as a bounded script

Every run is a script you save under `tools/probes/E-nn.<ext>`, never a command typed
once and eyeballed. The script must:

1. **Start the system in its own process group** (`setsid` on Linux, a new process group
   on Windows), with all output going to a file.
2. **Wait for readiness on the first real data**, never on "process started" or "the
   channel exists". A topic, socket or queue can exist before anything flows through it.
3. **Enforce a time cap** on the whole run.
4. **Stop the whole group**: interrupt, a short grace period, then kill. Confirm that no
   process is left.
5. **Compute the answer from the recorded data** and print one line:
   `VERDICT: <number with units> (<criterion>)`.

State the criterion before running. For example, "settled = within 2% of the final value
for 1 s", or "slippage = fill price − reference price, mean over all fills".

**Repeat runs** (at least 3) whenever the system has noise, randomness or timing
jitter, and report the mean and the spread. Once is enough only for a deterministic
system you have shown to be deterministic.

## Step 3 — the evidence file

`se/evidence/E-nn.md`, one page at most, with these sections in this order:

```markdown
# E-nn — <question>
## Question
<the item's text, plus the criterion you applied>
## Command
`python tools/probes/E-nn.py --runs 3`
## Raw results
| Run | <measured quantity> | ... |
## Verdict
<the VERDICT line(s), with mean and spread>
## Limits
<what this does not show: model fidelity, ranges not exercised>
```

## Step 4 — update the item, then apply it

1. Set the item's `status: answered`, a one-line `answer` taken from the verdict, and
   `evidence: evidence/E-nn.md`.
2. Apply it to every requirement in `blocks` and every requirement whose `open_items`
   lists this item:
   - **An open value in a requirement with no children, tests or implementation:** fill
     it in and drop the ID from `open_items`.
   - **The answer contradicts or changes a requirement that has children, tests or an
     implementation:** leave the item `answered` and run
     `se_check.py se --mark-suspect <ID>`. The router then sends the project to
     `se:change-management`, which applies the answer.
3. Set `applied`, run `se_check.py se` (it must exit 0), then set `closed`.

## When the run cannot happen

A missing tool, a broken build, or no access: write that as the item's `answer`, keep
it `open`, and report it as the blocker. Never substitute an estimate for a
measurement.

## Examples

| Domain | Item | Probe |
|---|---|---|
| Mobile robot simulator | "What rate does the lidar publish at?" | launch, wait for the first scan, count scans for 20 s, `VERDICT: 10.0 Hz (mean of 3 runs)` |
| Trading backtest | "What slippage does the broker simulator apply?" | run 3 seeded backtests, compute fill − reference per fill, `VERDICT: 0.041 per share mean, 0.004 sd` |

## Red flags — stop

| Thought | Reality |
|---|---|
| "The output is clear, I'll just read it." | Reading is not computing. The next reader cannot check a glance. |
| "One run is enough to be quick." | Speed doesn't change the physics. Noise is exactly what one run hides. |
| "I'll mark it closed, it's answered." | Closed means applied. Check `blocks` first. |
| "The user can tell us the value." | If a run can measure it, the run is the source. |
