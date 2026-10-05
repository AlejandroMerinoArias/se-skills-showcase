"""Regression tests for the final-review robustness fixes.

Two waves live here:

- Plan A's final review: defensive guards against requirements *missing*
  'id'/'text', and se_trace's schema-validation gate before scanning/writing
  (see .superpowers/sdd/final-review-fixes.md).
- Plan B1's final review (F1): the *wrong-type* half of the same defect class.
  A schema field of the wrong type must produce a finding and an exit code,
  never a traceback — the exit-code contract (0 clean / 1 ERROR / 2 malformed)
  has no traceback in it (README.md, spec section 9).
"""

import hashlib
import json
import os

import pytest
import yaml

import se_check
import se_lib
import se_trace
from helpers import make_requirement, make_data


def _write_requirements(se_dir, data):
    os.makedirs(se_dir, exist_ok=True)
    with open(os.path.join(se_dir, "requirements.yaml"), "w", encoding="utf-8") as f:
        yaml.safe_dump(data, f, sort_keys=False)


# --- direct unit coverage for the defensive by_id / known_ids builds ---

def test_build_verified_by_skips_id_less_requirement():
    data = make_data([make_requirement(id="SYS-F-001"), {"text": "no id here"}])
    test_defs = [se_trace.TestDef(file="t.py", name="test_one", line=2, req_ids=["SYS-F-001"])]
    verified_by_map, unknown_refs = se_trace.build_verified_by(data, test_defs)
    assert verified_by_map == {"SYS-F-001": ["t.py::test_one"]}
    assert unknown_refs == []


def test_compute_req_hashes_skips_id_less_and_text_less_requirements():
    data = make_data([
        make_requirement(id="SYS-F-001", text="Fine."),
        {"id": "SYS-F-002"},  # missing text
        {"text": "orphaned"},  # missing id
    ])
    hashes = se_trace.compute_req_hashes(data)
    assert set(hashes) == {"SYS-F-001"}


def test_check_suspect_cascade_skips_id_less_requirement(tmp_path):
    data = make_data([make_requirement(id="SYS-F-001", text="text"), {"text": "no id"}])
    findings, updated, changed = se_check.check_suspect_cascade(data, str(tmp_path))
    assert findings == []
    assert changed is False


def test_mark_suspect_skips_id_less_requirement_and_still_finds_target():
    data = make_data([make_requirement(id="SYS-F-001", parent=None), {"text": "no id"}])
    updated, subtree = se_check.mark_suspect(data, "SYS-F-001")
    assert subtree == ["SYS-F-001"]


# --- se_trace.main schema gate ---

def test_se_trace_main_rejects_schema_invalid_requirements_and_writes_nothing(tmp_path):
    se_dir = tmp_path / "se"
    tests_dir = tmp_path / "tests"
    os.makedirs(se_dir)
    os.makedirs(tests_dir)

    good = make_requirement(id="SYS-F-001", text="Valid requirement.")
    bad = make_requirement(text="Missing id field.")
    del bad["id"]
    data = make_data([good, bad])
    _write_requirements(se_dir, data)

    req_path = se_dir / "requirements.yaml"
    original_yaml = req_path.read_text(encoding="utf-8")

    (tests_dir / "test_thing.py").write_text(
        "# VERIFIES: SYS-F-001\ndef test_trigger_response():\n    assert True\n"
    )

    exit_code, captured = None, None
    import io
    import contextlib
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        exit_code = se_trace.main([str(se_dir), "--tests", str(tests_dir)])
    captured = buf.getvalue()

    assert exit_code == 1
    assert "[ERROR]" in captured
    assert not (se_dir / "generated").exists()
    assert req_path.read_text(encoding="utf-8") == original_yaml


# --- se_check.main stays clean (no traceback) on schema-invalid data ---

def test_se_check_main_returns_1_cleanly_with_existing_hash_snapshot(tmp_path):
    se_dir = tmp_path / "se"
    generated_dir = se_dir / "generated"
    os.makedirs(generated_dir)
    (generated_dir / "req_hashes.json").write_text("{}", encoding="utf-8")

    good = make_requirement(id="SYS-F-001", text="Valid requirement.")
    bad = make_requirement(text="Missing id field.")
    del bad["id"]
    data = make_data([good, bad])
    _write_requirements(se_dir, data)

    exit_code = se_check.main([str(se_dir)])
    assert exit_code == 1


