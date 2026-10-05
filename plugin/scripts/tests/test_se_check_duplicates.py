import se_check
from helpers import make_requirement, make_data


def test_check_duplicate_ids_flags_repeats():
    data = make_data([
        make_requirement(id="SYS-F-001"),
        make_requirement(id="SYS-F-001"),
        make_requirement(id="SYS-F-002"),
    ])
    findings = se_check.check_duplicate_ids(data)
    assert len(findings) == 1
    assert findings[0].level == "ERROR"
    assert findings[0].req_id == "SYS-F-001"
    assert "duplicate" in findings[0].message.lower()


def test_check_duplicate_ids_no_findings_when_unique():
    data = make_data([
        make_requirement(id="SYS-F-001"),
        make_requirement(id="SYS-F-002"),
    ])
    assert se_check.check_duplicate_ids(data) == []
