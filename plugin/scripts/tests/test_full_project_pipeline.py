import os
import shutil
import subprocess
import sys

import yaml

FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures", "full_project")
SCRIPTS_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _copy_project(tmp_path):
    dest = tmp_path / "project"
    shutil.copytree(FIXTURES, dest)
    return dest


def test_se_trace_then_se_check_end_to_end(tmp_path):
    project = _copy_project(tmp_path)
    se_dir = project / "se"
    tests_dir = project / "tests"
    junit_path = project / "junit.xml"

    trace_result = subprocess.run(
        [sys.executable, os.path.join(SCRIPTS_DIR, "se_trace.py"), str(se_dir),
         "--tests", str(tests_dir), "--results", str(junit_path)],
        capture_output=True, text=True,
    )
    assert trace_result.returncode == 0, trace_result.stdout + trace_result.stderr

    matrix_path = se_dir / "generated" / "matrix.md"
    hashes_path = se_dir / "generated" / "req_hashes.json"
    assert matrix_path.is_file()
    assert hashes_path.is_file()

    matrix_text = matrix_path.read_text()
    assert "SYS-F-001" in matrix_text
    assert "PASS" in matrix_text

    check_result = subprocess.run(
        [sys.executable, os.path.join(SCRIPTS_DIR, "se_check.py"), str(se_dir)],
        capture_output=True, text=True,
    )
    assert check_result.returncode == 0, check_result.stdout + check_result.stderr


def test_suspect_cascade_triggers_on_text_change(tmp_path):
    project = _copy_project(tmp_path)
    se_dir = project / "se"
    tests_dir = project / "tests"

    first = subprocess.run(
        [sys.executable, os.path.join(SCRIPTS_DIR, "se_trace.py"), str(se_dir), "--tests", str(tests_dir)],
        capture_output=True, text=True,
    )
    assert first.returncode == 0, first.stdout + first.stderr

    req_path = se_dir / "requirements.yaml"
    text = req_path.read_text()
    text = text.replace(
        "the controller shall command a hover state within 200 ms.",
        "the controller shall command a hover state within 150 ms.",
    )
    req_path.write_text(text)

    check_result = subprocess.run(
        [sys.executable, os.path.join(SCRIPTS_DIR, "se_check.py"), str(se_dir)],
        capture_output=True, text=True,
    )
    assert check_result.returncode == 0, check_result.stdout + check_result.stderr
    assert "suspect" in check_result.stdout.lower()

    updated = yaml.safe_load(req_path.read_text())
    by_id = {r["id"]: r for r in updated["requirements"]}
    assert by_id["ITEM-D-002"]["suspect"] is True
    assert by_id["ITEM-S-003"]["suspect"] is True
