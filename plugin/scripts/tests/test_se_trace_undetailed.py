import se_trace
from helpers import make_requirement, make_data


def test_apply_verified_by_preserves_evidence_links():
    data = make_data([
        make_requirement(id="SYS-F-001", moc="test", verified_by=[]),
        make_requirement(id="SYS-S-002", moc="analysis",
                         verified_by=["evidence/sys-s-002-analysis.md"]),
    ])
    out = se_trace.apply_verified_by(data, {"SYS-F-001": ["t.py::test_a"]})
    reqs = {r["id"]: r for r in out["requirements"]}
    assert reqs["SYS-F-001"]["verified_by"] == ["t.py::test_a"]
    assert reqs["SYS-S-002"]["verified_by"] == ["evidence/sys-s-002-analysis.md"]


def test_undetailed_requirement_flagged():
    data = make_data([
        make_requirement(id="SYS-F-001", moc="test", verified_by=[]),
    ])
    findings = se_trace.generate_trace_findings(data, [], [])
    assert any(f.check == "trace_undetailed" and f.req_id == "SYS-F-001"
               for f in findings)


def test_parent_with_children_and_verified_leaf_not_undetailed():
    data = make_data([
        make_requirement(id="SYS-F-001", moc="test", verified_by=[]),
        make_requirement(id="ITEM-F-001", parent="SYS-F-001", moc="test",
                         verified_by=["t.py::test_b"]),
    ], levels=["SYS", "ITEM"])
    findings = se_trace.generate_trace_findings(data, [], [])
    flagged = {f.req_id for f in findings if f.check == "trace_undetailed"}
    assert "SYS-F-001" not in flagged   # has a child
    assert "ITEM-F-001" not in flagged  # has a linked test


def test_retired_requirement_not_undetailed():
    data = make_data([
        make_requirement(id="SYS-F-009", moc="test", verified_by=[],
                         status="retired"),
    ])
    findings = se_trace.generate_trace_findings(data, [], [])
    assert not any(f.check == "trace_undetailed" for f in findings)


def test_matrix_row_evidence_for_analysis_req():
    data = make_data([
        make_requirement(id="SYS-S-002", moc="analysis",
                         verified_by=["evidence/sys-s-002-analysis.md"]),
    ])
    rows = se_trace.build_matrix_rows(data)
    assert rows[0]["result"] == "EVIDENCE"
