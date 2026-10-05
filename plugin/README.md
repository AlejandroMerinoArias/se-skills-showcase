> **Status:** experimental proof of concept, in active development, not a supported tool. This is the plugin's technical reference; start with the repository's main README.

# se-skills

Systems Engineering skill set for Claude Code: formal requirements, full
bidirectional traceability, and criticality-driven verification. This repo
provides a deterministic Python foundation (two CLIs, `se_check.py` and `se_trace.py`, on four shared modules, plus
their pytest suite) and the full V-model pipeline of skills that call out to it. The design is described in the repository's docs/how-it-works.md.

## Setup

```bash
pip install -r requirements.txt
```

Requires Python 3.11+.

## Skills

The pipeline lives under `skills/`: eight skills, about 5,800 words in total (v1: ten skills, 30,746). Each one states its own
triggering conditions in its frontmatter; the one-liners below are a map, not the trigger.

`se:develop` is the entry point: it does no phase work itself. It runs `se_check.py --route`
and dispatches the phase that owns the state.

| Skill | Use when |
|---|---|
| `se:develop` | The next SE step needs deciding, a project is being resumed, or the user asks to keep working. |
| `se:tailoring` | There is no `se/se-config.yaml` yet, or the mode, models, budgets, `test_command` or `sim_command` must change. |
| `se:requirements` | Top-level requirements need capturing, triaging, reviewing or validating. |
| `se:experiment` | An `experiment` item is open, or a fact about a simulator, runtime or dataset could be measured instead of asked. |
| `se:increment` | Validated top-level requirements need splitting into increments, or the active increment needs its design slice. |
| `se:build` | The active increment's validated, allocated requirements need a plan, code and tests. |
| `se:verification` | Implemented requirements need verifying, an increment needs closing, or the final validation is due. |
| `se:change-management` | A requirement is suspect, a measured fact contradicts one, or a change hits work already done downstream. |

## Data model

Each project keeps a single source of truth at `<project>/se/requirements.yaml`:

```yaml
meta:
  project: my-project
  mode: full          # lite | full
  levels: [SYS, ITEM]  # literal ID-prefix strings, top-to-bottom order

requirements:
  - id: SYS-F-012
    text: "..."
    category: functional   # functional | performance | interface | safety | derived | constraint
    criticality: A          # A | B | C
    rationale: null
    source: null
    parent: null
    allocated_to: null
    moc: test                # test | analysis | inspection | demonstration
    verified_by: []
    status: draft             # draft -> validated -> implemented -> verified | retired
    waiver: null
    suspect: false
    target: null
    threshold: null
    history: []
```

ID format: `^[A-Z]+(-[A-Z]+)?-[A-Z]-\d{3}$`, e.g. `SYS-F-012`, `ITEM-P-004`.

**Convention — `meta.levels`:** stores the literal ID-prefix strings used in
this project's requirement IDs, ordered from the top level down, e.g.
`levels: [SYS, ITEM]`. A requirement is considered top-level (and therefore
allowed a `null` parent) iff its ID's prefix equals `meta.levels[0]`.

**Convention — evidence references:** for `moc: analysis` or `moc:
inspection`, `verified_by` entries are file paths relative to the project's
`se/` directory, e.g. `evidence/depth_camera_analysis.md`. For `moc: test`,
entries are `relative/test/file::test_or_case_name` and are written only by
`se_trace.py` — never hand-edit them.

## `se-config.yaml`

Written by `se:tailoring` at `<project>/se/se-config.yaml`, read by every
later phase skill. `se_check.py` validates it when present; its absence is
legal and is the state that routes a new project to `se:tailoring`.

```yaml
mode: full                 # lite | full
models:
  crit_a: opus             # implementer model for CRIT-A requirements
  crit_b: sonnet
  crit_c: sonnet
  architecture: opus       # the architecture phase always uses the high tier
research: ask              # enabled | disabled | ask
traceability: annotation   # annotation
test_command: "python -m pytest"
```

All five top-level keys are required. Unknown top-level keys are a WARNING,
not an ERROR — the file is user-editable and forward compatibility beats
brittleness. Malformed YAML or a non-mapping top level exits `2`.

## `scripts/se_check.py`

```bash
python scripts/se_check.py <se-dir>
python scripts/se_check.py <se-dir> --mark-suspect <REQ-ID>
python scripts/se_check.py <se-dir> --route
```

