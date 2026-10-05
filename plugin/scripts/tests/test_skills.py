"""The plugin surface: skill frontmatter, cross-skill links, plugin.json.

Nothing in the suite touched `skills/` or `.claude-plugin/plugin.json` before
this file, so 1,936 lines of skill Markdown and the manifest were guarded by
human review alone. `test_readme.py` is the precedent that this repo checks
its own docs mechanically.

The load-bearing test here is the link resolver. Three skills reference each
other by relative path, and the plan says of two of those files "do not move
or rename it" - twice, because Plan B2's se:change-management also reads
`incose-criteria.md`. The point is that a rename or a moved reference fails
this suite instead of failing silently in B2.
"""

import json
import os
import re
import shutil
import subprocess

import pytest
import yaml

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SKILLS_DIR = os.path.join(REPO_ROOT, "skills")
PLUGIN_JSON = os.path.join(REPO_ROOT, ".claude-plugin", "plugin.json")

# A Markdown link whose target is neither a URL nor a pure in-page anchor.
RELATIVE_LINK_RE = re.compile(r"\[[^\]]*\]\(([^)]+)\)")

NAME_RE = re.compile(r"^[a-z0-9-]+$")


def _skill_dirs():
    return sorted(
        d for d in os.listdir(SKILLS_DIR)
        if os.path.isfile(os.path.join(SKILLS_DIR, d, "SKILL.md"))
    )


def _skill_md_files():
    """Every .md file under skills/, as (repo-relative path, absolute path)."""
    out = []
    for root, _dirs, files in os.walk(SKILLS_DIR):
        for fname in sorted(files):
            if fname.endswith(".md"):
                full = os.path.join(root, fname)
                out.append((os.path.relpath(full, REPO_ROOT).replace(os.sep, "/"), full))
    return sorted(out)


def _frontmatter(path):
    """Parse the YAML frontmatter block. Returns None if there isn't one."""
    with open(path, encoding="utf-8") as f:
        content = f.read()
    if not content.startswith("---\n") and not content.startswith("---\r\n"):
        return None
    parts = re.split(r"^---\s*$", content, maxsplit=2, flags=re.MULTILINE)
    if len(parts) < 3:
        return None
    return yaml.safe_load(parts[1])


SKILL_DIRS = _skill_dirs()
SKILL_MD_FILES = _skill_md_files()


# --- v2 roster (Plan 2) ---

# Spec §7 target words per SKILL.md; the hard cap is target * BUDGET_SLACK.
V2_BUDGETS = {
    "se-build": 1100,
    "se-change-management": 900,
    "se-develop": 800,
    "se-experiment": 1000,
    "se-increment": 1500,
    "se-requirements": 1700,
    "se-tailoring": 600,
    "se-verification": 900,
}
BUDGET_SLACK = 1.15
TOTAL_WORD_CAP = 9000

# Each Plan 2 task appends its skill here in the same commit as the skill.
V2_WRITTEN = [
    "se-tailoring",
    "se-experiment",
    "se-requirements",
    "se-increment",
    "se-build",
    "se-verification",
    "se-change-management",
    "se-develop",
]

# v1 skills with no v2 counterpart; Task 10 deletes them and empties this list.
V1_LEGACY = []

FORBIDDEN_DOMAIN_RE = re.compile(
    r"\b(caves?|lanterns?|uavs?|drones?|quadrotors?|subterrain)\b", re.IGNORECASE)
REPO_FLAG_RE = re.compile(r'add_argument\(\s*"(--[a-z][a-z-]*)"')
CITED_FLAG_RE = re.compile(r"(?<![\w-])(--[a-z][a-z-]*)")


def _skill_words(skill):
    with open(os.path.join(SKILLS_DIR, skill, "SKILL.md"), encoding="utf-8") as f:
        return len(f.read().split())


