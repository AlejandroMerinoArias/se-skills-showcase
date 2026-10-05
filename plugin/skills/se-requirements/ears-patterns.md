# Writing a requirement: EARS patterns, IDs, and the word lint

Reference for `se:requirements` and `se:increment`. Every
requirement written into `se/requirements.yaml` matches one of the five
patterns below, is atomic, and survives the word lint.

## The five patterns

Each is a template. `<system>` is the thing being built, named the same way
every time. `shall` is the only obligation verb — never "should", "will",
"must", or "needs to".

### 1. Ubiquitous — always true, no condition

> **The `<system>` shall `<response>`.**

- The donation tracker shall record the weight, category, and donor of every
  intake in kilograms.
- The charger shall limit output current to 4 A.

Use when the behaviour has no trigger and no precondition. If you find
yourself adding "at all times", delete it — that is what ubiquitous means.

### 2. Event-driven — a trigger occurs

> **When `<trigger>`, the `<system>` shall `<response>`.**

- When a volunteer confirms a donation intake, the tracker shall assign the
  record an intake number that no other record holds.
- When the cell temperature reading rises above 45 °C, the charger shall stop
  charging within 2 s.

The trigger is a discrete thing that happens at a moment. This is the most
common pattern and the right default when you are unsure.

### 3. State-driven — true while a condition holds

> **While `<state>`, the `<system>` shall `<response>`.**

- While the pantry is outside its published opening hours, the tracker shall
  reject new intake records.
- While the pack is charging, the charger shall display the measured pack
  voltage.

The distinguishing test: a trigger happens once; a state persists. "While"
behaviour starts when the state is entered and ends when it is left.

### 4. Unwanted behaviour — a fault or an out-of-bounds condition

> **If `<unwanted condition>`, then the `<system>` shall `<response>`.**

- If a donation record is submitted with no donor and no "anonymous" mark,
  then the tracker shall reject the submission and state which field is
  missing.
- If the temperature sensor returns no reading for 3 consecutive samples,
  then the charger shall stop charging and latch a sensor-fault indication.

This is the pattern for everything the safety and maintenance rows of the
elicitation checklist turn up. A system with no `If ... then ...`
requirements has not been asked what happens when things go wrong.

### 5. Optional feature — behaviour that exists only in some builds

> **Where `<feature is included>`, the `<system>` shall `<response>`.**

- Where the tracker is configured with a second pantry site, the tracker
  shall keep each site's stock counts separate.
- Where the charger is fitted with the mains-isolation relay, the charger
  shall open the relay before reporting charge complete.

Use only for genuinely optional configurations, not for "maybe later". A
feature nobody has decided to build is not a requirement yet.

## Atomicity — one requirement, one `shall`

A sentence with "and" joining two responses is **two requirements**.

Not atomic:

> "When a game is returned, the system shall set its status to on-shelf and
> clear the recorded borrower."

Two requirements:

> "When a lent item is returned, the system shall set its status to
> on-shelf."
> "When a lent item is returned, the system shall clear its recorded
> borrower."

Why it matters mechanically: a requirement is the unit that gets a
verification result. If one ID covers two behaviours, a test can pass for one
and fail for the other, and the matrix cannot say which. Splitting costs one
ID; not splitting costs the traceability.

"And" inside a *single* response is fine — "shall record the weight and
category of the intake" is one action producing one record. The test is
whether the two halves could pass and fail independently.

## The word lint

`se_check.py` flags these words in requirement `text` as WARNINGs. Each has a
question that replaces it. Answer the question and the vagueness is gone.

| Flagged | Ask instead |
|---|---|
| user-friendly | Usable by whom, doing which task, measured how? |
| fast | Fast compared to what, measured how? |
| quick | Quick by what measured time? |
| rapid | Within how many seconds? |
| adequate | Adequate against which pass/fail value? |
| appropriate | Decided by which rule, applied by whom? |
| satisfactory | Satisfactory against which acceptance value? |
| minimize | Down to what number? |
| maximize | Up to what number? |
| etc. | Name the remaining items, or the rule that generates them. |
| support | Does what, in a verb a tester can perform? |
| high fidelity | Fidelity on which scale, at which value? |
| fault tolerant | Tolerant of which faults, still doing what? |
| adaptable | Adaptable to which change, within what effort? |

### The lint is a floor, not a ceiling

It matches whole words, case-insensitively. It cannot see vagueness it has no
word for. All of these pass the lint and none of them is a requirement:

- "The controller shall water the plants when the soil is dry." — *dry* is
  not a measured value.
- "The controller shall send an alert if something goes wrong." — *something*
  is not a named condition.
- "The system shall handle large donations sensibly." — no threshold, no
  defined behaviour.

The real test is the one the lint approximates: **could two people
independently decide pass or fail, and get the same answer?** If not, the
requirement is not verifiable, whatever the lint says.

Never resolve this by leaving a placeholder in the text. `"shall water when
moisture is below <TBD>%"` is not a requirement — it is a note. Propose a
concrete value, record that you proposed it, and let the user confirm or
correct it at the validation gate.

## Performance requirements carry `target` and `threshold`

- **`target`** — the design goal. What you are aiming for.
- **`threshold`** — the pass/fail value. Worse than this fails.

```yaml
- id: SYS-P-002
  text: "When a volunteer submits an intake record, the tracker shall confirm the record within 2 s."
  category: performance
  target: 0.5        # design goal, seconds
  threshold: 2.0     # pass/fail, seconds
```

Both are plain numbers in a unit named in `text`. A performance requirement
with neither is not verifiable — there is nothing for a test to compare
against — and a `target` worse than its `threshold` is a contradiction.

Requirements in other categories leave both `null`.

## IDs

Format: **`<level>-<category letter>-<number>`**, matching
`^[A-Z]+(-[A-Z]+)?-[A-Z]-\d{3}$`.

- **`<level>`** — a literal prefix from `meta.levels` in
  `requirements.yaml`, e.g. `SYS`, `ITEM`. A requirement is **top-level** iff
  its prefix equals `meta.levels[0]`.
- **`<category letter>`** — the first letter of `category`:

  | Letter | category |
  |---|---|
  | F | functional |
  | P | performance |
  | I | interface |
  | S | safety |
  | C | constraint |
  | D | derived — produced by `se:increment`, never at capture |

- **`<number>`** — exactly three digits, zero-padded, counting up within its
  level-and-letter series: `SYS-F-001`, `SYS-F-002`, `SYS-P-001`.

Examples: `SYS-F-012`, `SYS-S-004`, `ITEM-P-004`.

### IDs are immutable and never reused

An ID is the handle every test annotation, evidence file, and matrix row
uses. Once written, it names that requirement forever.

- **Never renumber** to close a gap. Gaps are normal and harmless.
- **Never delete** a requirement that is no longer wanted. Set
  `status: retired` and add a `history` entry saying why. A retired
  requirement stays in the file, keeps its ID, and appears in the matrix as
  retired.
- **Never reuse** a retired ID for a new requirement. The next requirement
  takes the next unused number.

Rewriting `text` under an existing ID is legal — that is a change to the same
requirement, and `se_check.py` marks its downstream subtree `suspect`.
Replacing what a requirement *is* under the same ID is not: that is a new
requirement and needs a new ID.
