"""Rule-3 symmetry (moc: test at status: verified needs a linked test) and
confinement of evidence paths to se/evidence/."""

import os

import se_check


def _req(rid, **overrides):
    req = {
        "id": rid, "text": f"text for {rid}", "category": "functional",
        "criticality": "B", "rationale": None, "source": None, "parent": None,
        "allocated_to": None, "moc": "test", "verified_by": [], "status": "verified",
        "waiver": None, "suspect": False, "target": None, "threshold": None,
        "history": [],
    }
    req.update(overrides)
    return req


def _data(*reqs):
    return {"meta": {"project": "p", "mode": "lite", "levels": ["SYS"]},
            "requirements": list(reqs)}


def _checks(findings):
    return [(f.level, f.check, f.req_id) for f in findings]


def test_verified_test_req_without_linked_test_is_an_error():
    findings = se_check.check_test_moc_verified(_data(_req("SYS-F-001")))
    assert _checks(findings) == [("ERROR", "check_test_moc_verified", "SYS-F-001")]


def test_verified_test_req_with_linked_test_is_clean():
    data = _data(_req("SYS-F-001", verified_by=["t.py::test_a"]))
    assert se_check.check_test_moc_verified(data) == []


def test_unverified_status_is_not_gated():
    data = _data(_req("SYS-F-001", status="implemented"))
    assert se_check.check_test_moc_verified(data) == []


def test_analysis_moc_is_not_touched_by_this_check():
    data = _data(_req("SYS-F-001", moc="analysis"))
    assert se_check.check_test_moc_verified(data) == []


def test_evidence_path_escaping_se_dir_is_rejected(tmp_path):
    se_dir = tmp_path / "se"
    (se_dir / "evidence").mkdir(parents=True)
    outside = tmp_path / "secret.md"
    outside.write_text("x", encoding="utf-8")
    data = _data(_req("SYS-F-001", moc="analysis",
                      verified_by=["evidence/../../secret.md"]))
    findings = se_check.check_moc_evidence(data, str(se_dir))
    assert [f.level for f in findings] == ["ERROR"]
    assert "outside" in findings[0].message


def test_absolute_evidence_path_is_rejected(tmp_path):
    se_dir = tmp_path / "se"
    (se_dir / "evidence").mkdir(parents=True)
    data = _data(_req("SYS-F-001", moc="analysis",
                      verified_by=[str(tmp_path / "secret.md")]))
    findings = se_check.check_moc_evidence(data, str(se_dir))
    assert [f.level for f in findings] == ["ERROR"]


def test_absolute_path_inside_evidence_dir_is_still_rejected(tmp_path):
    # Regression guard for the isabs branch specifically: the file exists and
    # the resolved path is inside se/evidence/, so only the isabs-first check
    # (not containment) can be responsible for rejecting it. If the isabs
    # check were deleted, containment alone would accept this path and the
    # test would fail.
    se_dir = tmp_path / "se"
    (se_dir / "evidence").mkdir(parents=True)
    inside_file = se_dir / "evidence" / "note.md"
    inside_file.write_text("x", encoding="utf-8")
    data = _data(_req("SYS-F-001", moc="analysis",
                      verified_by=[str(inside_file)]))
    findings = se_check.check_moc_evidence(data, str(se_dir))
    assert [f.level for f in findings] == ["ERROR"]


def test_evidence_path_inside_evidence_dir_is_accepted(tmp_path):
    se_dir = tmp_path / "se"
    (se_dir / "evidence" / "sub").mkdir(parents=True)
    (se_dir / "evidence" / "sub" / "note.md").write_text("x", encoding="utf-8")
    data = _data(_req("SYS-F-001", moc="analysis",
                      verified_by=["evidence/sub/note.md"]))
    assert se_check.check_moc_evidence(data, str(se_dir)) == []


def test_run_all_checks_includes_the_new_check():
    findings = se_check.run_all_checks(_data(_req("SYS-F-001")), os.getcwd())
    assert any(f.check == "check_test_moc_verified" for f in findings)
