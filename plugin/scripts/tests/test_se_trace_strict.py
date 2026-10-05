"""--strict: the verification gate (spec section 7's exit condition, and
section 3 rule 7's 'elevated to a blocking condition at the final
verification gate').

Without --strict nothing changes: the same findings, the same WARNING levels,
the same exit 0. The flag is what se:verification runs, once, at the end."""

import se_trace


def _req(rid, **overrides):
    req = {
        "id": rid, "text": f"text for {rid}", "category": "functional",
        "criticality": "B", "rationale": None, "source": None, "parent": None,
        "allocated_to": None, "moc": "test", "verified_by": [], "status": "implemented",
        "waiver": None, "suspect": False, "target": None, "threshold": None,
        "history": [],
    }
    req.update(overrides)
    return req


def _data(*reqs):
    return {"meta": {"project": "p", "mode": "lite", "levels": ["SYS"]},
            "requirements": list(reqs)}


def _levels(findings, check):
    return [f.level for f in findings if f.check == check]


def test_unannotated_test_is_a_warning_without_strict():
    defs = [se_trace.TestDef(file="t.py", name="test_a", line=1, req_ids=[])]
    findings = se_trace.generate_trace_findings(_data(), defs, [])
    assert _levels(findings, "trace_missing_annotation") == ["WARNING"]


def test_unannotated_test_is_an_error_with_strict():
    defs = [se_trace.TestDef(file="t.py", name="test_a", line=1, req_ids=[])]
    findings = se_trace.generate_trace_findings(_data(), defs, [], strict=True)
    assert _levels(findings, "trace_missing_annotation") == ["ERROR"]


def test_untested_requirement_is_an_error_with_strict():
    findings = se_trace.generate_trace_findings(_data(_req("SYS-F-001")), [], [],
                                                 strict=True)
    assert _levels(findings, "trace_untested_req") == ["ERROR"]


def test_strict_does_not_elevate_the_undetailed_warning():
    """trace_undetailed fires on decomposed-but-untested shapes that the gate
    already catches through their children. Elevating it would fail projects
    the gate is designed to pass."""
    findings = se_trace.generate_trace_findings(_data(_req("SYS-F-001")), [], [],
                                                 strict=True)
    assert _levels(findings, "trace_undetailed") == ["WARNING"]


def test_gate_flags_a_requirement_that_never_reached_verified():
    data = _data(_req("SYS-F-001", verified_by=["t.py::test_a"]))
    findings = se_trace._gate_findings(data, {"test_a": "pass"})
    assert _levels(findings, "gate_unverified") == ["ERROR"]


def test_gate_passes_a_verified_requirement():
    data = _data(_req("SYS-F-001", status="verified", verified_by=["t.py::test_a"]))
    assert se_trace._gate_findings(data, {"test_a": "pass"}) == []


def test_gate_passes_a_waived_requirement():
    data = _data(_req("SYS-F-001", waiver="user accepted 2026-08-01: no rig"))
    assert se_trace._gate_findings(data, None) == []


def test_gate_ignores_retired_requirements():
    assert se_trace._gate_findings(_data(_req("SYS-F-001", status="retired")), None) == []


def test_gate_flags_a_failing_test_even_at_status_verified():
    """The status field is written by an agent; the JUnit result is not. When
    they disagree, the gate believes the results."""
    data = _data(_req("SYS-F-001", status="verified", verified_by=["t.py::test_a"]))
    findings = se_trace._gate_findings(data, {"test_a": "fail"})
    assert _levels(findings, "gate_failed") == ["ERROR"]


def test_gate_passes_a_nested_parent():
    """The parent is deliberately left at 'implemented': a decomposed parent is
    verified through its children and has no test of its own, so requiring it
    to reach 'verified' by itself would put the same permanent floor under the
    gate that the NESTED matrix result exists to remove."""
    data = _data(_req("SYS-F-001", status="implemented"),
                 _req("SYS-F-002", parent="SYS-F-001", status="verified",
                      verified_by=["t.py::test_a"]))
    assert se_trace._gate_findings(data, {"test_a": "pass"}) == []


def test_gate_flags_verified_by_with_no_results_file():
    """This is the '--strict without --results' case, and it is the one that
    matters most: status: verified alone must not be enough to close the
    gate when nothing confirms the linked test ran."""
    data = _data(_req("SYS-F-001", status="verified", verified_by=["t.py::test_a"]))
    findings = se_trace._gate_findings(data, None)
    assert _levels(findings, "gate_unknown") == ["ERROR"]


def test_gate_flags_verified_by_absent_from_the_results_given():
    """The renamed/skipped-test case: a results file was given, but it does
    not name this requirement's linked test."""
    data = _data(_req("SYS-F-001", status="verified", verified_by=["t.py::test_a"]))
    findings = se_trace._gate_findings(data, {"test_b": "pass"})
    assert _levels(findings, "gate_unknown") == ["ERROR"]


def test_gate_passes_a_waived_requirement_with_no_results_file_at_all():
    """Guards the ruling, not the new gate_unknown branch: a project with no
    verified_by test evidence at all (moc: analysis here, waived rather than
    tested) must still be able to close the gate without a JUnit file. This
    would pass even if the gate_unknown branch were deleted — the requirement
    never produces an UNKNOWN result because it has no verified_by to begin
    with, so this is a regression guard on the ruling's carve-out, not a test
    of the new code."""
    data = _data(_req("SYS-F-001", moc="analysis", verified_by=[],
                       waiver="user accepted 2026-08-01: no rig"))
    assert se_trace._gate_findings(data, None) == []


def test_strict_run_exits_1_on_an_unverified_project(tmp_path, capsys):
    se_dir = tmp_path / "se"
    se_dir.mkdir()
    (se_dir / "requirements.yaml").write_text(
        "meta:\n  project: p\n  mode: lite\n  levels: [SYS]\n"
        "requirements:\n  - id: SYS-F-001\n    text: the system shall do a thing\n"
        "    category: functional\n    criticality: B\n    rationale: null\n"
        "    source: null\n    parent: null\n    allocated_to: null\n"
        "    moc: test\n    verified_by: []\n    status: implemented\n"
        "    waiver: null\n    suspect: false\n    target: null\n"
        "    threshold: null\n    history: []\n", encoding="utf-8")
    tests_dir = tmp_path / "tests"
    tests_dir.mkdir()
    (tests_dir / "test_x.py").write_text(
        "# VERIFIES: SYS-F-001\ndef test_a():\n    pass\n", encoding="utf-8")

    assert se_trace.main([str(se_dir), "--tests", str(tests_dir)]) == 0
    assert se_trace.main([str(se_dir), "--tests", str(tests_dir), "--strict"]) == 1
    # No --results is given, so the linked test's evidence is UNKNOWN, not
    # merely unverified by status — gate_unknown, not gate_unverified.
    assert "gate_unknown" in capsys.readouterr().out
