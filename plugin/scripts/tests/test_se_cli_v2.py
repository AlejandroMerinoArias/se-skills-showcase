"""The v2 command-line surface of se_check.py and se_trace.py."""

import json

import se_check
import se_trace

CONFIG = (
    "mode: full\n"
    "models:\n  crit_a: opus\n  crit_b: sonnet\n  crit_c: sonnet\n  architecture: opus\n"
    "research: ask\ntraceability: annotation\ntest_command: \"pytest\"\n"
)

REQ = """- id: {rid}
  text: When the trigger occurs, the system shall respond within 100 ms.
  category: functional
  criticality: B
  rationale: null
  source: null
  parent: null
  allocated_to: {alloc}
  moc: test
  verified_by: []
  status: {status}
  waiver: null
  suspect: false
  target: null
  threshold: null
  increment: I1
"""


def _project(tmp_path, reqs=(("SYS-F-001", "validated", "m"),), increments=True, items=None):
    se = tmp_path / "se"
    se.mkdir()
    (se / "se-config.yaml").write_text(CONFIG, encoding="utf-8")
    body = "".join(REQ.format(rid=r, status=s, alloc=a) for r, s, a in reqs)
    (se / "requirements.yaml").write_text(
        "# keep me\nmeta:\n  project: p\n  mode: full\n  levels: [SYS, ITEM]\nrequirements:\n" + body,
        encoding="utf-8")
    if increments:
        ids = ", ".join(r for r, _s, _a in reqs)
        (se / "increments.yaml").write_text(
            f"increments:\n- id: I1\n  goal: g\n  requirements: [{ids}]\n  status: active\n"
            f"final_validation: null\n", encoding="utf-8")
    if items is not None:
        (se / "open-items.yaml").write_text(items, encoding="utf-8")
    return se


def test_trace_runs_without_tests_and_keeps_comments(tmp_path, capsys):
    se = _project(tmp_path)
    assert se_trace.main([str(se)]) == 0
    assert "# keep me" in (se / "requirements.yaml").read_text(encoding="utf-8")
    matrix = (se / "generated" / "matrix.md").read_text(encoding="utf-8")
    assert "| ID | Inc |" in matrix and "| SYS-F-001 | I1 |" in matrix


def test_retired_requirement_is_not_reported_untested(tmp_path, capsys):
    se = _project(tmp_path, reqs=(("SYS-F-001", "retired", "null"),))
    se_trace.main([str(se)])
    assert "trace_untested_req" not in capsys.readouterr().out


def _route(se, capsys, *flags):
    code = se_check.main([str(se), "--route", *flags])
    return code, capsys.readouterr().out.splitlines()


def test_route_prints_the_active_increment(tmp_path, capsys):
    code, lines = _route(_project(tmp_path), capsys)
    assert code == 0
    assert lines[0] == "state: ready_to_build"
    assert lines[2] == "increment: I1"


def test_route_without_record_never_writes(tmp_path, capsys):
    se = _project(tmp_path)
    _route(se, capsys)
    assert not (se / "generated" / "route-log.jsonl").exists()


