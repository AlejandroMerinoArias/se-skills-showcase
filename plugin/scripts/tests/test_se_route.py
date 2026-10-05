"""compute_state: where is this project? (spec section 2.3, as a predicate)

The routing table used to live only in se:develop's prose, which made it
testable only by pressure test at n=1. These are the same rows, as asserts."""

import hashlib
import json

import pytest

import se_check
import se_lib
import se_route


def _req(rid, **overrides):
    req = {
        "id": rid, "text": f"text for {rid}", "category": "functional",
        "criticality": "B", "rationale": None, "source": None, "parent": None,
        "allocated_to": None, "moc": "test", "verified_by": [], "status": "draft",
        "waiver": None, "suspect": False, "target": None, "threshold": None,
        "history": [],
    }
    req.update(overrides)
    return req


def _data(*reqs, levels=("SYS",), mode="lite"):
    return {"meta": {"project": "p", "mode": mode, "levels": list(levels)},
            "requirements": list(reqs)}


def _cfg(**overrides):
    cfg = {
        "mode": "lite",
        "models": {"crit_a": "opus", "crit_b": "sonnet",
                   "crit_c": "sonnet", "architecture": "opus"},
        "research": "ask",
        "traceability": "annotation",
        "test_command": "python -m pytest",
    }
    cfg.update(overrides)
    return cfg


def _state(data, cfg=None, findings=None, items=None, increments=None):
    return se_check.compute_state(data, cfg if cfg is not None else _cfg(),
                                   findings or [], items, increments)[0]


def _incs(*specs, final=None):
    """specs: (id, status, [top-level req ids])."""
    return {"increments": [{"id": i, "goal": f"goal {i}", "requirements": list(r),
                            "status": st, "exit_evidence": None, "failure_cause": None}
                           for i, st, r in specs],
            "final_validation": final}


def test_absent_config_is_greenfield():
    state, reason = se_check.compute_state(_data(_req("SYS-F-001")), None, [])
    assert state == "greenfield"
    assert "se-config.yaml" in reason


def test_any_error_finding_blocks_before_any_other_state():
    findings = [se_lib.Finding("ERROR", "validate_schema", "SYS-F-001", "boom")]
    assert _state(_data(_req("SYS-F-001")), findings=findings) == "blocked_invalid"


def test_warnings_alone_do_not_block():
    findings = [se_lib.Finding("WARNING", "check_allocation", "SYS-F-001", "meh")]
    assert _state(_data(_req("SYS-F-001")), findings=findings) == "draft_top_level"


def test_suspect_outranks_the_phase_states():
    data = _data(_req("SYS-F-001", status="implemented", suspect=True))
    assert _state(data) == "suspects_pending"


def test_retired_suspect_does_not_route_to_change_management():
    """A retired requirement is out of the tree; its stale suspect flag is not
    work waiting to be done."""
    data = _data(_req("SYS-F-001", status="retired", suspect=True),
                 _req("SYS-F-002", status="verified"))
    assert _state(data) == "complete"


def test_empty_requirements_is_its_own_state():
    """se:tailoring seeds an empty requirements.yaml, so 'the file exists' can
    never mean 'requirements exist'."""
    assert _state(_data()) == "no_requirements"


def test_greenfield_outranks_blocked_invalid():
    """Pins the greenfield/blocked_invalid pair: cfg is None is checked before
    findings are ever inspected. If the two branches were swapped, a project
    with no se-config.yaml but an ERROR finding in hand would report
    blocked_invalid instead, and this test would fail."""
    findings = [se_lib.Finding("ERROR", "validate_schema", "SYS-F-001", "boom")]
    state, reason = se_check.compute_state(_data(_req("SYS-F-001")), None, findings)
    assert state == "greenfield"


def test_blocked_invalid_outranks_suspects_pending():
    """Pins the blocked_invalid/suspects_pending pair: an ERROR finding and a
    suspect requirement both present at once. If the two branches were
    swapped, this would report suspects_pending instead, and this test would
    fail."""
    findings = [se_lib.Finding("ERROR", "validate_schema", "SYS-F-001", "boom")]
    data = _data(_req("SYS-F-001", suspect=True))
    assert _state(data, findings=findings) == "blocked_invalid"


def test_draft_top_level_requirements_route_to_validation():
    assert _state(_data(_req("SYS-F-001"))) == "draft_top_level"