def _v2_scanned_files():
    """Every file the v2 validation run could read that Plan 2 wrote."""
    roots = [os.path.join(SKILLS_DIR, s) for s in V2_WRITTEN]
    roots.append(os.path.join(REPO_ROOT, "pressure-tests", "v2"))
    roots.append(os.path.join(REPO_ROOT, "pressure-tests", "tools"))
    fixtures = os.path.join(REPO_ROOT, "pressure-tests", "fixtures")
    if os.path.isdir(fixtures):
        roots += [os.path.join(fixtures, d) for d in os.listdir(fixtures) if d.startswith("v2-")]
    out = []
    for root in roots:
        for dirpath, _dirs, files in os.walk(root):
            out += [os.path.join(dirpath, f) for f in files]
    return sorted(out)


def _script_flags():
    flags = set()
    for name in ("se_check.py", "se_trace.py"):
        with open(os.path.join(REPO_ROOT, "scripts", name), encoding="utf-8") as f:
            flags |= set(REPO_FLAG_RE.findall(f.read()))
    return flags


def test_only_known_skills_are_shipped():
    """A directory in neither roster is a skill nobody decided to ship."""
    unknown = sorted(set(SKILL_DIRS) - set(V2_BUDGETS) - set(V1_LEGACY))
    assert unknown == [], f"skills in neither roster: {unknown}"


def test_every_written_v2_skill_exists():
    missing = sorted(s for s in V2_WRITTEN if s not in SKILL_DIRS)
    assert missing == [], f"V2_WRITTEN names skills with no directory: {missing}"


@pytest.mark.parametrize("skill", V2_WRITTEN)
def test_v2_skill_within_word_budget(skill):
    cap = int(V2_BUDGETS[skill] * BUDGET_SLACK)
    words = _skill_words(skill)
    assert words <= cap, f"{skill}/SKILL.md has {words} words; cap {cap}"


def test_v2_total_within_cap():
    total = sum(_skill_words(s) for s in V2_WRITTEN)
    assert total <= TOTAL_WORD_CAP, f"v2 skills total {total} words; cap {TOTAL_WORD_CAP}"


def test_v2_files_carry_no_validation_domain_words():
    hits = []
    for path in _v2_scanned_files():
        try:
            with open(path, encoding="utf-8") as f:
                for n, line in enumerate(f, 1):
                    if FORBIDDEN_DOMAIN_RE.search(line):
                        hits.append(f"{os.path.relpath(path, REPO_ROOT)}:{n}")
        except UnicodeDecodeError:
            continue
    assert hits == [], f"validation-project vocabulary found: {hits}"


def test_v2_skills_cite_only_real_flags():
    real = _script_flags()
    cited = set()
    for skill in V2_WRITTEN:
        for dirpath, _dirs, files in os.walk(os.path.join(SKILLS_DIR, skill)):
            for fname in files:
                if not fname.endswith(".md"):
                    continue
                with open(os.path.join(dirpath, fname), encoding="utf-8") as f:
                    for line in f:
                        if "se_check.py" in line or "se_trace.py" in line:
                            cited |= set(CITED_FLAG_RE.findall(line))
    assert sorted(cited - real) == [], f"skills cite flags the scripts lack: {sorted(cited - real)}"


def test_se_develop_names_every_route_state():
    """A state the router can print but the routing table lacks sends an agent nowhere."""
    import se_route
    with open(os.path.join(SKILLS_DIR, "se-develop", "SKILL.md"), encoding="utf-8") as f:
        content = f.read()
    missing = [s for s in se_route.ROUTE_STATES if f"`{s}`" not in content]
    assert missing == [], f"se-develop's table lacks: {missing}"


def test_the_v2_skill_set_is_complete():
    assert sorted(SKILL_DIRS) == sorted(V2_BUDGETS)
    assert sorted(V2_WRITTEN) == sorted(V2_BUDGETS)


def test_the_flag_scanner_sees_the_scripts():
    """Control: if REPO_FLAG_RE stops matching, the flag test passes vacuously."""
    assert {"--route", "--record", "--ack-stall", "--changed", "--mark-suspect",
            "--tests", "--results", "--strict"} <= _script_flags()


# --- the skill set itself ---

def test_every_skill_directory_has_a_skill_md():
    """A directory under skills/ with no SKILL.md is invisible to the plugin
    loader, which is a silent failure rather than a loud one."""
    present = sorted(d for d in os.listdir(SKILLS_DIR)
                     if os.path.isdir(os.path.join(SKILLS_DIR, d)))
    assert present == SKILL_DIRS, \
        f"directories without a SKILL.md: {sorted(set(present) - set(SKILL_DIRS))}"


