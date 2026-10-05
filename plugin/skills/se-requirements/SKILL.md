---
name: se-requirements
description: Use when se_check.py --route prints no_requirements, draft_top_level or awaiting_customer during setup, when a customer describes what a system must do, or when top-level requirements need capturing, triaging, reviewing or validating
---

# se-requirements

Captures the **top-level** requirements (`SYS-…`), triages every unknown, runs the capped
review, and holds the one human gate on the top level. Derived requirements belong to
`se:increment`.

## Artifacts this skill writes

| File | What goes in it |
|---|---|
| `se/CONOPS.md` | Four sections: Purpose, Use cases, Environment, Interfaces. At most ~15 KB. **Never** a log, a question list or a discussion record. |
| `se/requirements.yaml` | `SYS-…` requirements, `status: draft` until the user validates them. |
| `se/open-items.yaml` | **Every** unknown, as a `Q-`, `E-` or `D-` item. Nothing unknown lives in prose. |
| `se/review-log.yaml` | One entry per review round. |

## Step 1 — CONOPS, then elicit

Write `CONOPS.md` first. If `research` in `se-config.yaml` is `enabled`, or `ask` and the user
agrees, look for the domain's standards, prior art and known failure modes. Each finding enters
as a `draft` requirement whose `source` names the reference, and passes the same review and gate.

Then walk the six sources for needs the user did not state:
environment, operation, interfaces, safety (what can fail, what does damage), maintenance,
constraints (deadline, budget, deliverables).

## Step 2 — triage every unknown before asking anything

Each unknown gets **exactly one** kind:

| Kind | Test | Who resolves it |
|---|---|---|
| `customer_question` (`Q-nn`) | Only the customer can know it: a mission need, a priority between needs, an acceptance criterion, an imposed constraint. | The customer, at a gate |
| `experiment` (`E-nn`) | Running the system or its simulator, reading the provided code or documentation, or measuring could answer it. | `se:experiment` |
| `design_decision` (`D-nn`) | It is a choice between ways of meeting a need. | The pipeline: recorded as D-nn with a rationale, **never deferred** |

**Design-decision IDs are one sequence** across `open-items.yaml` and `architecture.md`. An undecided choice is an open `D-nn` item; once decided, the decision is written in `architecture.md` under the same ID (create the file with a `## Decisions` section if needed), and the item is set `closed` with the decision as its `answer`. The next ID is one above the highest in either file.

Write each one to `se/open-items.yaml`:

```yaml
- id: E-01
  kind: experiment
  text: What slippage does the broker simulator apply per fill?
  blocks: [SYS-F-003]
  owner: setup
  status: open
  answer: null
  evidence: null
```

Customer questions go out **in one batch per gate**, within the caps in `se-config.yaml`
(`budgets.customer_questions_per_gate`, `customer_questions_total`). Before a question goes
into the batch, it must fail both other tests.

| Rationalization | Reality |
|---|---|
| "Strategy A or B is a business call, so I'll ask." | Choosing *how* to meet a need is a design decision. Ask the customer what they need (a return target, a risk limit); the pipeline picks the strategy. |
| "The customer is asking me to ask them." | They asked you to settle the unknowns. Settle each by its kind. |
| "The stub can't show it, so it goes to the customer or the broker." | Then the experiment is different: read the documentation, extend the probe. It is still an `E-` item. |
| "I'll note the open questions in CONOPS." | CONOPS is not a log. Items go in `open-items.yaml`, where the router can see them. |

## Step 3 — write the requirements

- EARS patterns and atomic statements: see [ears-patterns.md](ears-patterns.md). IDs are
  immutable, and a struck requirement becomes `status: retired`.
- **Open values:** write the unknown into the text and link the item, for example "…within
  `S` per share (E-01)" with `open_items: [E-01]`. A requirement may be validated with an open
  value; the scripts block it from being implemented until the item closes.
- `rationale` is at most 400 characters. Longer reasoning goes in a D-nn decision or an
  evidence file, and the rationale points to it.

## Step 4 — the capped review

Each round is run by **a reviewer agent other than the author**, against
[incose-criteria.md](incose-criteria.md).

1. The scope is only what changed:

   ```bash
   python "${CLAUDE_PLUGIN_ROOT}/scripts/se_check.py" se --changed
   ```

2. **Round 1** may raise blocking and advisory findings. **Rounds 2 and later raise blocking
   findings only.**
   - **Blocking:** a conflict, something that cannot be verified, a parent's demand not
     covered, or wrong against evidence already in hand.
   - **Advisory:** everything else. Recorded once, in round 1, and never a required change.
3. *Correct* means correct against current evidence. A doubt that depends on a missing fact
   is an `E-` item, not a finding.
4. Append the round to `se/review-log.yaml`:

   ```yaml
   - phase: requirements
     increment: setup
     round: 2
     blocking: 1
     advisory: 0
   ```

5. **The cap:** read `budgets.review_rounds_per_phase` (default 2). When the log already holds
   that many `requirements`/`setup` rounds, **there is no next round**, whoever asks. Each
   remaining blocking finding leaves by exactly one of three exits:
   - it depends on an unknown fact → an `E-` item, with `blocks:` naming the requirement;
   - it is CRIT-A or a genuine conflict → a `Q-` item in the gate batch;
   - anything else → an `accepted_risk` item; the one-line note goes in `answer`.

| Rationalization | Reality |
|---|---|
| "One more round makes it perfect." | The cap exists because another round always finds something. Take the exits. |
| "The wording fixes are quick, so I'll just apply them." | Advisory findings never require changes. Applying them re-opens review on what you changed. |
| "Round 2 found six clarifications; I'll log them." | In round 2 they are not findings. Log `advisory: 0`. |

## Step 5 — the human gate

Present the top-level list, the open `Q-` batch, and any blocking findings that went to the
user. Set `status: validated` only on the user's word. Record each answer as the item's
one-line `answer` with `status: answered`.

**Apply every answer** (the router sends `setup`-owned answered items here as
`items_unapplied`): update the requirements it affects, set the item `applied`, run
`se_check.py se`, then set it `closed`.

## Exit

```bash
python "${CLAUDE_PLUGIN_ROOT}/scripts/se_check.py" se
```

It must exit 0, with no `SYS-…` requirement still at `draft`. Then refresh the snapshot that
`--changed` compares against, and hand off to `se:increment`:

```bash
python "${CLAUDE_PLUGIN_ROOT}/scripts/se_trace.py" se
```

The same flow serves a trading backtest bot and a warehouse picking robot. Only the
questions differ.

## Red flags — stop

- A question to the customer that a run, the code or a document could answer.
- A choice between two designs sent to the customer.
- A third entry in `review-log.yaml` for the same phase and increment when the cap is 2.
- Editing requirement text because of an advisory finding.
- Open questions written anywhere except `open-items.yaml`.
