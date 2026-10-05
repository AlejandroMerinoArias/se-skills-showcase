"""The v2 router rows (design spec section 8) and the stall detector (5.6)."""

import se_route
from helpers import make_data, make_requirement

FULL = {"mode": "full"}
LITE = {"mode": "lite"}


def _incs(*specs, final=None):
    return {"increments": [{"id": i, "goal": f"goal {i}", "requirements": list(r),
                            "status": st} for i, st, r in specs],
            "final_validation": final}


def _full(*reqs):
    return make_data(list(reqs), levels=["SYS", "ITEM"])


def _state(data, cfg=FULL, items=None, increments=None):
    return se_route.compute_state(data, cfg, [], items, increments)[0]


def _exp(iid="E-01", status="open", owner="I0", blocks=()):
    return {"id": iid, "kind": "experiment", "status": status, "owner": owner,
            "blocks": list(blocks), "text": "t", "answer": None if status == "open" else "a"}


def test_answered_item_outranks_customer_questions():
    items = [_exp(status="answered"),
             {"id": "Q-01", "kind": "customer_question", "status": "open", "owner": "setup"}]
    state, reason = se_route.compute_state(_full(), FULL, [], items, None)
    assert state == "items_unapplied"
    assert "E-01 (owner I0)" in reason


def test_suspect_outranks_items_unapplied():
    data = _full(make_requirement(status="validated", suspect=True))
    assert _state(data, items=[_exp(status="answered")]) == "suspects_pending"


def test_open_customer_questions_come_before_requirements_work():
    items = [{"id": "Q-01", "kind": "customer_question", "status": "open", "owner": "setup"}]
    assert _state(_full(make_requirement()), items=items) == "awaiting_customer"


def test_closed_customer_question_does_not_wait():
    items = [{"id": "Q-01", "kind": "customer_question", "status": "closed", "owner": "setup"}]
    assert _state(_full(make_requirement()), items=items) == "draft_top_level"


def test_experiment_owned_by_the_active_increment_blocks_it():
    data = _full(make_requirement(status="validated", increment="I1"))
    incs = _incs(("I0", "active", []), ("I1", "planned", ["SYS-F-001"]))
    assert _state(data, items=[_exp(owner="I0")], increments=incs) == "experiments_open"


def test_experiment_blocking_a_later_increment_does_not_block_the_active_one():
    data = _full(make_requirement(status="validated", allocated_to="m", increment="I1"),
                 make_requirement(id="SYS-F-002", status="validated", increment="I2"))
    incs = _incs(("I1", "active", ["SYS-F-001"]), ("I2", "planned", ["SYS-F-002"]))
    items = [_exp(owner="I2", blocks=["SYS-F-002"])]
    assert _state(data, items=items, increments=incs) == "ready_to_build"


def test_experiment_blocking_an_active_requirement_blocks_regardless_of_owner():
    data = _full(make_requirement(status="validated", allocated_to="m", increment="I1"))
    incs = _incs(("I1", "active", ["SYS-F-001"]))
    items = [_exp(owner="I2", blocks=["SYS-F-001"])]
    assert _state(data, items=items, increments=incs) == "experiments_open"


def test_later_increment_drafts_do_not_block_the_active_increment():
    data = _full(make_requirement(status="validated", allocated_to="m", increment="I1"),
                 make_requirement(id="SYS-F-002", status="validated", increment="I2"),
                 make_requirement(id="ITEM-D-001", parent="SYS-F-002", category="derived",
                                  rationale="r", increment="I2"))
    incs = _incs(("I1", "active", ["SYS-F-001"]), ("I2", "planned", ["SYS-F-002"]))
    assert _state(data, increments=incs) == "ready_to_build"


def test_characterization_increment_with_no_requirements_asks_to_be_closed():
    data = _full(make_requirement(status="validated", increment="I1"))
    incs = _incs(("I0", "active", []), ("I1", "planned", ["SYS-F-001"]))
    state, reason = se_route.compute_state(data, FULL, [], [_exp(status="closed")], incs)
    assert state == "increment_unverified"
    assert "close I0" in reason


def test_all_increments_done_needs_final_validation_then_completes():
    data = _full(make_requirement(status="verified", increment="I1"))
    incs = _incs(("I1", "verified", ["SYS-F-001"]))
    assert _state(data, increments=incs) == "final_validation"
    incs["final_validation"] = {"result": "mission demonstrated", "date": "2026-10-01"}
    assert _state(data, increments=incs) == "complete"


def test_a_failed_increment_is_skipped_by_the_router():
    data = _full(make_requirement(status="validated", increment="I1"),
                 make_requirement(id="SYS-F-002", status="validated", allocated_to="m", increment="I2"))
    incs = _incs(("I1", "failed", ["SYS-F-001"]), ("I2", "active", ["SYS-F-002"]))
    assert _state(data, increments=incs) == "ready_to_build"


def test_lite_mode_ignores_increments_and_finishes_without_final_validation():
    data = make_data([make_requirement(status="verified")])
    assert _state(data, cfg=LITE, increments=_incs(("I1", "active", []))) == "complete"


def test_lite_mode_experiment_blocking_a_requirement():
    data = make_data([make_requirement(status="validated")])
    assert _state(data, cfg=LITE, items=[_exp(owner="setup", blocks=["SYS-F-001"])]) == "experiments_open"


def test_malformed_blocks_does_not_crash_the_router():
    data = make_data([make_requirement(status="validated")])
    items = [dict(_exp(owner="setup"), blocks="SYS-F-001"), "not-a-mapping"]
    assert _state(data, cfg=LITE, items=items) == "ready_to_build"


