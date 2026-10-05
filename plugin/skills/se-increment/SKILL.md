---
name: se-increment
description: Use when se_check.py --route prints no_increment_plan or increment_design, when validated top-level requirements need splitting into increments, or when the active increment needs its architecture slice, module allocation or derived child requirements
---

# se-increment

Turns validated top-level requirements into work that runs. There are two modes, picked by
the router's state:

| State | Mode |
|---|---|
| `no_increment_plan` | **Planning.** Sketch the architecture and order the increments. |
| `increment_design` | **Design.** The active increment only: allocate, derive children, decide. |

```bash
python "${CLAUDE_PLUGIN_ROOT}/scripts/se_check.py" se --route
```

## Planning mode

1. **A coarse sketch in `se/architecture.md`:** a module table (module → responsibility), the
   interfaces between modules, and decisions `D-01…` for anything structural (middleware,
   language). No per-increment detail yet.
2. **`se/increments.yaml`:**
   - **I0 = characterization.** It owns every `experiment` item from setup, and has no
     requirements.
   - **I1…In are slices ordered so that I1 runs end to end as early as possible** (a walking
     skeleton), then the riskiest dependencies first.
   - Every live top-level requirement goes in exactly one increment's `requirements`, and
     each requirement also gets `increment: I<n>`.
3. Run `se_check.py se`. It must exit 0: it checks assignments against the `increment` fields.

A warehouse picking robot: I1 = drive to one shelf and back; I2 = pick one tote; I3 = full
order flow. A trading bot: I1 = one strategy over a one-month backtest writing its report;
I2 = risk limits; I3 = paper trading.

## Design mode (the active increment only)

Increments after the active one are not designed yet, and their drafts do not block you.

1. **Allocate** each of the increment's requirements to modules (`allocated_to`).
2. **Decide.** Each design choice becomes a D-nn under a `## I<n> — <goal>` section of
   `architecture.md`:

   ```markdown
   D-07 — Fixed-fraction position sizing at 2.5% of equity.
   Alternatives: volatility-scaled sizing. Why: fewer parameters, directly bounds drawdown.
   Reverses if: the E-06 backtest shows drawdown above 4% over 12 months.
   ```

   **Design-decision IDs are one sequence** across `open-items.yaml` and `architecture.md`. An undecided choice is an open `D-nn` item; once decided, the decision is written in `architecture.md` under the same ID (create the file with a `## Decisions` section if needed), and the item is set `closed` with the decision as its `answer`. The next ID is one above the highest in either file.

   **Decisions are made now.** A design choice is never deferred for a customer answer, and
   verification catches wrong ones. Only needs, priorities and acceptance criteria go to the
   customer.
3. **Unknown facts** become `experiment` items owned by this increment, with `blocks:` set.
4. **Derive children** where a requirement needs a design-level statement:

   ```yaml
   - id: ITEM-D-004
     text: When an order is sized, the sizer shall cap the position at 2.5% of account equity.
     category: derived
     criticality: B
     rationale: "D-07: 2.5% keeps a 3-sigma daily loss inside the 5% drawdown of SYS-S-001; derivation in evidence/A-03.md."
     source: null
     parent: SYS-S-001
     allocated_to: [position_sizer]
     moc: test
     verified_by: []
     status: draft
     waiver: null
     suspect: false
     target: null
     threshold: null
     increment: I2
   ```

   - `category: derived` and `source: null`. The ID family is `ITEM-<category letter>-<nnn>`,
     continuing the highest number in use.
   - **`rationale` is at most 400 characters: the conclusion, its D-nn and a pointer.** The
     working goes in `se/evidence/A-nn.md` (inputs, steps, result, assumptions) or in the
     D-nn itself.

| Rationalization | Reality |
|---|---|
| "The user asked for the whole analysis in the rationale." | Honour the intent (it is all findable from the requirement) with a pointer. The checker flags a rationale over 400 characters as BLOAT, and every agent re-reads the rationale forever. |
| "It's all in one place that way." | One place is the evidence file. The rationale is the index to it. |

5. **Derived validation** follows `se:requirements`' Step 4 rules: a separate reviewer, only
   `--changed` IDs, round 1 raises blocking and advisory findings, rounds 2+ blocking only,
   the cap from `budgets.review_rounds_per_phase`, and a `review-log.yaml` entry with
   `phase: increment_design` and `increment: I<n>`. The reviewer validates the children
   itself, except **CRIT-A children and genuine conflicts, which go to the user** in the next
   gate batch as a `customer_question` item (owner this increment, `blocks:` the child). When
   the router brings the answer back as `items_unapplied`: approved → the child becomes
   `validated`; rejected → redesign it. Then set the item `applied`, and `closed` once
   `se_check.py se` exits 0.

## Exit

`se_check.py se` exits 0, with no `BLOAT` finding on anything you wrote. Refresh the snapshot
(`python "${CLAUDE_PLUGIN_ROOT}/scripts/se_trace.py" se`) so the next review's `--changed`
covers only what changes after this point.
`se_check.py se --route` leaves `increment_design`. Then hand off to `se:build`.

## Red flags — stop

- A rationale that shows its arithmetic.
- "Let's wait for the customer" about *how* to build something.
- Designing requirements that belong to a later increment.
- A D-nn with no "reverses if".
