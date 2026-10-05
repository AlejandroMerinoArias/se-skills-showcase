# The 10 criteria, the set-level checks, and the division of labour

Reference for the review rounds in `se:requirements` and `se:increment`. Also read by `se:change-management`,
which re-runs **Consistency** over a suspect subtree. Do not move or rename this
file.

## Run the script first, then review what it cannot see

`se_check.py` is deterministic, runs in about a second, and already covers
everything in the left column. **Run it before you read a single requirement.**

```bash
python "${CLAUDE_PLUGIN_ROOT}/scripts/se_check.py" se
```

| The script already checks | You review |
|---|---|
| Schema: all sixteen fields present, enums valid (`category`, `criticality`, `moc`, `status`) | Whether the values are the *right* ones |
| ID format, and that `meta.levels` is populated | Whether the requirement belongs at that level |
| Duplicate IDs | Duplicate *intent* under two different IDs |
| Orphans and parent cycles | Whether the parent link is the *correct* parent |
| `category: derived` has a non-empty `rationale` | Whether that rationale records a real design decision |
| The forbidden-word lint (14 words) | Every vagueness the lint has no word for |
| MoC evidence: `analysis`/`inspection`/`test` at `verified` have `verified_by` | Whether the declared `moc` could actually settle this requirement |

Exit 2 means a file is missing or malformed; exit 1 means a schema, ID or
duplicate error. Fix those before reviewing content — there is no point applying
judgement to a file that does not load.

**Exit 0 is the starting line, not a result.** Every requirement in this
document's failing examples passes `se_check.py`. The script cannot see that
"in a way that feels natural" has no pass/fail value, that two requirements set
different timeouts on the same interface, or that a requirement is a solution
wearing a requirement's ID. That is the whole of your job.

Never re-derive by hand what the script does. A review that spends its effort
confirming that IDs are unique has spent it on the one part that was already
free.

## The 10 criteria

Applied **per requirement**. Each is a question with a yes/no answer, not a
score. Every failing example below passes `se_check.py`.

### 1. Necessary

*If this requirement were deleted, would anything be missing?*

> ✗ **Clinic appointment booking** — "The booking system shall offer appointment
> reminders by fax."
>
> Delete it and no stakeholder is worse off. Nobody asked for it, nothing
> depends on it, and it will still cost review, implementation and verification
> effort for the life of the project.

A requirement nobody would miss is not free. It gets a task, a test, a matrix
row and a place in every later review.

### 2. Appropriate

*Is this at the right level of abstraction for the level it sits at — a need,
not a solution?*

> ✗ **Food bank donation tracker** — "The tracker shall store intake records in
> a PostgreSQL table named `intake`."
>
> The need is that intake records survive a restart and can be totalled at
> audit. The database is a design decision, and writing it here removes it from
> the architecture phase where it would have been reasoned about.

The test: could you satisfy the need a different way, and does this sentence
forbid it for no stated reason? Then it is over-constrained.

### 3. Singular

*One requirement, one response?*

> ✗ **Library inter-branch loans** — "When an item arrives at the receiving
> branch, the system shall mark it available **and** notify the requesting
> member."
>
> Two responses that can pass and fail independently. One test result cannot say
> which happened.

Atomicity, and the "and" that is allowed inside a single response, are in
[`../se-requirements/ears-patterns.md`](../se-requirements/ears-patterns.md).

### 4. Correct

*Is this a true statement of the actual need?*

> ✗ **E-bike battery charger** — "When the cell temperature rises above 60 °C,
> the charger shall stop charging within 2 s." — where the cell manufacturer's
> datasheet gives a 45 °C maximum.
>
> EARS form, atomic, verifiable, lint-clean, and wrong. A test written against
> it will pass while the pack cooks.

**Correct is the criterion no amount of good form can supply.** It is checked
against the source — the datasheet, the CONOPS, the regulation, the user — not
against the sentence.

### 5. Conforming

*Does it match the project's approved pattern and style?*

> ✗ **Food bank donation tracker** — "The tracker should be able to support bulk
> intake."
>
> Three failures at once: `should` instead of `shall`, no EARS pattern, and
> `support` is on the word lint.

The pattern set, the obligation verb, the atomicity rule, the word lint, the ID
format, and the rule that performance requirements carry `target` and
`threshold` are all defined in
[`../se-requirements/ears-patterns.md`](../se-requirements/ears-patterns.md).
Check against that file. It is not restated here.