# --- stall detection ---

def _dispatch(state="ready_to_build", fp="fp1", inc="I1"):
    return {"kind": "dispatch", "state": state, "fingerprint": fp, "increment": inc}


def test_two_identical_dispatches_then_the_same_again_is_stalled():
    history = [_dispatch(), _dispatch()]
    state, reason = se_route.apply_stall("ready_to_build", "r", history, "fp1", "I1", 8)
    assert state == "stalled" and "no progress" in reason


def test_a_changed_fingerprint_is_progress():
    history = [_dispatch(), _dispatch()]
    assert se_route.apply_stall("ready_to_build", "r", history, "fp2", "I1", 8)[0] == "ready_to_build"


def test_one_repeat_is_not_yet_a_stall():
    assert se_route.apply_stall("ready_to_build", "r", [_dispatch()], "fp1", "I1", 8)[0] == "ready_to_build"


def test_dispatch_budget_per_increment():
    history = [_dispatch(fp=f"fp{n}") for n in range(8)]
    state, reason = se_route.apply_stall("ready_to_build", "r", history, "new", "I1", 8)
    assert state == "stalled" and "8 of 8" in reason
    assert se_route.apply_stall("ready_to_build", "r", history, "new", "I2", 8)[0] == "ready_to_build"


def test_acknowledgement_resets_both_tests():
    history = [_dispatch(fp=f"fp{n}") for n in range(7)] + [_dispatch(fp="same"), _dispatch(fp="same"),
                                                            {"kind": "ack"}]
    assert se_route.apply_stall("ready_to_build", "r", history, "same", "I1", 8)[0] == "ready_to_build"


def test_unstallable_states_pass_through():
    history = [_dispatch(state="complete"), _dispatch(state="complete")]
    assert se_route.apply_stall("complete", "r", history, "fp1", "I1", 8)[0] == "complete"


def test_route_log_skips_garbage_lines(tmp_path):
    (tmp_path / "generated").mkdir()
    (tmp_path / "generated" / "route-log.jsonl").write_text(
        '{"kind": "dispatch"}\nnot json\n[1, 2]\n\n{"kind": "ack"}\n', encoding="utf-8")
    assert [r["kind"] for r in se_route.read_route_log(str(tmp_path))] == ["dispatch", "ack"]


def test_append_then_read_round_trips(tmp_path):
    se_route.append_route_record(str(tmp_path), _dispatch())
    assert se_route.read_route_log(str(tmp_path)) == [_dispatch()]


def test_fingerprint_changes_with_any_tracked_file(tmp_path):
    (tmp_path / "requirements.yaml").write_text("a", encoding="utf-8")
    first = se_route.fingerprint(str(tmp_path))
    (tmp_path / "open-items.yaml").write_text("items: []", encoding="utf-8")
    second = se_route.fingerprint(str(tmp_path))
    (tmp_path / "increments.yaml").write_text("increments: []", encoding="utf-8")
    assert len({first, second, se_route.fingerprint(str(tmp_path))}) == 3


# --- final-review fix C2: decomposed parents follow their children ---

def _pair(parent_status, child_status, child_alloc=True):
    return _full(
        make_requirement(status=parent_status, allocated_to=["m"], increment="I1"),
        make_requirement(id="ITEM-D-001", parent="SYS-F-001", category="derived", rationale="D-01",
                         status=child_status, allocated_to=["m"] if child_alloc else None,
                         increment="I1"))


def test_decomposed_parent_is_not_built_itself():
    incs = _incs(("I1", "active", ["SYS-F-001"]))
    assert _state(_pair("validated", "implemented"), increments=incs) == "increment_unverified"


def test_decomposed_parent_settles_when_its_children_do():
    incs = _incs(("I1", "active", ["SYS-F-001"]))
    state, reason = se_route.compute_state(_pair("validated", "verified"), FULL, [], [], incs)
    assert state == "increment_unverified" and "close I1" in reason


def test_a_full_project_with_a_parent_and_child_reaches_complete():
    """Walk the router from greenfield to complete; every step must make progress."""
    walk = []
    walk.append(se_route.compute_state(_full(), None, [])[0])
    walk.append(_state(_full()))
    walk.append(_state(_full(make_requirement())))
    walk.append(_state(_full(make_requirement(status="validated"))))
    top = make_requirement(status="validated", increment="I1")
    i0 = _incs(("I0", "active", []), ("I1", "planned", ["SYS-F-001"]))
    walk.append(_state(_full(top), items=[_exp()], increments=i0))
    walk.append(_state(_full(top), items=[_exp(status="closed")], increments=i0))
    i1 = _incs(("I0", "verified", []), ("I1", "active", ["SYS-F-001"]))
    walk.append(_state(_full(top), increments=i1))
    walk.append(_state(_pair("validated", "draft", child_alloc=False), increments=i1))
    walk.append(_state(_pair("validated", "validated"), increments=i1))
    walk.append(_state(_pair("validated", "implemented"), increments=i1))
    walk.append(_state(_pair("validated", "verified"), increments=i1))
    done = _incs(("I0", "verified", []), ("I1", "verified", ["SYS-F-001"]))
    walk.append(_state(_pair("validated", "verified"), increments=done))
    done["final_validation"] = {"result": "demonstrated"}
    walk.append(_state(_pair("validated", "verified"), increments=done))
    assert walk == ["greenfield", "no_requirements", "draft_top_level", "no_increment_plan",
                    "experiments_open", "increment_unverified", "increment_design",
                    "increment_design", "ready_to_build", "increment_unverified",
                    "increment_unverified", "final_validation", "complete"]
