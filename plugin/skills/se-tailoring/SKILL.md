---
name: se-tailoring
description: Use when starting systems-engineering work on a project that has no se/se-config.yaml, when se_check.py --route prints greenfield, or when the user asks to change a project's SE mode, models, budgets, test_command or sim_command
---

# se-tailoring

Writes `se/se-config.yaml` and seeds the empty `se/` files. Nothing else in the pipeline
can run until this exists and `se_check.py` accepts it.

## Step 1 — git first

```bash
git rev-parse --is-inside-work-tree
```

v2 keeps requirement history in git and nowhere else: requirements carry no `history`
field. **A project that is not a git repository gets no config.**

- **Not a repository:** offer `git init`, and say why in one sentence.
- **The user declines:** stop. Write nothing. Tell them SE setup resumes when the project is
  a repository.

| Rationalization | Reality |
|---|---|
| "The user said no git, so I'll track SE files as plain files." | Without git, every requirement edit erases what it replaced; change management has nothing to compare against. Declining git declines v2. |
| "I'll add `version_control: false` to the config." | No such key exists. The checker rejects invented keys, and the dependency is not optional. |

## Step 2 — the interview, one question at a time

Ask; never infer these from a README.

1. **`test_command`**: the command that runs the project's tests (`python -m pytest`,
   `npm test`, `cargo test`).
2. **`sim_command`**: only if the system runs in a simulator or live runtime. It must be a
   launcher that **runs bounded and exits by itself**: a backtest over a fixed window, a game
   build that plays one scripted level. Omit it if there is none.
3. **Models per criticality**: `crit_a`, `crit_b`, `crit_c`, `architecture`.
4. **`research`**: `enabled`, `disabled` or `ask`.

**Mode is `full`** unless the user explicitly asks for lite. Record that request in a comment.

## Step 3 — write exactly this shape

```yaml
mode: full
models:
  crit_a: opus
  crit_b: sonnet
  crit_c: sonnet
  architecture: opus
research: ask
traceability: annotation
test_command: "python -m pytest"
sim_command: "python tools/backtest.py --days 30"   # omit when there is no simulator
budgets:
  review_rounds_per_phase: 2
  customer_questions_per_gate: 5
  customer_questions_total: 15
  dispatches_per_increment: 8
  agent_soft_tokens: 150000
```

Then seed the other two files:

```yaml
# se/requirements.yaml
meta:
  project: <name>
  mode: full
  levels: [SYS, ITEM]
requirements: []
```

```yaml
# se/open-items.yaml
items: []
```

Use only keys from these templates. The checker is the schema.

## Step 4 — exit gate

```bash
python "${CLAUDE_PLUGIN_ROOT}/scripts/se_check.py" se
```

It must exit `0`. Show the user the config, and hand off only once they approve it. Next
comes `se:requirements`: a trading backtest bot and a mobile shelf-scanning app go the same
way from here.

## Red flags — stop

- Writing `se/` in a directory where `git rev-parse` failed.
- A config key that is not in the template.
- A `test_command` or `sim_command` you guessed rather than heard.