### 6. Unambiguous

*Can this be read exactly one way?*

> ✗ **Clinic appointment booking** — "The booking system shall cancel
> appointments that are not confirmed within 24 hours."
>
> 24 hours after the appointment was booked, or 24 hours before it is due? Both
> are ordinary readings and they produce different software.

The test is not whether *you* can tell what was meant. It is whether two people
who have not spoken to each other reach the same reading.

### 7. Complete

*Does it stand on its own, with nothing left to fill in?*

> ✗ **Library inter-branch loans** — "The system shall hold a requested item at
> the collection desk for TBD days."
>
> A placeholder is a note wearing a requirement's ID, and it will still be a
> note when the implementer reaches it.

Also incomplete: a performance requirement with no `threshold`, and a trigger
with no stated response.

### 8. Feasible

*Can this be built, within this project's constraints?*

> ✗ **E-bike battery charger** — "The charger shall determine the pack's
> remaining capacity to within 1 % from the terminal voltage alone."
>
> The chemistry's voltage curve is nearly flat across the middle of its range.
> No amount of software recovers 1 % from that measurement.

Feasibility is judged against *this* project's budget, schedule, hardware, skills
and law — not against what is possible in principle.

### 9. Verifiable

*Could someone prove this holds, by the declared `moc`?*

> ✗ **Food bank donation tracker** — "The tracker shall make intake recording
> easy for new volunteers."
>
> No pass/fail value exists, so no two assessors are obliged to agree. Declaring
> `moc: test` on it makes the claim worse, not better: it names a method that
> cannot be executed.

Check the requirement against its own `moc` field. "Verifiable by a test that
does not yet exist" is fine; "verifiable by a test that could not exist" is a
finding.

### 10. Consistent

*Does it contradict any other requirement in the set?*

> ✗ **Clinic appointment booking** — `SYS-C-002` "The booking system shall
> retain appointment records for 7 years." against `SYS-F-009` "When a patient
> requests deletion, the booking system shall remove their appointment records
> within 30 days."
>
> Both are well-formed. Together they are unbuildable, and neither one is wrong
> on its own.

Consistency is the one per-requirement criterion you cannot check by reading one
requirement. It is why the set-level pass below exists.

## Set-level checks

Run **over the whole set**, after the per-requirement pass. These four find
nothing when you look at requirements one at a time, which is why they are
listed separately and why skipping them is invisible.

### Conflicts

Two requirements that cannot both hold. Group by what they constrain — the same
interface, the same quantity, the same resource, the same window of time — and
read each group together.

The common shape is two numbers on the same thing, written by different people
at different times: a retry timer that fires inside another requirement's
abandon timer; a retention period against a deletion duty; a power cap against a
throughput floor.

**A detected conflict always goes to the human.** You may say which side you
think is right; you may not pick one.

### Gaps

An area the requirements should cover and do not. Walk the six elicitation
sources from **se:requirements** — Environment, Operation, Interfaces, Safety,
Maintenance, Budget/constraints — and ask which of them no requirement in the
set answers.

> **Clinic appointment booking.** Every requirement describes the system working.
> Nothing anywhere says what happens when the SMS reminder provider is
> unreachable — the Interfaces row is empty. That is a gap, and it is a finding
> even though no requirement is defective.

A gap is the finding a per-requirement review structurally cannot produce,
because there is no requirement to attach it to.

### Unit homogeneity

The same physical quantity expressed in different units in different
requirements.

> **Food bank donation tracker.** `SYS-F-002` records intake weight in
> kilograms; `SYS-F-008` warns the coordinator when a pallet exceeds 400 pounds.
> Both are verifiable. The conversion lives in nobody's head and in no
> requirement, so it will be done twice and disagree once.

Pick the project's unit for each quantity and report every requirement that
departs from it.

### Duplicate intent under different IDs

`se_check.py` catches duplicate *IDs*. It cannot catch the same requirement
written twice in different words.

> **Library inter-branch loans.** `SYS-F-004` "The system shall refuse a loan
> request from a member holding 10 items." and `SYS-F-011` "While a member holds
> the maximum permitted number of items, the system shall reject further
> requests."
>
> Two IDs, one behaviour. They will get two tasks and two tests, and the day
> someone changes the limit, one of them will be missed.

Report the pair and say which ID you recommend keeping; retiring the other is a
user decision, and retiring is `status: retired`, never deletion.
