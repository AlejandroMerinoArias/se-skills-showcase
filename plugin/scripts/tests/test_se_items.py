"""open-items.yaml and increments.yaml (v2 design spec sections 4 and 6.2)."""

import pytest

import se_items
import se_lib
from helpers import make_data, make_requirement


def _item(**overrides):
    item = {"id": "E-01", "kind": "experiment", "text": "What rate does the depth camera publish at?",
            "blocks": [], "owner": "I0", "status": "open", "answer": None, "evidence": None}
    item.update(overrides)
    return item


def _errors(findings):
    return [f.message for f in findings if f.level == "ERROR"]


# --- loading ---

def test_absent_items_file_is_empty(tmp_path):
    assert se_items.load_items(str(tmp_path)) == []


def test_items_file_without_items_key_is_empty(tmp_path):
    (tmp_path / "open-items.yaml").write_text("{}\n", encoding="utf-8")
    assert se_items.load_items(str(tmp_path)) == []


def test_empty_items_file_is_empty(tmp_path):
    (tmp_path / "open-items.yaml").write_text("", encoding="utf-8")
    assert se_items.load_items(str(tmp_path)) == []


def test_items_must_be_a_list(tmp_path):
    (tmp_path / "open-items.yaml").write_text("items: {a: 1}\n", encoding="utf-8")
    with pytest.raises(se_lib.SeYamlError):
        se_items.load_items(str(tmp_path))


def test_malformed_items_yaml_raises(tmp_path):
    (tmp_path / "open-items.yaml").write_text("items: [\n", encoding="utf-8")
    with pytest.raises(se_lib.SeYamlError):
        se_items.load_items(str(tmp_path))


# --- validate_items ---

def test_a_well_formed_item_is_clean(tmp_path):
    assert se_items.validate_items([_item()], set(), str(tmp_path)) == []


def test_prefix_must_match_kind(tmp_path):
    msgs = _errors(se_items.validate_items([_item(id="Q-01")], set(), str(tmp_path)))
    assert any("requires kind 'customer_question'" in m for m in msgs)


def test_duplicate_item_ids(tmp_path):
    msgs = _errors(se_items.validate_items([_item(), _item()], set(), str(tmp_path)))
    assert any("duplicate" in m for m in msgs)


def test_bad_id_status_owner_and_text(tmp_path):
    msgs = _errors(se_items.validate_items(
        [_item(id="X-1", status="done", owner="increment-0", text="")], set(), str(tmp_path)))
    assert any("must look like" in m for m in msgs)
    assert any("'status'" in m for m in msgs)
    assert any("'owner'" in m for m in msgs)
    assert any("'text'" in m for m in msgs)


def test_setup_is_a_valid_owner(tmp_path):
    assert se_items.validate_items([_item(owner="setup")], set(), str(tmp_path)) == []


def test_blocks_must_name_existing_requirements(tmp_path):
    msgs = _errors(se_items.validate_items([_item(blocks=["SYS-F-009"])], {"SYS-F-001"}, str(tmp_path)))
    assert any("unknown requirement 'SYS-F-009'" in m for m in msgs)


def test_blocks_must_be_a_list(tmp_path):
    msgs = _errors(se_items.validate_items([_item(blocks="SYS-F-001")], {"SYS-F-001"}, str(tmp_path)))
    assert any("'blocks' must be a list" in m for m in msgs)


@pytest.mark.parametrize("status", ["answered", "applied", "closed", "accepted_risk"])
def test_resolved_statuses_need_an_answer(tmp_path, status):
    msgs = _errors(se_items.validate_items([_item(status=status)], set(), str(tmp_path)))
    assert any("requires a one-line 'answer'" in m for m in msgs)


def test_evidence_must_exist_inside_evidence_dir(tmp_path):
    (tmp_path / "evidence").mkdir()
    (tmp_path / "evidence" / "E-01.md").write_text("30 Hz", encoding="utf-8")
    ok = _item(status="answered", answer="30 Hz", evidence="evidence/E-01.md")
    assert se_items.validate_items([ok], set(), str(tmp_path)) == []
    missing = _item(status="answered", answer="30 Hz", evidence="evidence/E-99.md")
    assert any("does not exist" in m for m in _errors(se_items.validate_items([missing], set(), str(tmp_path))))
    escape = _item(status="answered", answer="30 Hz", evidence="../x.md")
    assert any("resolves outside" in m for m in _errors(se_items.validate_items([escape], set(), str(tmp_path))))


def test_non_mapping_item(tmp_path):
    assert _errors(se_items.validate_items(["E-01"], set(), str(tmp_path)))


# --- open values ---

def test_validated_requirement_may_hold_an_open_value():
    data = make_data([make_requirement(status="validated", open_items=["E-01"])])
    assert se_items.check_open_values(data, [_item()]) == []


@pytest.mark.parametrize("status", ["implemented", "verified"])
def test_open_value_blocks_implementation(status):
    data = make_data([make_requirement(status=status, open_items=["E-01"])])
    msgs = _errors(se_items.check_open_values(data, [_item(status="answered", answer="x")]))
    assert any("not closed or accepted_risk" in m for m in msgs)


