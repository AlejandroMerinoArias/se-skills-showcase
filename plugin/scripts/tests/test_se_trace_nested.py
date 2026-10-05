"""A decomposed parent is verified through its children, not by a test of its
own. Rendering it UNVERIFIED makes a full-mode tree permanently unable to reach
a clean verification matrix."""

import se_trace


def _req(rid, **overrides):
    req = {
        "id": rid, "text": f"text for {rid}", "category": "functional",
        "criticality": "B", "rationale": None, "source": None, "parent": None,
        "allocated_to": None, "moc": "test", "verified_by": [], "status": "validated",
        "waiver": None, "suspect": False, "target": None, "threshold": None,
        "history": [],
    }
    req.update(overrides)
    return req


def _data(*reqs):
    return {"meta": {"project": "p", "mode": "full", "levels": ["SYS", "ITEM"]},
            "requirements": list(reqs)}


def _result_for(rows, rid):
    return next(r["result"] for r in rows if r["id"] == rid)


def test_decomposed_parent_renders_nested_not_unverified():
    data = _data(
        _req("SYS-F-001"),
        _req("ITEM-F-001", parent="SYS-F-001", verified_by=["t.py::test_a"]),
    )
    rows = se_trace.build_matrix_rows(data)
    assert _result_for(rows, "SYS-F-001") == "NESTED"


def test_childless_requirement_with_no_test_still_unverified():
    rows = se_trace.build_matrix_rows(_data(_req("SYS-F-001")))
    assert _result_for(rows, "SYS-F-001") == "UNVERIFIED"


def test_parent_with_its_own_tests_keeps_the_test_result():
    data = _data(
        _req("SYS-F-001", verified_by=["t.py::test_parent"]),
        _req("ITEM-F-001", parent="SYS-F-001"),
    )
    rows = se_trace.build_matrix_rows(data, junit_results={"test_parent": "pass"})
    assert _result_for(rows, "SYS-F-001") == "PASS"


def test_decomposed_parent_with_analysis_moc_is_also_nested():
    data = _data(
        _req("SYS-F-001", moc="analysis"),
        _req("ITEM-F-001", parent="SYS-F-001"),
    )
    rows = se_trace.build_matrix_rows(data)
    assert _result_for(rows, "SYS-F-001") == "NESTED"


def test_decomposed_parent_does_not_raise_untested_warning():
    data = _data(
        _req("SYS-F-001"),
        _req("ITEM-F-001", parent="SYS-F-001", verified_by=["t.py::test_a"]),
    )
    findings = se_trace.generate_trace_findings(data, [], [])
    untested = [f for f in findings
                if f.check == "trace_untested_req" and f.req_id == "SYS-F-001"]
    assert untested == []


def test_childless_untested_requirement_still_warns():
    findings = se_trace.generate_trace_findings(_data(_req("SYS-F-001")), [], [])
    checks = [(f.check, f.req_id) for f in findings]
    assert ("trace_untested_req", "SYS-F-001") in checks
