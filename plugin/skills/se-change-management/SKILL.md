---
name: se-change-management
description: Use when se_check.py --route prints suspects_pending, when a measured fact or answered item contradicts a validated requirement, when the user asks to change a requirement that already has downstream work, or when an implementer files a problem report
---

# se-change-management

Changes validated requirements **without losing the thread**: the change is marked, only the
affected subtree is re-examined, and it is resolved at the decision that caused it.

## Arrivals

| Arrival | First move |
|---|---|
| `suspects_pending` | The flags are already set. Go to Step 2. |
| An `answered` item contradicts a requirement (for example, a measured maximum below a derived speed) | Step 1 |
| The user asks to change a requirement | Step 1 |
| A problem report from `se:build` | Step 1, with the report as the evidence |

## Step 1 — make the change visible before making it

```bash
python "${CLAUDE_PLUGIN_ROOT}/scripts/se_check.py" se --mark-suspect <ID> [<ID> ...]
```

List every requirement whose text will change. The script marks each one and its whole
downstream subtree `suspect: true`. Never set `suspect` by hand: the script computes the
subtree, and you would miss part of it.

## Step 2 — read the subtree, and only the subtree

The suspect set is the scope: each suspect requirement, its parent, its D-nn, and its tests
(`verified_by`). Nothing else is re-opened.

## Step 3 — resolve at the level of the invalidated decision

A derived requirement exists because of a decision (the D-nn in its rationale). When a fact
breaks it:

1. **Revisit the D-nn** in `architecture.md`. State what the new fact does to the decision's
   goal, for example: "a 40 ms sensor latency leaves 15 ms of the 55 ms control budget". Then
   record the revised or replacing decision, with its alternatives.
2. **Redesign the derived requirement(s)** to match. Splitting one into two is allowed. The
   old ID stays, retired if the requirement is replaced.
3. **The top-level need changes only on the user's word.** If no design meets the need any
   more, that is the one question that goes to the user: whether to relax the need or
   fund the redesign. It is a `customer_question` item.
4. **A measured fact is never a customer question.** The measurement stands.

For example: a trading bot whose derived position limit assumed a fill model that a backtest
disproved gets its sizing decision revisited. The customer's drawdown limit stays as it is.

## Step 4 — close the change

1. Clear `suspect` only on the requirements you actually re-examined.
2. Refresh the snapshot so the next change compares against this one:

   ```bash
   python "${CLAUDE_PLUGIN_ROOT}/scripts/se_trace.py" se
   ```

3. Anything already `implemented` or `verified` in the affected subtree goes back to
   `validated`, to be rebuilt and re-verified. The rest of the matrix is untouched. The router
   only sees the active increment, so a requirement from an increment that is already closed
   moves into the active increment: its `increment` field, and for a top-level requirement
   the `requirements` lists in `increments.yaml`. Closed increments are never reopened.
4. Move the triggering item to `applied`, and then to `closed` once `se_check.py se` exits 0.

## Exit

`se_check.py se --route` no longer prints `suspects_pending`, and `se_check.py se` exits 0.
Then hand off to what the router names next.

## Red flags — stop

- `suspect: true` typed by hand.
- A requirement's number changed while its D-nn still says the old number.
- A top-level requirement edited without the user.
- Re-verifying requirements outside the suspect subtree.