def test_draft_children_below_the_top_level_are_a_different_state():
    """The predicate Plan B1's integration run proved necessary: this project
    and the one above are both 'has drafts', and they need different phases."""
    data = _data(_req("SYS-F-001", status="validated", allocated_to="mod", increment="I1"),
                 _req("ITEM-D-001", parent="SYS-F-001", status="draft",
                      category="derived", rationale="a decision", increment="I1"),
                 levels=("SYS", "ITEM"), mode="full")
    incs = _incs(("I1", "active", ["SYS-F-001"]))
    assert _state(data, _cfg(mode="full"), increments=incs) == "increment_design"


def test_a_draft_top_level_requirement_outranks_draft_children():
    data = _data(_req("SYS-F-001"),
                 _req("ITEM-D-001", parent="SYS-F-001", status="draft",
                      category="derived", rationale="a decision"),
                 levels=("SYS", "ITEM"), mode="full")
    assert _state(data, _cfg(mode="full")) == "draft_top_level"


def test_draft_top_level_outranks_validated_unallocated():
    """Pins the draft_top_level/validated_unallocated pair: a top-level draft
    requirement and a separate validated-but-unallocated requirement both
    present, in full mode, at once. If the draft branches and the
    validated_unallocated branch were swapped in code order, this would
    report validated_unallocated instead, and this test would fail."""
    data = _data(_req("SYS-F-001", status="draft"),
                 _req("SYS-F-002", status="validated"),
                 levels=("SYS", "ITEM"), mode="full")
    assert _state(data, _cfg(mode="full")) == "draft_top_level"


def test_full_mode_without_increments_routes_to_increment_planning():
    data = _data(_req("SYS-F-001", status="validated"),
                 levels=("SYS", "ITEM"), mode="full")
    assert _state(data, _cfg(mode="full")) == "no_increment_plan"


def test_full_mode_validated_but_unallocated_in_the_active_increment_is_design():
    data = _data(_req("SYS-F-001", status="validated", increment="I1"),
                 levels=("SYS", "ITEM"), mode="full")
    incs = _incs(("I1", "active", ["SYS-F-001"]))
    assert _state(data, _cfg(mode="full"), increments=incs) == "increment_design"


def test_lite_mode_never_reports_unallocated():
    """Lite has no architecture phase, so unallocated is its normal shape.
    se_check still WARNs about it; the router does not send anywhere."""
    assert _state(_data(_req("SYS-F-001", status="validated"))) == "ready_to_build"


def test_all_validated_and_allocated_is_ready_to_build():
    data = _data(_req("SYS-F-001", status="validated", allocated_to="mod", increment="I1"),
                 levels=("SYS", "ITEM"), mode="full")
    incs = _incs(("I1", "active", ["SYS-F-001"]))
    assert _state(data, _cfg(mode="full"), increments=incs) == "ready_to_build"


def test_a_mix_of_validated_and_implemented_is_still_implementing():
    data = _data(_req("SYS-F-001", status="implemented"),
                 _req("SYS-F-002", status="validated"))
    assert _state(data) == "implementing"


def test_everything_implemented_and_nothing_verified_is_increment_unverified():
    data = _data(_req("SYS-F-001", status="implemented"),
                 _req("SYS-F-002", status="implemented"))
    assert _state(data) == "increment_unverified"


def test_all_verified_is_complete():
    data = _data(_req("SYS-F-001", status="verified", verified_by=["t.py::test_a"]))
    assert _state(data) == "complete"


def test_a_waived_requirement_counts_as_settled():
    """Spec section 7: the exit gate is 100% verified OR explicit user-approved
    waivers. A waiver that did not close the gate would be no waiver at all."""
    data = _data(_req("SYS-F-001", status="verified", verified_by=["t.py::test_a"]),
                 _req("SYS-F-002", status="implemented",
                      waiver="user accepted 2026-08-01: hardware unavailable"))
    assert _state(data) == "complete"


def test_an_empty_string_waiver_does_not_settle_anything():
    data = _data(_req("SYS-F-001", status="implemented", waiver="   "))
    assert _state(data) == "increment_unverified"


def test_retired_requirements_are_ignored_by_every_phase_state():
    data = _data(_req("SYS-F-001", status="retired"),
                 _req("SYS-F-002", status="draft"))
    assert _state(data) == "draft_top_level"


