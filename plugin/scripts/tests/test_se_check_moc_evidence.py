import se_check
import se_lib
from helpers import make_requirement, make_data


def test_missing_evidence_reference(tmp_path):
    data = make_data([make_requirement(id="SYS-S-001", moc="analysis", status="verified", verified_by=[])])
    findings = se_check.check_moc_evidence(data, str(tmp_path))
    assert any(f.req_id == "SYS-S-001" and f.level == "ERROR" for f in findings)


def test_evidence_file_missing_on_disk(tmp_path):
    data = make_data([make_requirement(
        id="SYS-S-002", moc="inspection", status="verified",
        verified_by=["evidence/missing_note.md"])])
    findings = se_check.check_moc_evidence(data, str(tmp_path))
    assert any(f.req_id == "SYS-S-002" and "does not exist" in f.message for f in findings)


def test_evidence_file_present_passes(tmp_path):
    evidence_dir = tmp_path / "evidence"
    evidence_dir.mkdir()
    (evidence_dir / "note.md").write_text("Signed inspection note.")
    data = make_data([make_requirement(
        id="SYS-S-003", moc="inspection", status="verified",
        verified_by=["evidence/note.md"])])
    assert se_check.check_moc_evidence(data, str(tmp_path)) == []


def test_moc_test_never_checked_here():
    data = make_data([make_requirement(id="SYS-F-001", moc="test", status="verified", verified_by=[])])
    assert se_check.check_moc_evidence(data, "/nonexistent") == []


def test_not_yet_verified_not_checked(tmp_path):
    data = make_data([make_requirement(id="SYS-S-004", moc="analysis", status="draft", verified_by=[])])
    assert se_check.check_moc_evidence(data, str(tmp_path)) == []


def test_demonstration_missing_evidence_reference(tmp_path):
    """moc: demonstration is the fourth MOC_ENUM member and was covered by no
    check at all: check_moc_evidence took only analysis|inspection and
    check_test_moc_verified only test. A demonstration requirement at
    status: verified with an empty verified_by therefore passed se_check.py
    at exit 0, passed se_trace.py --strict at exit 0, and made --route report
    `complete` — on a project with no evidence of any kind. No fixture and no
    test in this repo used the value, which is why fourteen task-scoped
    reviews did not see it."""
    data = make_data([make_requirement(id="SYS-S-005", moc="demonstration",
                                       status="verified", verified_by=[])])
    findings = se_check.check_moc_evidence(data, str(tmp_path))
    assert any(f.req_id == "SYS-S-005" and f.level == "ERROR" for f in findings)


def test_demonstration_evidence_file_missing_on_disk(tmp_path):
    data = make_data([make_requirement(
        id="SYS-S-006", moc="demonstration", status="verified",
        verified_by=["evidence/demo_record.md"])])
    findings = se_check.check_moc_evidence(data, str(tmp_path))
    assert any(f.req_id == "SYS-S-006" and "does not exist" in f.message for f in findings)


def test_demonstration_evidence_file_present_passes(tmp_path):
    evidence_dir = tmp_path / "evidence"
    evidence_dir.mkdir()
    (evidence_dir / "demo_record.md").write_text("Witnessed demonstration, 2026-08-13.")
    data = make_data([make_requirement(
        id="SYS-S-007", moc="demonstration", status="verified",
        verified_by=["evidence/demo_record.md"])])
    assert se_check.check_moc_evidence(data, str(tmp_path)) == []


def test_verified_demonstration_without_evidence_fails_the_whole_gate(tmp_path):
    """End-to-end counterpart: the unit check above is what the exit code is
    built from, but the defect was that the *command* returned 0. Assert the
    exit code, not just the finding."""
    import yaml
    data = make_data([make_requirement(id="SYS-S-008", moc="demonstration",
                                       status="verified", verified_by=[])])
    with open(tmp_path / "requirements.yaml", "w", encoding="utf-8") as f:
        yaml.safe_dump(data, f, sort_keys=False)
    assert se_check.main([str(tmp_path)]) == 1


def test_every_moc_enum_member_is_gated_at_status_verified(tmp_path):
    """The structural guard, not another instance: iterate MOC_ENUM itself so
    a fifth member added to se_lib without a check in se_check fails here
    rather than shipping as a second `demonstration`. A hand-written list of
    the four values would reproduce exactly the defect this closes."""
    ungated = []
    for moc in sorted(se_lib.MOC_ENUM):
        data = make_data([make_requirement(id="SYS-F-001", moc=moc,
                                           status="verified", verified_by=[])])
        findings = se_check.run_all_checks(data, str(tmp_path))
        if not any(f.level == "ERROR" and f.req_id == "SYS-F-001" for f in findings):
            ungated.append(moc)
    assert ungated == [], (
        f"moc value(s) {ungated} reach status 'verified' with an empty "
        f"verified_by and no ERROR from any check")