def test_closed_item_unblocks():
    data = make_data([make_requirement(status="implemented", open_items=["E-01"])])
    assert se_items.check_open_values(data, [_item(status="closed", answer="30 Hz")]) == []


def test_open_items_reference_must_exist():
    data = make_data([make_requirement(open_items=["E-07"])])
    assert any("unknown item 'E-07'" in m for m in _errors(se_items.check_open_values(data, [])))


# --- question budget ---

def _q(n, status="open"):
    return _item(id=f"Q-{n:02d}", kind="customer_question", owner="setup", status=status,
                 answer=None if status == "open" else "yes")


def test_question_caps_warn_not_block():
    items = [_q(n) for n in range(1, 7)]
    findings = se_items.check_question_budget(items, {})
    assert [f.level for f in findings] == ["WARNING"]
    assert "customer_questions_per_gate" in findings[0].message


def test_total_question_cap():
    items = [_q(n, status="closed") for n in range(1, 17)]
    findings = se_items.check_question_budget(items, {})
    assert len(findings) == 1 and "customer_questions_total" in findings[0].message


def test_question_caps_follow_config():
    items = [_q(1), _q(2)]
    assert se_items.check_question_budget(items, {"budgets": {"customer_questions_per_gate": 1}})


# --- increments ---

def _incs(*specs, final=None):
    return {"increments": [{"id": i, "goal": f"goal {i}", "requirements": list(r),
                            "status": st, "exit_evidence": None, "failure_cause": None}
                           for i, st, r in specs],
            "final_validation": final}


def _full(*reqs):
    return make_data(list(reqs), levels=["SYS", "ITEM"])


def test_absent_increments_file_is_none(tmp_path):
    assert se_items.load_increments(str(tmp_path)) is None


def test_empty_increments_file_means_no_plan_yet(tmp_path):
    (tmp_path / "increments.yaml").write_text(chr(10), encoding="utf-8")
    assert se_items.load_increments(str(tmp_path)) is None


def test_increments_file_needs_a_list(tmp_path):
    (tmp_path / "increments.yaml").write_text("final_validation: null\n", encoding="utf-8")
    with pytest.raises(se_lib.SeYamlError):
        se_items.load_increments(str(tmp_path))


def test_active_increment_is_the_first_not_done():
    incs = _incs(("I0", "verified", []), ("I1", "failed", []), ("I2", "planned", []))
    assert se_items.active_increment(incs)["id"] == "I2"
    assert se_items.active_increment(_incs(("I0", "verified", []))) is None
    assert se_items.active_increment(None) is None


def test_consistent_increments_are_clean():
    data = _full(make_requirement(increment="I1"),
                 make_requirement(id="ITEM-D-001", parent="SYS-F-001", category="derived",
                                  rationale="r", increment="I1"))
    assert se_items.validate_increments(_incs(("I0", "active", []), ("I1", "planned", ["SYS-F-001"])), data) == []


def test_live_requirement_without_increment():
    data = _full(make_requirement())
    msgs = _errors(se_items.validate_increments(_incs(("I1", "active", ["SYS-F-001"])), data))
    assert any("needs an 'increment'" in m for m in msgs)


def test_retired_requirement_needs_no_increment():
    data = _full(make_requirement(status="retired"))
    assert se_items.validate_increments(_incs(("I1", "active", [])), data) == []


def test_requirement_field_must_match_assignment():
    data = _full(make_requirement(increment="I2"))
    incs = _incs(("I1", "active", ["SYS-F-001"]), ("I2", "planned", []))
    msgs = _errors(se_items.validate_increments(incs, data))
    assert any("assigns it to I1" in m for m in msgs)


def test_assignment_rules():
    data = _full(make_requirement(increment="I1"),
                 make_requirement(id="ITEM-D-001", parent="SYS-F-001", category="derived",
                                  rationale="r", increment="I1"))
    incs = _incs(("I1", "active", ["SYS-F-001", "ITEM-D-001", "SYS-F-404"]),
                 ("I2", "planned", ["SYS-F-001"]))
    msgs = _errors(se_items.validate_increments(incs, data))
    assert any("not top-level" in m for m in msgs)
    assert any("unknown requirement 'SYS-F-404'" in m for m in msgs)
    assert any("already assigned to I1" in m for m in msgs)


def test_failed_increment_needs_a_cause_and_ids_are_checked():
    incs = {"increments": [{"id": "I1", "goal": "g", "requirements": [], "status": "failed"},
                           {"id": "I1", "goal": "", "requirements": [], "status": "doing"},
                           {"id": "one", "goal": "g", "requirements": [], "status": "planned"}],
            "final_validation": "done"}
    msgs = _errors(se_items.validate_increments(incs, _full()))
    assert any("requires a 'failure_cause'" in m for m in msgs)
    assert any("duplicate increment id" in m for m in msgs)
    assert any("'goal'" in m for m in msgs)
    assert any("'status'" in m for m in msgs)
    assert any("must look like I0" in m for m in msgs)
    assert any("'final_validation'" in m for m in msgs)
