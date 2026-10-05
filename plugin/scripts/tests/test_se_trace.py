import hashlib
import os

import yaml

import se_lib
import se_trace
from helpers import make_requirement, make_data


def test_truncate_long_text():
    long_text = "x" * 100
    assert se_trace.truncate(long_text, 60) == "x" * 57 + "..."


def test_truncate_short_text_unchanged():
    assert se_trace.truncate("short", 60) == "short"


def test_build_verified_by_maps_known_ids():
    data = make_data([make_requirement(id="SYS-F-001"), make_requirement(id="SYS-F-002")])
    test_defs = [
        se_trace.TestDef(file="test_a.py", name="test_one", line=2, req_ids=["SYS-F-001"]),
        se_trace.TestDef(file="test_a.py", name="test_two", line=8, req_ids=["SYS-F-001", "SYS-F-999"]),
    ]
    verified_by_map, unknown_refs = se_trace.build_verified_by(data, test_defs)
    assert verified_by_map["SYS-F-001"] == ["test_a.py::test_one", "test_a.py::test_two"]
    assert "SYS-F-002" not in verified_by_map
    assert unknown_refs == [("SYS-F-999", "test_a.py", 8)]


def test_apply_verified_by_updates_requirements_without_mutating_input():
    data = make_data([make_requirement(id="SYS-F-001", verified_by=[])])
    updated = se_trace.apply_verified_by(data, {"SYS-F-001": ["test_a.py::test_one"]})
    assert updated["requirements"][0]["verified_by"] == ["test_a.py::test_one"]
    assert data["requirements"][0]["verified_by"] == []


def test_compute_req_hashes():
    data = make_data([make_requirement(id="SYS-F-001", text="Fixed text.")])
    hashes = se_trace.compute_req_hashes(data)
    assert hashes["SYS-F-001"] == hashlib.sha256(b"Fixed text.").hexdigest()


def test_build_matrix_rows_unverified_and_render():
    data = make_data([make_requirement(id="SYS-F-001", text="Short text.", verified_by=[])])
    rows = se_trace.build_matrix_rows(data)
    assert rows[0]["result"] == "UNVERIFIED"
    md = se_trace.render_matrix_md(rows)
    assert "SYS-F-001" in md
    assert "Short text." in md
    assert "| ID |" in md


def test_build_matrix_rows_unknown_result_without_junit():
    data = make_data([make_requirement(id="SYS-F-001", verified_by=["t.py::test_one"])])
    rows = se_trace.build_matrix_rows(data)
    assert rows[0]["result"] == "UNKNOWN"


def test_generate_trace_findings_unknown_id_no_annotation_and_untested():
    data = make_data([make_requirement(id="SYS-F-001", moc="test", verified_by=[])])
    test_defs = [
        se_trace.TestDef(file="t.py", name="test_annotated", line=2, req_ids=["SYS-F-001"]),
        se_trace.TestDef(file="t.py", name="test_bare", line=6, req_ids=[]),
    ]
    unknown_refs = [("SYS-F-999", "t.py", 10)]
    findings = se_trace.generate_trace_findings(data, test_defs, unknown_refs)
    assert any(f.level == "ERROR" and "nonexistent" in f.message for f in findings)
    assert any(f.level == "WARNING" and "no VERIFIES annotation" in f.message for f in findings)
    assert any(f.level == "WARNING" and "no linked test" in f.message for f in findings)


def test_main_writes_matrix_hashes_and_updates_yaml(tmp_path):
    se_dir = tmp_path / "se"
    tests_dir = tmp_path / "tests"
    os.makedirs(se_dir)
    os.makedirs(tests_dir)

    data = make_data([make_requirement(id="SYS-F-001", text="Trigger response requirement.")])
    with open(se_dir / "requirements.yaml", "w", encoding="utf-8") as f:
        yaml.safe_dump(data, f, sort_keys=False)

    (tests_dir / "test_thing.py").write_text(
        "# VERIFIES: SYS-F-001\ndef test_trigger_response():\n    assert True\n"
    )

    exit_code = se_trace.main([str(se_dir), "--tests", str(tests_dir)])
    assert exit_code == 0

    matrix_path = se_dir / "generated" / "matrix.md"
    hashes_path = se_dir / "generated" / "req_hashes.json"
    assert matrix_path.is_file()
    assert hashes_path.is_file()

    updated = se_lib.load_requirements_yaml(str(se_dir / "requirements.yaml"))
    assert updated["requirements"][0]["verified_by"] == ["test_thing.py::test_trigger_response"]


FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures")


def test_parse_junit():
    results = se_trace.parse_junit(os.path.join(FIXTURES, "sample_junit.xml"))
    assert results["test_hover_command_latency_under_obstacle"] == "pass"
    assert results["test_slow_case"] == "fail"


def test_build_matrix_rows_with_junit_pass():
    data = make_data([make_requirement(
        id="SYS-F-001", verified_by=["tests/test_hover.py::test_hover_command_latency_under_obstacle"])])
    rows = se_trace.build_matrix_rows(data, {"test_hover_command_latency_under_obstacle": "pass"})
    assert rows[0]["result"] == "PASS"


def test_build_matrix_rows_with_junit_fail():
    data = make_data([make_requirement(id="SYS-F-002", verified_by=["tests/test_hover.py::test_slow_case"])])
    rows = se_trace.build_matrix_rows(data, {"test_slow_case": "fail"})
    assert rows[0]["result"] == "FAIL"


def test_main_with_results_flag_marks_pass_fail(tmp_path):
    se_dir = tmp_path / "se"
    tests_dir = tmp_path / "tests"
    os.makedirs(se_dir)
    os.makedirs(tests_dir)

    data = make_data([make_requirement(id="SYS-F-001", text="Trigger response requirement.")])
    with open(se_dir / "requirements.yaml", "w", encoding="utf-8") as f:
        yaml.safe_dump(data, f, sort_keys=False)

    (tests_dir / "test_hover.py").write_text(
        "# VERIFIES: SYS-F-001\ndef test_hover_command_latency_under_obstacle():\n    assert True\n"
    )
    junit_path = tmp_path / "junit.xml"
    junit_path.write_text(
        '<?xml version="1.0"?><testsuite name="s" tests="1" failures="0">'
        '<testcase classname="tests.test_hover" name="test_hover_command_latency_under_obstacle" time="0.01"/>'
        "</testsuite>"
    )

    exit_code = se_trace.main([str(se_dir), "--tests", str(tests_dir), "--results", str(junit_path)])
    assert exit_code == 0
    matrix_text = (se_dir / "generated" / "matrix.md").read_text()
    assert "PASS" in matrix_text