# --- se_check.py --mark-suspect UNKNOWN-ID exits 2 ---

def test_se_check_main_mark_suspect_unknown_id_returns_2(tmp_path):
    data = make_data([make_requirement(id="SYS-F-001", parent=None)])
    _write_requirements(tmp_path, data)

    exit_code = se_check.main([str(tmp_path), "--mark-suspect", "SYS-F-999"])
    assert exit_code == 2


# =====================================================================
# F1 - wrong-typed schema fields produce findings, never tracebacks
# =====================================================================

# One entry per malformed shape the Plan B1 final review fuzzed. The second
# requirement in each pair carries the defect; the first is well-formed, so a
# crash cannot be excused as "the file had nothing usable in it".
WRONG_TYPED_SHAPES = {
    "parent-is-a-list": dict(id="SYS-F-002", parent=["SYS-F-001"]),
    "parent-is-a-dict": dict(id="SYS-F-002", parent={"ref": "SYS-F-001"}),
    "id-is-a-list": dict(id=["SYS-F-002"]),
    "id-is-an-int": dict(id=123),
    "text-is-a-list": dict(id="SYS-F-002", text=["clause one", "clause two"]),
    "verified_by-holds-an-int": dict(id="SYS-F-002", moc="analysis",
                                     status="verified", verified_by=[7]),
}


def _data_with(shape_key):
    return make_data([make_requirement(),
                      make_requirement(**WRONG_TYPED_SHAPES[shape_key])])


@pytest.mark.parametrize("shape", sorted(WRONG_TYPED_SHAPES))
def test_validate_schema_reports_every_wrong_typed_field(shape):
    """Layer 1: the wrong type is *named* as a finding, not merely survived."""
    findings = se_lib.validate_schema(_data_with(shape))
    assert any(f.level == "ERROR" for f in findings), \
        f"{shape} produced no ERROR finding: {[f.format() for f in findings]}"


@pytest.mark.parametrize("shape", sorted(WRONG_TYPED_SHAPES))
def test_se_check_main_returns_1_without_traceback_on_wrong_typed_field(shape, tmp_path, capsys):
    """The exit-code contract: 1 plus a printed finding, never a traceback."""
    _write_requirements(tmp_path, _data_with(shape))
    exit_code = se_check.main([str(tmp_path)])
    out = capsys.readouterr().out
    assert exit_code == 1, f"{shape} did not exit 1 (got {exit_code}); output:\n{out}"
    assert "[ERROR]" in out, f"{shape} exited 1 but printed no ERROR finding"


@pytest.mark.parametrize("shape", sorted(WRONG_TYPED_SHAPES))
def test_se_check_run_all_checks_does_not_raise_on_wrong_typed_field(shape, tmp_path):
    """Library-level: every caller of run_all_checks is protected, not just main."""
    se_check.run_all_checks(_data_with(shape), str(tmp_path))


@pytest.mark.parametrize("shape", sorted(WRONG_TYPED_SHAPES))
def test_se_check_suspect_helpers_do_not_raise_on_wrong_typed_field(shape, tmp_path):
    """The suspect cascade builds its own by_id and must guard it too.

    A hash snapshot has to exist or check_suspect_cascade returns early and
    the by_id build is never reached - which is how this stayed hidden.
    """
    generated = tmp_path / "generated"
    generated.mkdir()
    (generated / "req_hashes.json").write_text(
        '{"SYS-F-001": "stale-hash"}', encoding="utf-8")
    se_check.check_suspect_cascade(_data_with(shape), str(tmp_path))
    se_check.mark_suspect(_data_with(shape), "SYS-F-001")


@pytest.mark.parametrize("shape", sorted(WRONG_TYPED_SHAPES))
def test_se_trace_library_functions_do_not_raise_on_wrong_typed_field(shape):
    """se_trace's half of F1, never reported by any per-task review.

    These are asserted at library level on purpose: se_trace.main runs
    validate_schema first and returns 1 on ERROR, so fixing layer 1 alone
    would mask the crash at CLI level while leaving every other caller of
    these functions broken.
    """
    data = _data_with(shape)
    se_trace._decomposed_ids(data)
    se_trace.build_verified_by(data, [])
    se_trace.apply_verified_by(data, {})
    se_trace.compute_req_hashes(data)
    rows = se_trace.build_matrix_rows(data)
    se_trace.render_matrix_md(rows)
    se_trace.generate_trace_findings(data, [], [])


