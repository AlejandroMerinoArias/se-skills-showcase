"""check_allocation - allocation completeness, checked by the script.

Spec section 1: "Everything a script can check, a script checks - not an LLM."
Before this check existed, se_check.py exited 0 with every validated
requirement unallocated (including a CRIT-A one) and exited 0 with a retired
requirement still allocated to modules, and se-architecture's exit gate
compensated with an inline one-liner in a Markdown file.

The two directions are deliberately asymmetric:

- validated + allocated_to null is a WARNING, because it is a *legal
  intermediate state* - exactly what a project looks like after
  se:requirements-validation and before se:architecture has run. It is what
  pressure-tests/fixtures/state-validated-unallocated/ exists to represent,
  and test_state_fixtures.py asserts that fixture is se_check-clean.
- retired + a non-null allocated_to is an ERROR, because it is wrong in every
  phase: it makes a module responsible for building something nobody agreed
  to build.
"""

import os

import yaml

import se_check
from helpers import make_requirement, make_data


def _write_requirements(se_dir, data):
    os.makedirs(se_dir, exist_ok=True)
    with open(os.path.join(se_dir, "requirements.yaml"), "w", encoding="utf-8") as f:
        yaml.safe_dump(data, f, sort_keys=False)


def _findings_for(*requirements):
    return se_check.check_allocation(make_data(list(requirements)))


# --- validated but unallocated: WARNING, never ERROR ---

def test_validated_requirement_with_null_allocated_to_warns():
    findings = _findings_for(
        make_requirement(id="SYS-F-001", status="validated", allocated_to=None))
    assert len(findings) == 1
    assert findings[0].level == "WARNING"
    assert findings[0].check == "check_allocation"
    assert findings[0].req_id == "SYS-F-001"


def test_validated_crit_a_requirement_with_null_allocated_to_warns():
    """The review's reproduction: a CRIT-A requirement nobody was made
    responsible for building produced zero findings and exit 0."""
    findings = _findings_for(
        make_requirement(id="SYS-S-001", status="validated",
                          criticality="A", allocated_to=None))
    assert [f.level for f in findings] == ["WARNING"]


def test_validated_requirement_with_empty_list_allocated_to_warns():
    """An empty list is unallocated just as null is - allocated_to holds a
    module name or a list of module names, and [] names nobody."""
    findings = _findings_for(
        make_requirement(id="SYS-F-001", status="validated", allocated_to=[]))
    assert [f.level for f in findings] == ["WARNING"]


def test_validated_requirement_with_allocated_to_is_clean():
    assert _findings_for(
        make_requirement(id="SYS-F-001", status="validated",
                          allocated_to="motion_controller")) == []


def test_validated_requirement_with_list_allocated_to_is_clean():
    assert _findings_for(
        make_requirement(id="SYS-F-001", status="validated",
                          allocated_to=["storage", "export"])) == []


# --- retired and still allocated: ERROR ---

def test_retired_requirement_with_allocated_to_is_an_error():
    findings = _findings_for(
        make_requirement(id="SYS-F-001", status="retired",
                          allocated_to=["storage", "export"]))
    assert len(findings) == 1
    assert findings[0].level == "ERROR"
    assert findings[0].check == "check_allocation"
    assert findings[0].req_id == "SYS-F-001"


def test_retired_requirement_with_null_allocated_to_is_clean():
    assert _findings_for(
        make_requirement(id="SYS-F-001", status="retired", allocated_to=None)) == []


# --- the states this check is deliberately silent about ---

def test_draft_requirement_with_null_allocated_to_is_clean():
    """Pins the narrowing. Requirements are unallocated by definition before
    architecture runs, and the derived children se:architecture writes enter
    at status: draft - so warning on draft would fire on every project that
    has ever captured a requirement. se-architecture's Step 2 command is what
    covers the draft children inside that phase."""
    assert _findings_for(
        make_requirement(id="SYS-F-001", status="draft", allocated_to=None)) == []


def test_non_mapping_requirement_is_skipped():
    assert se_check.check_allocation(make_data(["not a mapping"])) == []


# --- registered in run_all_checks, and the exit codes that follow ---

def test_check_allocation_runs_as_part_of_run_all_checks(tmp_path):
    data = make_data([make_requirement(id="SYS-F-001", status="retired",
                                        allocated_to="storage")])
    findings = se_check.run_all_checks(data, str(tmp_path))
    assert any(f.check == "check_allocation" and f.level == "ERROR"
               for f in findings), [f.format() for f in findings]


def test_main_exits_0_with_a_warning_on_the_validated_unallocated_state(tmp_path, capsys):
    """The legal intermediate state stays clean at exit 0 and still reports."""
    _write_requirements(tmp_path, make_data([
        make_requirement(id="SYS-F-001", status="validated", allocated_to=None),
        make_requirement(id="SYS-S-001", status="validated",
                          criticality="A", allocated_to=None),
    ]))
    exit_code = se_check.main([str(tmp_path)])
    out = capsys.readouterr().out
    assert exit_code == 0, out
    assert out.count("[WARNING] check_allocation") == 2, out


def test_main_exits_1_on_a_retired_requirement_that_is_still_allocated(tmp_path, capsys):
    _write_requirements(tmp_path, make_data([
        make_requirement(id="SYS-F-001", status="retired",
                          allocated_to=["storage", "export"]),
    ]))
    exit_code = se_check.main([str(tmp_path)])
    out = capsys.readouterr().out
    assert exit_code == 1, out
    assert "[ERROR] check_allocation" in out


def test_readme_documents_check_allocation():
    readme = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
        "README.md")
    with open(readme, encoding="utf-8") as f:
        content = f.read()
    assert "allocated_to" in content
    assert "check_allocation" in content, \
        "README.md's numbered check list does not mention check_allocation"