# --- frontmatter ---

@pytest.mark.parametrize("skill", SKILL_DIRS)
def test_skill_frontmatter_parses_and_carries_name_and_description(skill):
    fm = _frontmatter(os.path.join(SKILLS_DIR, skill, "SKILL.md"))
    assert isinstance(fm, dict), f"{skill}/SKILL.md has no parseable YAML frontmatter"
    assert isinstance(fm.get("name"), str) and fm["name"].strip(), \
        f"{skill}/SKILL.md frontmatter has no 'name'"
    assert isinstance(fm.get("description"), str) and fm["description"].strip(), \
        f"{skill}/SKILL.md frontmatter has no 'description'"


@pytest.mark.parametrize("skill", SKILL_DIRS)
def test_skill_name_matches_its_directory(skill):
    """The loader addresses a skill by directory; the frontmatter names it.
    When they disagree, every cross-reference in the other skills is wrong."""
    fm = _frontmatter(os.path.join(SKILLS_DIR, skill, "SKILL.md"))
    assert fm["name"] == skill


@pytest.mark.parametrize("skill", SKILL_DIRS)
def test_skill_name_is_letters_numbers_and_hyphens_only(skill):
    """METHOD.md's frontmatter rule."""
    fm = _frontmatter(os.path.join(SKILLS_DIR, skill, "SKILL.md"))
    assert NAME_RE.match(fm["name"]), fm["name"]


@pytest.mark.parametrize("skill", SKILL_DIRS)
def test_skill_description_states_triggering_conditions(skill):
    """METHOD.md: descriptions are third person and start with "Use when".
    The rule exists because an agent that reads a workflow summary follows
    the summary instead of the skill body - an empirical finding, per
    METHOD.md, not a style rule."""
    fm = _frontmatter(os.path.join(SKILLS_DIR, skill, "SKILL.md"))
    assert fm["description"].startswith("Use when"), fm["description"]


# --- cross-file links: the "do not move or rename it" guard ---

@pytest.mark.parametrize("rel_path,abs_path", SKILL_MD_FILES,
                          ids=[p for p, _ in SKILL_MD_FILES])
def test_relative_links_in_skill_files_resolve(rel_path, abs_path):
    with open(abs_path, encoding="utf-8") as f:
        content = f.read()
    base = os.path.dirname(abs_path)
    broken = []
    for target in RELATIVE_LINK_RE.findall(content):
        target = target.strip().split(" ")[0]
        if "://" in target or target.startswith("#") or target.startswith("mailto:"):
            continue
        resolved = os.path.normpath(os.path.join(base, target.split("#")[0]))
        if not os.path.exists(resolved):
            broken.append(target)
    assert broken == [], f"{rel_path} has unresolvable relative links: {broken}"


def test_the_cross_skill_links_that_exist_are_actually_being_checked():
    """A control on the test above: if the link regex ever stops matching, the
    resolver passes vacuously on every file. Pin the count that exists today
    so a silent regex regression fails here instead of going unnoticed."""
    total = 0
    for _rel, abs_path in SKILL_MD_FILES:
        with open(abs_path, encoding="utf-8") as f:
            content = f.read()
        for target in RELATIVE_LINK_RE.findall(content):
            target = target.strip().split(" ")[0]
            if "://" in target or target.startswith("#") or target.startswith("mailto:"):
                continue
            total += 1
    assert total >= 4, f"expected the known cross-skill links, found {total}"


@pytest.mark.parametrize("referenced", [
    "se-requirements/ears-patterns.md",
    "se-requirements/incose-criteria.md",
])
def test_files_the_plan_says_not_to_move_still_exist(referenced):
    """Both are named "do not move or rename it" in the plan, because Plan B2's
    se:change-management reads them as well as the skills that link them."""
    assert os.path.isfile(os.path.join(SKILLS_DIR, *referenced.split("/")))


# --- the never-delete rule, which shipped contradicted twice ---