def test_every_returned_state_is_a_declared_one():
    """ROUTE_STATES is the contract se:develop's table is written against; a
    state the table has no row for routes an agent nowhere."""
    cases = [
        (_data(_req("SYS-F-001")), _cfg(), []),
        (_data(), _cfg(), []),
        (_data(_req("SYS-F-001")), None, []),
        (_data(_req("SYS-F-001", status="verified")), _cfg(), []),
    ]
    for data, cfg, findings in cases:
        state, reason = se_check.compute_state(data, cfg, findings)
        assert state in se_check.ROUTE_STATES
        assert reason.strip()


def test_every_declared_state_is_reachable():
    """The converse control: a name in ROUTE_STATES that nothing can produce is
    a routing row nobody will ever land on. 'stalled' comes from apply_stall."""
    produced = set()
    full = _cfg(mode="full")
    lv = ("SYS", "ITEM")
    produced.add(se_check.compute_state(_data(_req("SYS-F-001")), None, [])[0])
    produced.add(_state(_data(_req("SYS-F-001")),
                        findings=[se_lib.Finding("ERROR", "validate_schema", None, "x")]))
    produced.add(se_route.apply_stall("ready_to_build", "r", [], "fp", "I1", 0)[0])
    produced.add(_state(_data(_req("SYS-F-001", suspect=True))))
    produced.add(_state(_data(), items=[{"id": "E-01", "kind": "experiment",
                                         "status": "answered", "owner": "I0"}]))
    produced.add(_state(_data(), items=[{"id": "Q-01", "kind": "customer_question",
                                         "status": "open", "owner": "setup"}]))
    produced.add(_state(_data()))
    produced.add(_state(_data(_req("SYS-F-001"))))
    produced.add(_state(_data(_req("SYS-F-001", status="validated"), levels=lv), full))
    produced.add(_state(_data(_req("SYS-F-001", status="validated", increment="I1"), levels=lv), full,
                        items=[{"id": "E-01", "kind": "experiment", "status": "open",
                                "owner": "I0", "blocks": ["SYS-F-001"]}],
                        increments=_incs(("I1", "active", ["SYS-F-001"]))))
    produced.add(_state(_data(_req("SYS-F-001", status="validated", increment="I1"), levels=lv), full,
                        increments=_incs(("I1", "active", ["SYS-F-001"]))))
    produced.add(_state(_data(_req("SYS-F-001", status="validated"))))
    produced.add(_state(_data(_req("SYS-F-001", status="implemented"),
                              _req("SYS-F-002", status="validated"))))
    produced.add(_state(_data(_req("SYS-F-001", status="implemented"))))
    produced.add(_state(_data(_req("SYS-F-001", status="verified", increment="I1"), levels=lv), full,
                        increments=_incs(("I1", "verified", ["SYS-F-001"]))))
    produced.add(_state(_data(_req("SYS-F-001", status="verified"))))
    assert produced == set(se_check.ROUTE_STATES)


# --- the --route CLI contract ---

REQS_HEADER = "meta:\n  project: p\n  mode: {mode}\n  levels: [{levels}]\n"

CONFIG_TEXT = (
    "mode: {mode}\n"
    "models:\n  crit_a: opus\n  crit_b: sonnet\n  crit_c: sonnet\n"
    "  architecture: opus\n"
    "research: ask\ntraceability: annotation\n"
    'test_command: "python -m pytest"\n'
)


def _project(tmp_path, reqs_text=None, config_text=CONFIG_TEXT.format(mode="lite"),
             mode="lite", levels="SYS"):
    se_dir = tmp_path / "se"
    se_dir.mkdir()
    if reqs_text is not None:
        (se_dir / "requirements.yaml").write_text(
            REQS_HEADER.format(mode=mode, levels=levels) + reqs_text,
            encoding="utf-8")
    if config_text is not None:
        (se_dir / "se-config.yaml").write_text(config_text, encoding="utf-8")
    return se_dir


def _run(se_dir, capsys):
    code = se_check.main([str(se_dir), "--route"])
    return code, capsys.readouterr().out


def test_route_prints_state_on_the_first_line(tmp_path, capsys):
    se_dir = _project(tmp_path, "requirements: []\n")
    code, out = _run(se_dir, capsys)
    assert code == 0
    assert out.splitlines()[0] == "state: no_requirements"


def test_route_reports_greenfield_when_nothing_exists_at_all(tmp_path, capsys):
    se_dir = tmp_path / "se"
    se_dir.mkdir()
    code, out = _run(se_dir, capsys)
    assert code == 0
    assert out.splitlines()[0] == "state: greenfield"