def test_record_three_times_without_progress_stalls(tmp_path, capsys):
    se = _project(tmp_path)
    assert _route(se, capsys, "--record")[1][0] == "state: ready_to_build"
    assert _route(se, capsys, "--record")[1][0] == "state: ready_to_build"
    assert _route(se, capsys, "--record")[1][0] == "state: stalled"
    log = (se / "generated" / "route-log.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(log) == 2  # a stalled route is not recorded as a dispatch
    assert json.loads(log[0])["increment"] == "I1"


def test_ack_stall_clears_the_stall(tmp_path, capsys):
    se = _project(tmp_path)
    for _ in range(2):
        _route(se, capsys, "--record")
    assert _route(se, capsys, "--ack-stall")[1][0] == "state: ready_to_build"


def test_record_requires_route(tmp_path, capsys):
    se = _project(tmp_path)
    try:
        se_check.main([str(se), "--record"])
    except SystemExit as exc:
        assert exc.code == 2
    else:
        raise AssertionError("argparse should have refused --record without --route")


def test_malformed_open_items_exits_2(tmp_path, capsys):
    se = _project(tmp_path, items="items: [\n")
    assert se_check.main([str(se), "--route"]) == 2
    assert se_check.main([str(se)]) == 2


def test_invalid_open_item_blocks_routing(tmp_path, capsys):
    se = _project(tmp_path, items="items:\n- id: E-01\n  kind: customer_question\n  text: t\n"
                                  "  owner: I0\n  status: open\n")
    assert _route(se, capsys)[1][0] == "state: blocked_invalid"


def test_check_reports_increment_mismatch(tmp_path, capsys):
    se = _project(tmp_path, increments=False)
    (se / "increments.yaml").write_text(
        "increments:\n- id: I1\n  goal: g\n  requirements: []\n  status: active\n", encoding="utf-8")
    assert se_check.main([str(se)]) == 1
    assert "check_increments" in capsys.readouterr().out


def test_mark_suspect_accepts_several_ids_and_keeps_comments(tmp_path, capsys):
    se = _project(tmp_path, reqs=(("SYS-F-001", "validated", "m"), ("SYS-F-002", "validated", "m")))
    assert se_check.main([str(se), "--mark-suspect", "SYS-F-001", "SYS-F-002"]) == 0
    assert "marked suspect: SYS-F-001, SYS-F-002" in capsys.readouterr().out
    text = (se / "requirements.yaml").read_text(encoding="utf-8")
    assert "# keep me" in text
    assert text.count("suspect: true") == 2


def test_mark_suspect_with_an_unknown_id_changes_nothing(tmp_path, capsys):
    se = _project(tmp_path)
    before = (se / "requirements.yaml").read_text(encoding="utf-8")
    assert se_check.main([str(se), "--mark-suspect", "SYS-F-001", "SYS-F-404"]) == 2
    assert (se / "requirements.yaml").read_text(encoding="utf-8") == before


def test_changed_lists_everything_before_a_snapshot_then_only_edits(tmp_path, capsys):
    se = _project(tmp_path, reqs=(("SYS-F-001", "validated", "m"), ("SYS-F-002", "validated", "m")))
    assert se_check.main([str(se), "--changed"]) == 0
    assert capsys.readouterr().out.split() == ["SYS-F-001", "SYS-F-002"]
    assert se_trace.main([str(se)]) in (0, 1)
    capsys.readouterr()
    path = se / "requirements.yaml"
    path.write_text(path.read_text(encoding="utf-8").replace(
        "respond within 100 ms.", "respond within 50 ms.", 1), encoding="utf-8")
    se_check.main([str(se), "--changed"])
    assert capsys.readouterr().out.split() == ["SYS-F-001"]



# --- final-review fixes ---

def test_trace_without_tests_keeps_existing_links(tmp_path, capsys):
    """Omitting --tests (to refresh the snapshot) must not erase test links."""
    se = _project(tmp_path)
    tests = tmp_path / "tests"
    tests.mkdir()
    (tests / "test_x.py").write_text("# VERIFIES: SYS-F-001\ndef test_x():\n    pass\n",
                                     encoding="utf-8")
    se_trace.main([str(se), "--tests", str(tests)])
    linked = (se / "requirements.yaml").read_text(encoding="utf-8")
    assert "test_x.py::test_x" in linked
    (se / "generated" / "req_hashes.json").unlink()
    se_trace.main([str(se)])
    assert (se / "requirements.yaml").read_text(encoding="utf-8") == linked
    assert (se / "generated" / "req_hashes.json").exists()


def test_non_utf8_requirements_is_a_clean_exit_2(tmp_path, capsys):
    """Windows PowerShell 5.1 Set-Content writes ANSI; that must be a clear
    malformed-file exit, not a traceback."""
    se = _project(tmp_path)
    path = se / "requirements.yaml"
    path.write_bytes(path.read_text(encoding="utf-8").replace(
        "# keep me", "# exploraci\u00f3n").encode("cp1252"))
    assert se_check.main([str(se)]) == 2
    assert "UTF-8" in capsys.readouterr().out
    assert se_check.main([str(se), "--route"]) == 2
    assert se_trace.main([str(se)]) == 2


def test_non_utf8_open_items_is_a_clean_exit_2(tmp_path, capsys):
    se = _project(tmp_path)
    (se / "open-items.yaml").write_bytes("items: []  # exploraci\u00f3n\n".encode("cp1252"))
    assert se_check.main([str(se), "--route"]) == 2
    assert "UTF-8" in capsys.readouterr().out


def test_waiting_for_the_customer_is_not_a_dispatch(tmp_path, capsys):
    """Routing to a customer gate hands work to the user, not to a phase agent,
    so repeated gates must never add up to a stall."""
    se = _project(tmp_path, items="items:\n- id: Q-01\n  kind: customer_question\n"
                                  "  text: which lanterns count?\n  owner: setup\n  status: open\n")
    for _ in range(3):
        assert _route(se, capsys, "--record")[1][0] == "state: awaiting_customer"
    assert not (se / "generated" / "route-log.jsonl").exists()