def test_ears_patterns_still_carries_the_immutable_id_rule():
    """The rule every other skill defers to. If it is ever softened or moved,
    the deferrals elsewhere become dangling claims."""
    path = os.path.join(SKILLS_DIR, "se-requirements", "ears-patterns.md")
    with open(path, encoding="utf-8") as f:
        content = f.read()
    for needle in ("Never renumber", "Never delete", "Never reuse", "status: retired"):
        assert needle in content, f"ears-patterns.md no longer states '{needle}'"


@pytest.mark.parametrize("rel_path,abs_path", SKILL_MD_FILES,
                          ids=[p for p, _ in SKILL_MD_FILES])
def test_no_skill_says_a_struck_requirement_is_deleted_now(rel_path, abs_path):
    """F3 regression pin.

    "...is deleted now, before it has an ID anyone depends on" shipped in
    se-requirements AND in se-domain-research. Task 11 removed it from the
    first; it survived in the second until the branch's final review, and
    following it produced real ID reuse against ears-patterns.md's
    never-reuse rule.

    This is deliberately a *literal* pin on the phrase that shipped twice,
    not a semantic guard. A sentence-level heuristic cannot separate this
    assertion from the prohibitions that legitimately contain the same words
    ("Never delete a requirement...", "A requirement the user strikes here is
    status: retired, not deleted"), so it would either miss the defect or fail
    on the fix. A narrow pin that actually discriminates beats a broad one
    that does not.
    """
    with open(abs_path, encoding="utf-8") as f:
        content = f.read()
    assert "deleted now" not in content, (
        f"{rel_path} tells the agent a struck requirement is deleted; "
        f"ears-patterns.md says set status: retired and never reuse the ID")


SKILL_REF_RE = re.compile(r"\bse:([a-z][a-z-]+)\b")


@pytest.mark.parametrize("rel_path,abs_path", SKILL_MD_FILES,
                          ids=[p for p, _ in SKILL_MD_FILES])
def test_every_se_skill_named_in_a_skill_exists(rel_path, abs_path):
    """Three shipped skills named se:writing-plans for a whole plan before it
    existed. A handoff to a skill the plugin does not load is a dead end the
    user hits at runtime and no test saw."""
    with open(abs_path, encoding="utf-8") as f:
        content = f.read()
    named = {f"se-{m}" for m in SKILL_REF_RE.findall(content)}
    known = set(SKILL_DIRS)
    missing = sorted(n for n in named if n not in known)
    assert missing == [], f"{rel_path} hands off to skills that do not exist: {missing}"


# --- the plugin manifest ---

def test_plugin_json_parses_and_carries_its_required_keys():
    """`author` is an OBJECT, not a string. This test asserted a string until
    Plan B2's integration run put the manifest through `claude plugin validate`
    for the first time and got `author: Invalid input: expected object,
    received string` — a shipped manifest the CLI refused to load, which no
    test saw because the test encoded the same wrong shape as the manifest."""
    with open(PLUGIN_JSON, encoding="utf-8") as f:
        manifest = json.load(f)
    for key in ("name", "version", "description"):
        assert isinstance(manifest.get(key), str) and manifest[key].strip(), \
            f"plugin.json is missing '{key}'"
    author = manifest.get("author")
    assert isinstance(author, dict), \
        f"plugin.json 'author' must be an object, got {type(author).__name__}"
    assert isinstance(author.get("name"), str) and author["name"].strip(), \
        "plugin.json 'author' is missing a non-empty 'name'"
    assert manifest["name"] == "se-skills"
    assert re.match(r"^\d+\.\d+\.\d+$", manifest["version"]), manifest["version"]


