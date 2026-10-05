import os

import se_lib
import se_check
from helpers import make_requirement, make_data

FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures")


def test_derived_without_rationale_flagged():
    data = se_lib.load_requirements_yaml(os.path.join(FIXTURES, "derived_no_rationale.yaml"))
    findings = se_check.check_derived_rationale(data)
    assert len(findings) == 1
    assert findings[0].req_id == "SYS-D-001"
    assert findings[0].level == "ERROR"
    assert "rationale" in findings[0].message


def test_derived_with_rationale_passes():
    data = make_data([make_requirement(id="SYS-D-001", category="derived", rationale="Sensor latency analysis.")])
    assert se_check.check_derived_rationale(data) == []


def test_non_derived_never_flagged():
    data = make_data([make_requirement(id="SYS-F-001", category="functional", rationale=None)])
    assert se_check.check_derived_rationale(data) == []