# =====================================================================
# The write paths refuse to run on a schema-invalid file
# =====================================================================
#
# The F1 guards are what make these tests necessary. Skipping a wrong-typed
# requirement is right for a *reporting* check - it lets the run continue and
# report every other defect. It is wrong for a *writing* path, where it turns
# what used to be a loud crash into a silent success: se_check.py --mark-suspect
# never called validate_schema, so it wrote requirements.yaml back to disk at
# exit 0 with an unrelated malformed requirement left unreported.
#
# The guard was right; it was guarding a path that should have refused to run.
# Both writing paths now require a schema-clean file, because the schema is
# exactly what makes the 'id' and 'parent' fields they walk trustworthy.
#
# Note the missing-'id' variants below: that half of the hole predates this
# wave (Plan A's guard, isinstance(r, dict) and "id" in r, had the same effect)
# and was never covered by a test either.

MALFORMED_NEIGHBOURS = {
    "wrong-typed-id": dict(id=["SYS-F-002"]),
    "wrong-typed-parent": dict(id="SYS-F-002", parent=["SYS-F-001"]),
    "wrong-typed-text": dict(id="SYS-F-002", text=["a", "b"]),
    "missing-id": "DELETE-ID",
    "missing-text": "DELETE-TEXT",
}


def _neighbour(key):
    """A second requirement that is malformed and unrelated to the target."""
    if key == "missing-id":
        req = make_requirement(text="Missing id field.")
        del req["id"]
        return req
    if key == "missing-text":
        req = make_requirement(id="SYS-F-002")
        del req["text"]
        return req
    return make_requirement(**MALFORMED_NEIGHBOURS[key])


@pytest.mark.parametrize("neighbour", sorted(MALFORMED_NEIGHBOURS))
def test_mark_suspect_refuses_to_write_when_another_requirement_is_invalid(
        neighbour, tmp_path, capsys):
    """--mark-suspect must honour the exit-code contract like every other path.

    The target requirement is perfectly valid; the defect is in an unrelated
    neighbour. Before this fix the neighbour was filtered out of by_id and the
    write went ahead at exit 0, reporting nothing at all.
    """
    _write_requirements(tmp_path, make_data([
        make_requirement(id="SYS-F-001", parent=None),
        _neighbour(neighbour),
    ]))
    req_path = tmp_path / "requirements.yaml"
    original = req_path.read_text(encoding="utf-8")

    exit_code = se_check.main([str(tmp_path), "--mark-suspect", "SYS-F-001"])
    out = capsys.readouterr().out

    assert exit_code == 1, f"expected 1, got {exit_code}; output:\n{out}"
    assert "[ERROR]" in out, "refused the write but reported no finding"
    assert req_path.read_text(encoding="utf-8") == original, \
        "requirements.yaml was modified despite a schema ERROR"


def test_mark_suspect_still_writes_on_a_schema_clean_file(tmp_path, capsys):
    """The gate must not swallow the happy path."""
    _write_requirements(tmp_path, make_data([
        make_requirement(id="SYS-F-001", parent=None),
        make_requirement(id="SYS-F-002", parent="SYS-F-001"),
    ]))
    req_path = tmp_path / "requirements.yaml"

    exit_code = se_check.main([str(tmp_path), "--mark-suspect", "SYS-F-001"])
    out = capsys.readouterr().out

    assert exit_code == 0, out
    assert "marked suspect" in out
    data = yaml.safe_load(req_path.read_text(encoding="utf-8"))
    assert all(r["suspect"] is True for r in data["requirements"])


def test_mark_suspect_returns_2_and_writes_nothing_on_malformed_yaml(tmp_path):
    """Exit 2 stays exit 2: malformed YAML is not a schema finding."""
    req_path = tmp_path / "requirements.yaml"
    req_path.write_text("meta: {levels: [SYS]\nrequirements: [", encoding="utf-8")
    original = req_path.read_text(encoding="utf-8")

    assert se_check.main([str(tmp_path), "--mark-suspect", "SYS-F-001"]) == 2
    assert req_path.read_text(encoding="utf-8") == original