Loads `<se-dir>/requirements.yaml` and runs, in order:

1. Schema / enum / ID-format validation.
2. Duplicate ID detection.
3. Parent-exists, no-cycles, and orphan (non-top-level requirement with no
   parent) checks.
4. `category: derived` requires a non-empty `rationale` (ERROR if missing).
5. Forbidden-words lint on `text` (WARNING): "user-friendly", "fast",
   "quick", "rapid", "adequate", "appropriate", "satisfactory", "minimize",
   "maximize", "etc.", "support", "high fidelity", "fault tolerant",
   "adaptable".
6. `moc: analysis | inspection` at `status: verified` requires `verified_by`
   to reference an existing evidence file under `se/evidence/` (ERROR if
   missing, not found on disk, or resolving outside `se/evidence/` — an
   absolute path or one escaping via `..` is rejected without touching disk).
7. `moc: test` at `status: verified` requires at least one linked test in
   `verified_by` (ERROR). Whether that test passes is not checked here —
   `se_check.py` never reads test results; `se_trace.py --results` is that
   gate, via the matrix's PASS/FAIL column.
8. `check_allocation`: allocation completeness. A `status: validated`
   requirement with an empty `allocated_to` is a WARNING — that is the legal
   intermediate state between `se:requirements` and
   `se:increment`, so it is reported without failing the run. A
   `status: retired` requirement with a non-null `allocated_to` is an ERROR:
   a retired requirement was struck, and allocating it makes a module
   responsible for building something nobody agreed to build. `status: draft`
   is not checked — requirements are unallocated by definition before
   architecture runs.
9. Suspect cascade: compares each requirement's current text hash against
   the `se/generated/req_hashes.json` snapshot written by `se_trace.py`. If
   the text changed and the requirement has children or `verified_by`
   links, the entire downstream subtree is marked `suspect: true` in the
   YAML (the one check that writes) and reported (WARNING).

`--mark-suspect <REQ-ID>` explicitly cascades `suspect: true` onto a
requirement and its entire downstream subtree, regardless of any hash
comparison, and writes the result immediately. It validates the schema first
and refuses to write if *any* requirement in the file fails it, even one
unrelated to the target: exit `1`, the findings printed, the file untouched.
A targeted write is still a write, and both writing paths require a file whose
schema validates — a suspect marking computed over requirements the script
could not read is a marking that was never fully determined.

### `--route` — where is this project?

```bash
python scripts/se_check.py <se-dir> --route            # look; writes nothing
python scripts/se_check.py <se-dir> --route --record   # before dispatching a phase
```

It prints four lines (`state:`, `mode:`, `increment:`, `reason:`) and exits `0`. The state is
re-derived from `se/` on every call, so the pipeline survives a crash or a compaction. The
sixteen states and the skill each routes to are the routing table in
`skills/se-develop/SKILL.md`; `scripts/tests/test_skills.py` checks that the table names every
state `se_route.py` can print. Precedence follows `ROUTE_STATES` in `scripts/se_route.py`: the
first matching state wins.

`--route` is the one documented exception to the exit-code contract: it returns `0` for every
state, including `blocked_invalid`, and `2` only when a file is missing or malformed.

Exit codes: `0` clean, `1` if any ERROR-level finding, `2` on malformed or
missing `requirements.yaml` (no partial writes ever occur in this case) or when `--mark-suspect` is called with an unknown ID.

## `scripts/se_trace.py`

```bash
python scripts/se_trace.py <se-dir> --tests <test-dir> [--results <junit.xml>] [--strict]
```

1. Scans `*.py`, `*.cpp`, `*.hpp`, `*.js`, `*.ts` files under `<test-dir>`
   for `# VERIFIES: ID[, ID...]` / `// VERIFIES: ID[, ID...]` comments
   attached to the next test definition (`def test_...`, `TEST(...)`,
   `TEST_F(...)`, `it('...')`).
2. Populates every requirement's `verified_by` list in `requirements.yaml`
   (atomic write); only `moc: test` requirements are touched, while
   `moc: analysis`, `inspection`, and `demonstration` preserve hand-edited
   evidence references.
