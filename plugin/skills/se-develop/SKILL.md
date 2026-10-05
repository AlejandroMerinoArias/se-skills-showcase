---
name: se-develop
description: Use when a project has an se/ directory and the next systems-engineering step must be decided, when resuming an SE project after a break or a crash, or when the user asks what to do next or to keep working on such a project
---

# se-develop

The router. It asks the scripts where the project is, dispatches the one phase that owns
that state, and stops where the user must decide. It does no phase work itself.

## The two commands

```bash
python "${CLAUDE_PLUGIN_ROOT}/scripts/se_check.py" se --route            # look (writes nothing)
python "${CLAUDE_PLUGIN_ROOT}/scripts/se_check.py" se --route --record   # immediately before dispatching a phase
```

It prints four lines, `state:`, `mode:`, `increment:` and `reason:`. **The first line picks
the row below.** Use `--record` exactly once per dispatch: it feeds the stall detector.

## The routing table

| State | Goes to |
|---|---|
| `greenfield` | `se:tailoring` |
| `blocked_invalid` | Run `se_check.py se` and report the ERROR lines to the user. Never repair them yourself. |
| `stalled` | **The user.** See below. |
| `suspects_pending` | `se:change-management` |
| `items_unapplied` | By the item named in the reason: owner `setup` → `se:requirements`; `E-` → `se:experiment`; `D-` → `se:increment`; a `Q-` owned by an increment → the skill that raised it, as its text says (CRIT-A approval: `se:build` or `se:increment`; fail or re-plan: `se:verification`). |
| `awaiting_customer` | **The user.** Present the open `Q-` items as one batch. Record each answer as `status: answered` with a one-line `answer`. |
| `no_requirements` | `se:requirements` |
| `draft_top_level` | `se:requirements` |
| `no_increment_plan` | `se:increment` (planning) |
| `experiments_open` | `se:experiment` |
| `increment_design` | `se:increment` (design) |
| `ready_to_build` | `se:build` |
| `implementing` | `se:build` |
| `increment_unverified` | `se:verification` |
| `final_validation` | `se:verification` (final) |
| `complete` | Nothing. Tell the user the project is complete. |

Hand off in one line (*"State `experiments_open` → se:experiment for E-03"*) and keep going
across phases without asking, until a state sends you to the user.

## `stalled` — the gate you do not pass alone

The reason line says why: the same state with unchanged artifacts across dispatches, or
the increment's dispatch budget used up. Present to the user:

1. the reason, quoted;
2. what the last dispatches tried;
3. the three options:
   - **continue**: another attempt, with a named change of approach;
   - **cut scope**: drop or defer requirements (`se:change-management`);
   - **accept the risk**: file an `accepted_risk` item (owner the increment, the one-line
     note in `answer`), then `--ack-stall`.

Only on the user's explicit **continue** do you run:

```bash
python "${CLAUDE_PLUGIN_ROOT}/scripts/se_check.py" se --route --ack-stall
```

**With the user away, stop.** Write the three options as your final message and change
nothing.

| Rationalization | Reality |
|---|---|
| "The user said keep working until it's done, don't wait." | That instruction predates the stall. A stall is the point where their judgment is needed; overriding it overnight is the v1 failure. |
| "I can see why it's stuck, so I'll break the loop myself." | Then say so in the options; that is the "continue" plan. The user approves it. |
| "I'll build, verify and close the increments to finish." | Each is a phase with its own gates. The router dispatches phases; it never does them. |
| "I'll note what happened in the route log." | `se/generated/` is written by scripts only. |

## Recovery

After a crash, a compaction or a new session, run `--route` again. The files are the
state; there is no other memory to trust.

The same table routes a trading backtest bot and a warehouse picking robot. The domain
changes what a phase finds, never where it goes.

## Red flags — stop

- Writing to `se/`, the code or the tests while routing.
- `--ack-stall` without the user's word.
- Any edit under `se/generated/`.
- Dispatching without `--record`.