@pytest.mark.parametrize("neighbour", sorted(MALFORMED_NEIGHBOURS))
def test_suspect_cascade_does_not_write_when_the_schema_is_invalid(
        neighbour, tmp_path, capsys):
    """The other write path in se_check.main, same reasoning.

    A cascade computed over a file whose ids and parents did not all parse is
    a half-computed cascade - it silently skipped the requirements it could
    not read - so persisting its conclusion writes a subtree marking that was
    never fully determined.
    """
    generated = tmp_path / "generated"
    generated.mkdir()
    # SYS-F-010, not SYS-F-002: the malformed neighbours use SYS-F-002, and a
    # duplicate ID would confound this with check_duplicate_ids.
    parent = make_requirement(id="SYS-F-001", parent=None, text="CHANGED text.")
    child = make_requirement(id="SYS-F-010", parent="SYS-F-001")
    _write_requirements(tmp_path, make_data([parent, child, _neighbour(neighbour)]))
    stale = hashlib.sha256(b"ORIGINAL text.").hexdigest()
    (generated / "req_hashes.json").write_text(
        json.dumps({"SYS-F-001": stale}), encoding="utf-8")

    req_path = tmp_path / "requirements.yaml"
    original = req_path.read_text(encoding="utf-8")

    exit_code = se_check.main([str(tmp_path)])
    out = capsys.readouterr().out

    assert exit_code == 1, out
    assert req_path.read_text(encoding="utf-8") == original, \
        "the cascade wrote to a file whose schema does not validate"


def test_suspect_cascade_still_writes_when_a_non_schema_error_is_present(tmp_path, capsys):
    """Pins where the line is drawn, so the gate is not quietly widened.

    The gate is on *schema* errors, not on any error. A dangling parent is an
    ERROR from check_orphans_and_cycles, but every id and parent in the file is
    well-formed, so the cascade's computation is complete and correct and its
    result should persist.
    """
    generated = tmp_path / "generated"
    generated.mkdir()
    # SYS-F-010, not SYS-F-002: the malformed neighbours use SYS-F-002, and a
    # duplicate ID would confound this with check_duplicate_ids.
    parent = make_requirement(id="SYS-F-001", parent=None, text="CHANGED text.")
    child = make_requirement(id="SYS-F-010", parent="SYS-F-001")
    dangling = make_requirement(id="SYS-F-003", parent="SYS-F-999")  # ERROR, not schema
    _write_requirements(tmp_path, make_data([parent, child, dangling]))
    stale = hashlib.sha256(b"ORIGINAL text.").hexdigest()
    (generated / "req_hashes.json").write_text(
        json.dumps({"SYS-F-001": stale}), encoding="utf-8")

    req_path = tmp_path / "requirements.yaml"

    exit_code = se_check.main([str(tmp_path)])
    out = capsys.readouterr().out

    assert exit_code == 1, out
    assert "check_orphans_and_cycles" in out
    data = yaml.safe_load(req_path.read_text(encoding="utf-8"))
    by_id = {r["id"]: r for r in data["requirements"]}
    assert by_id["SYS-F-010"]["suspect"] is True, \
        "the cascade result was not persisted despite a schema-clean file"


@pytest.mark.parametrize("shape", sorted(WRONG_TYPED_SHAPES))
def test_se_trace_main_returns_1_without_traceback_on_wrong_typed_field(shape, tmp_path, capsys):
    se_dir = tmp_path / "se"
    tests_dir = tmp_path / "tests"
    se_dir.mkdir()
    tests_dir.mkdir()
    _write_requirements(se_dir, _data_with(shape))

    exit_code = se_trace.main([str(se_dir), "--tests", str(tests_dir)])
    out = capsys.readouterr().out
    assert exit_code == 1, f"{shape} did not exit 1 (got {exit_code}); output:\n{out}"
    assert "[ERROR]" in out
    assert not (se_dir / "generated").exists(), \
        f"{shape} wrote generated output despite a schema ERROR"
