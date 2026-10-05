import os

import se_lib
import se_check
from helpers import make_requirement, make_data

FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures")


def test_orphan_detected():
    data = se_lib.load_requirements_yaml(os.path.join(FIXTURES, "orphan.yaml"))
    findings = se_check.check_orphans_and_cycles(data)
    orphan_findings = [f for f in findings if f.req_id == "ITEM-F-002"]
    assert len(orphan_findings) == 1
    assert orphan_findings[0].level == "ERROR"
    assert "orphan" in orphan_findings[0].message


def test_cycle_detected():
    data = se_lib.load_requirements_yaml(os.path.join(FIXTURES, "cycle.yaml"))
    findings = se_check.check_orphans_and_cycles(data)
    cycle_findings = [f for f in findings if "cycle" in f.message]
    assert len(cycle_findings) == 1
    assert cycle_findings[0].level == "ERROR"


def test_missing_parent_reported():
    data = make_data([make_requirement(id="SYS-F-001", parent="SYS-F-999")], levels=["SYS"])
    findings = se_check.check_orphans_and_cycles(data)
    assert any(f.req_id == "SYS-F-001" and "does not exist" in f.message for f in findings)


def test_valid_tree_has_no_findings():
    data = make_data([
        make_requirement(id="SYS-F-001", parent=None),
        make_requirement(id="SYS-F-002", parent="SYS-F-001", category="derived", rationale="why"),
    ], levels=["SYS"])
    assert se_check.check_orphans_and_cycles(data) == []
