"""v2 changes to se_lib: round-trip YAML, the relaxed and extended schema,
and the budgets / size-limits config sections."""

import se_lib
from helpers import make_data, make_requirement

COMMENTED = """# Customer's statement, verbatim: keep this comment.
meta:
  project: p
  levels:
  - SYS
requirements:
- id: SYS-F-001   # inline note
  text: When the trigger occurs, the system shall respond within 100 ms.
  category: functional
  criticality: B
  rationale: null
  source: null
  parent: null
  allocated_to: null
  moc: test
  verified_by: []
  status: draft
  waiver: null
  suspect: false
  target: null
  threshold: null
"""


def test_comments_survive_a_load_and_dump(tmp_path):
    path = tmp_path / "requirements.yaml"
    path.write_text(COMMENTED, encoding="utf-8")
    data = se_lib.load_requirements_yaml(str(path))
    data["requirements"][0]["suspect"] = True
    se_lib.atomic_write_yaml(str(path), data)
    out = path.read_text(encoding="utf-8")
    assert "# Customer's statement, verbatim: keep this comment." in out
    assert "# inline note" in out
    assert "suspect: true" in out


def test_crlf_input_round_trips_with_comments_and_accents(tmp_path):
    """Files edited on Windows arrive with CRLF; the customer writes Spanish."""
    path = tmp_path / "requirements.yaml"
    source = COMMENTED.replace("keep this comment.", "keep this comment: cañón, exploración.")
    path.write_bytes(source.replace(chr(10), chr(13) + chr(10)).encode("utf-8"))
    data = se_lib.load_requirements_yaml(str(path))
    se_lib.atomic_write_yaml(str(path), data)
    out = path.read_bytes().decode("utf-8")
    assert "cañón, exploración." in out
    assert chr(13) not in out
    assert se_lib.load_requirements_yaml(str(path))["requirements"][0]["id"] == "SYS-F-001"


def test_a_shared_object_is_never_written_as_an_anchor():
    """v1 GAP 126: one date object reused across entries made PyYAML emit
    &id001 anchors, and a later write was refused."""
    shared = {"date": "2026-09-27", "change": "created"}
    data = make_data([make_requirement(history=[shared]),
                      make_requirement(id="SYS-F-002", history=[shared])])
    out = se_lib.dump_requirements_yaml(data)
    assert "&id" not in out and "*id" not in out


def test_long_text_is_not_wrapped():
    text = "When the trigger occurs, " + "the system shall respond " * 10 + "now."
    out = se_lib.dump_requirements_yaml(make_data([make_requirement(text=text)]))
    assert text in out


def test_history_is_no_longer_required():
    req = make_requirement()
    del req["history"]
    assert se_lib.validate_schema(make_data([req])) == []


def test_increment_and_open_items_are_accepted():
    req = make_requirement(increment="I2", open_items=["E-02", "Q-01"])
    assert se_lib.validate_schema(make_data([req])) == []


def test_a_malformed_increment_is_an_error():
    findings = se_lib.validate_schema(make_data([make_requirement(increment="2")]))
    assert any("'increment'" in f.message and f.level == "ERROR" for f in findings)


def test_malformed_open_items_are_an_error():
    for bad in ("E-02", ["E2"], [3]):
        findings = se_lib.validate_schema(make_data([make_requirement(open_items=bad)]))
        assert any("'open_items'" in f.message for f in findings), bad


def _cfg(**extra):
    cfg = {"mode": "full",
           "models": {"crit_a": "opus", "crit_b": "sonnet", "crit_c": "sonnet",
                      "architecture": "opus"},
           "research": "ask", "traceability": "annotation", "test_command": "pytest"}
    cfg.update(extra)
    return cfg


def test_v2_optional_config_keys_are_not_unknown():
    cfg = _cfg(sim_command="ros2 launch sim.launch.py",
               budgets={"review_rounds_per_phase": 3},
               size_limits={"conops_kb": 20})
    assert se_lib.validate_config(cfg) == []


def test_bad_budget_values_are_errors():
    for bad in (0, -1, "2", True, 1.5):
        findings = se_lib.validate_config(_cfg(budgets={"review_rounds_per_phase": bad}))
        assert any(f.level == "ERROR" for f in findings), bad


def test_unknown_budget_key_is_a_warning():
    findings = se_lib.validate_config(_cfg(budgets={"review_round": 2}))
    assert [f.level for f in findings] == ["WARNING"]


def test_empty_sim_command_is_an_error():
    assert any(f.level == "ERROR" for f in se_lib.validate_config(_cfg(sim_command=" ")))


def test_effective_budgets_overlay_only_valid_values():
    b = se_lib.effective_budgets(_cfg(budgets={"review_rounds_per_phase": 3,
                                               "customer_questions_total": "x"}))
    assert b["review_rounds_per_phase"] == 3
    assert b["customer_questions_total"] == se_lib.DEFAULT_BUDGETS["customer_questions_total"]
    assert se_lib.effective_budgets(None) == se_lib.DEFAULT_BUDGETS


def test_effective_size_limits_default():
    assert se_lib.effective_size_limits({}) == se_lib.DEFAULT_SIZE_LIMITS