def test_claude_plugin_validate_accepts_this_plugin():
    """Run the schema's own validator instead of hand-asserting its schema.

    The test above encodes the manifest's shape by hand, and that is exactly
    how the shipped manifest stayed broken: the test believed `author` was a
    string, the manifest said the same, and the suite was green on a manifest
    the CLI refused. A hand-written assertion about a schema-backed artifact
    certifies whatever shape its author believed in. The next schema change
    - a new required key, an `email` made mandatory, a marketplace manifest
    arriving - reproduces the identical failure with the identical symptom
    unless something runs the real validator. This does.
    """
    claude = shutil.which("claude")
    if claude is None:
        pytest.skip("the `claude` CLI is not on PATH; nothing can run the "
                    "plugin schema's own validator here")
    proc = subprocess.run([claude, "plugin", "validate", "."],
                          cwd=REPO_ROOT, capture_output=True, text=True, timeout=120)
    assert proc.returncode == 0, (
        f"`claude plugin validate .` exited {proc.returncode}\n"
        f"stdout:\n{proc.stdout}\nstderr:\n{proc.stderr}")


# --- final-review fixes (Plan 2): literal pins on the skill text ---

def _skill_text(skill):
    with open(os.path.join(SKILLS_DIR, skill, "SKILL.md"), encoding="utf-8") as f:
        return f.read()


@pytest.mark.parametrize("skill", ["se-requirements", "se-increment", "se-build", "se-verification"])
def test_skills_that_raise_customer_questions_apply_the_answers(skill):
    """C1: a gate that files a customer_question must also say how its answer is applied."""
    text = _skill_text(skill)
    assert "customer_question" in text and "`applied`" in text


def test_router_sends_answered_customer_questions_to_the_skill_that_raised_them():
    row = [l for l in _skill_text("se-develop").splitlines() if l.startswith("| `items_unapplied`")][0]
    assert "Q-" in row


@pytest.mark.parametrize("skill", ["se-experiment", "se-build"])
def test_handoffs_to_change_management_write_state(skill):
    """I1: a handoff the router cannot see loops back to the same skill."""
    assert "--mark-suspect" in _skill_text(skill)


def test_se_build_has_one_rule_for_open_items():
    """I2: 'build the others meanwhile' contradicted the router's experiments_open."""
    assert "meanwhile" not in _skill_text("se-build")


def test_change_management_moves_reopened_work_into_the_active_increment():
    """I3: the router only sees the active increment."""
    assert "active increment" in _skill_text("se-change-management")


@pytest.mark.parametrize("skill", ["se-requirements", "se-increment"])
def test_gates_refresh_the_snapshot_that_changed_reads(skill):
    """I4: --changed compares against req_hashes.json, which only se_trace.py writes."""
    assert "se_trace.py" in _skill_text(skill)


def test_simulator_checks_are_linkable_evidence():
    """I5: 'simulator check' is not a moc value."""
    text = _skill_text("se-verification")
    assert "VERIFIES:" in text and "moc: demonstration" in text


def test_accepted_risk_exits_are_mechanical():
    """I6: validate_items requires the note in 'answer'; the stall exit must say what to write."""
    assert "goes in `answer`" in _skill_text("se-requirements")
    assert "accepted_risk" in _skill_text("se-develop")


@pytest.mark.parametrize("skill", ["se-requirements", "se-increment"])
def test_design_decision_ids_are_one_sequence(skill):
    """I7: D- IDs had two homes and collided."""
    assert "one sequence" in _skill_text(skill)


def test_research_setting_is_read_somewhere():
    """I8: se-tailoring asks for research; some skill must act on it."""
    assert "`research`" in _skill_text("se-requirements")


def test_round_cap_red_flag_counts_correctly():
    """I11: with a cap of 2, the third entry is already the violation."""
    text = _skill_text("se-requirements")
    assert "third entry" in text and "fourth line" not in text


def test_no_validation_toolchain_in_skills_or_script_fixtures():
    """I10: the plugin ships scripts/tests/fixtures too."""
    assert "colcon" not in _skill_text("se-tailoring")
    fixtures = os.path.join(REPO_ROOT, "scripts", "tests", "fixtures")
    hits = []
    for dirpath, _dirs, files in os.walk(fixtures):
        for name in files:
            with open(os.path.join(dirpath, name), encoding="utf-8", errors="replace") as f:
                if FORBIDDEN_DOMAIN_RE.search(f.read().replace("-", " ").replace("_", " ")):
                    hits.append(os.path.relpath(os.path.join(dirpath, name), REPO_ROOT))
    assert hits == [], f"validation-project vocabulary in script fixtures: {hits}"