3. If `--results <junit.xml>` is given, cross-references JUnit `testcase`
   elements by their `name` attribute against each `verified_by` entry's
   test identifier to produce a per-requirement result. **Known limitation:**
   matching is by exact `name` attribute — for C++/gtest projects, configure
   your JUnit exporter (or a thin wrapper) so the reported `name` equals
   `Suite.Case` (matching the `TEST(Suite, Case)` macro), not just the bare
   case name.
4. Writes `se/generated/matrix.md` (one row per requirement: ID, truncated
   text, CRIT, MoC, status, verified_by, and result) and
   `se/generated/req_hashes.json` (SHA-256 of each requirement's `text`,
   consumed by `se_check.py`'s suspect cascade).
   Result values: `NESTED` for a requirement that other requirements name as
   parent and that has no `verified_by` of its own — it is verified through
   its children, and this is what keeps a decomposed tree able to reach a
   clean matrix. Otherwise, for `moc: test`: `PASS`/`FAIL`/`UNKNOWN`/
   `UNVERIFIED` based on linked tests and JUnit results; for the other MoCs:
   `EVIDENCE` if `verified_by` is non-empty, else `UNVERIFIED`.
5. Reports: `moc: test` requirements with no linked test, excluding decomposed parents (WARNING);
   `VERIFIES:` annotations referencing nonexistent requirement IDs (ERROR);
   tests with no `VERIFIES:` annotation at all (WARNING);
   `trace_undetailed` (WARNING): a non-retired requirement has no downstream trace at all — no child requirements and an empty `verified_by`.

Exit codes: `0` clean, `1` if any ERROR-level finding, `2` on malformed or
missing `requirements.yaml`.

### `--strict` — the verification gate

```bash
python scripts/se_trace.py <se-dir> --tests <test-dir> --results junit.xml --strict
```

The command `se:verification` runs once, at the end. It computes nothing new;
it changes which facts block:

- Tests with no `VERIFIES:` annotation: WARNING → **ERROR** (spec section 3
  rule 7's "elevated to a blocking condition at the final verification gate").
- `moc: test` requirements with no linked test: WARNING → **ERROR**.
- Plus the gate itself: every live requirement must be `status: verified`,
  carry a non-empty `waiver`, or render `NESTED` (verified through its
  children). A requirement whose linked test FAILED is an error even at
  `status: verified`, and so is one whose result is UNKNOWN — `verified_by`
  names a test but nothing confirms it ran, whether because `--results` was
  omitted or because the linked test's name is absent from the results file
  given (renamed, skipped, excluded from the run). The status field is
  written by an agent, the JUnit result is not, and when they disagree — or
  when there is no result to compare against — the gate believes the
  results.

`trace_undetailed` stays a WARNING under `--strict`: it fires on shapes the
gate already judges through their children, and elevating it would fail
projects the gate is designed to pass.

## Running the test suite

```bash
python -m pytest scripts/tests -v
```

## v2 additions (0.4.0)

Install the one new dependency: `pip install -r requirements.txt` (named `requirements-dev.txt` in the development repository; adds `ruamel.yaml`,
which every write now uses so that comments in `requirements.yaml` survive).

New files under `se/`, both optional:

- `open-items.yaml` — every customer question (`Q-nn`), experiment (`E-nn`) and design
  decision (`D-nn`), with `status: open | answered | applied | closed | accepted_risk`.
  A requirement may reference items in `open_items:`; it cannot reach `implemented`
  until each is `closed` or `accepted_risk`.
- `increments.yaml` — the ordered increments (`I0`, `I1`, …); every live requirement
  carries `increment:` once this file exists, and `final_validation` records the end demo.

New `se_check.py` flags:

```
python scripts/se_check.py se --route             # state / mode / increment / reason; writes nothing
python scripts/se_check.py se --route --record    # same, and logs the dispatch for the stall detector
python scripts/se_check.py se --route --ack-stall # the user chose to continue past a stall
python scripts/se_check.py se --changed           # requirement IDs a diff-only review must cover
python scripts/se_check.py se --mark-suspect SYS-F-001 SYS-F-004
```

`se_trace.py` no longer requires `--tests` before any test exists. `history` is optional
(git is the history). BLOAT warnings flag oversized rationales, `CONOPS.md`,
`architecture.md` and `se/` as a whole; limits and budgets live in `se-config.yaml`
under `size_limits:` and `budgets:`.