def test_route_prints_mode_and_reason(tmp_path, capsys):
    se_dir = _project(tmp_path, "requirements: []\n")
    _code, out = _run(se_dir, capsys)
    lines = out.splitlines()
    assert lines[1] == "mode: lite"
    assert lines[2] == "increment: -"
    assert lines[3].startswith("reason: ")


def test_route_exits_0_even_when_the_project_is_invalid(tmp_path, capsys):
    """The one documented exception to the exit-code contract. 'There are
    errors' is carried by the state name, not by the exit code: a router that
    exits non-zero makes every caller's shell chain misfire on the exact
    state the caller most needs to read."""
    se_dir = _project(
        tmp_path,
        "requirements:\n  - id: nope\n    text: x\n    category: functional\n"
        "    criticality: B\n    rationale: null\n    source: null\n"
        "    parent: null\n    allocated_to: null\n    moc: test\n"
        "    verified_by: []\n    status: draft\n    waiver: null\n"
        "    suspect: false\n    target: null\n    threshold: null\n"
        "    history: []\n")
    code, out = _run(se_dir, capsys)
    assert code == 0
    assert out.splitlines()[0] == "state: blocked_invalid"


def test_route_exits_2_when_config_exists_but_requirements_do_not(tmp_path, capsys):
    """se:tailoring writes both files. Config alone is a half-written project,
    not a greenfield one, and routing it to tailoring would hide the damage."""
    se_dir = _project(tmp_path, reqs_text=None)
    code, out = _run(se_dir, capsys)
    assert code == 2
    assert "requirements" in out


def test_route_exits_2_on_malformed_yaml(tmp_path, capsys):
    se_dir = _project(tmp_path, "requirements: [unclosed\n")
    code, _out = _run(se_dir, capsys)
    assert code == 2


def test_route_exits_2_on_malformed_config_yaml(tmp_path, capsys):
    """The symmetric case to the malformed-requirements test above: a broken
    se-config.yaml must not be swallowed into a state either."""
    se_dir = _project(tmp_path, "requirements: []\n", config_text="mode: [unclosed\n")
    code, _out = _run(se_dir, capsys)
    assert code == 2


def test_route_never_writes_anything(tmp_path, capsys):
    """--route is a query. The suspect cascade is the one check that writes,
    and it must not run here: routing a project must never change it.

    The seeded req_hashes.json entry for SYS-F-001 deliberately does NOT
    match its current text, and SYS-D-002 is a real child of it. Together
    those are what make a real check_suspect_cascade run mark SYS-D-002
    suspect and set changed=True, i.e. what would produce a write if a
    future edit ever wired the cascade into _route. Without that mismatch,
    this test could not fail no matter what _route did, since the fixture
    would never give the cascade anything to act on -- do not remove it as
    setup noise."""
    reqs = (
        "requirements:\n"
        "  - id: SYS-F-001\n    text: the system shall do a thing\n"
        "    category: functional\n    criticality: B\n    rationale: null\n"
        "    source: null\n    parent: null\n    allocated_to: null\n"
        "    moc: test\n    verified_by: []\n    status: draft\n    waiver: null\n"
        "    suspect: false\n    target: null\n    threshold: null\n"
        "    history: []\n"
        "  - id: SYS-D-002\n    text: a derived child of SYS-F-001\n"
        "    category: derived\n    criticality: B\n    rationale: a decision\n"
        "    source: null\n    parent: SYS-F-001\n    allocated_to: null\n"
        "    moc: test\n    verified_by: []\n    status: draft\n    waiver: null\n"
        "    suspect: false\n    target: null\n    threshold: null\n"
        "    history: []\n")
    se_dir = _project(tmp_path, reqs)
    generated_dir = se_dir / "generated"
    generated_dir.mkdir()
    stale_hash = hashlib.sha256(b"stale text from a prior se_trace snapshot").hexdigest()
    (generated_dir / "req_hashes.json").write_text(
        json.dumps({"SYS-F-001": stale_hash}), encoding="utf-8")

    before = (se_dir / "requirements.yaml").read_bytes()
    _run(se_dir, capsys)
    after = (se_dir / "requirements.yaml").read_bytes()
    assert after == before
    assert "suspect: false" in after.decode("utf-8")


def test_route_and_mark_suspect_together_are_rejected(tmp_path, capsys):
    """A query flag and a write flag in one invocation is a caller error, and
    silently honouring one of them is how a router acquires a side effect."""
    se_dir = _project(tmp_path, "requirements: []\n")
    with pytest.raises(SystemExit):
        se_check.main([str(se_dir), "--route", "--mark-suspect", "SYS-F-001"])
