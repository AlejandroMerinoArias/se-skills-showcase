import os

import yaml

import se_check
from helpers import make_requirement, make_data


def _write_requirements(se_dir, data):
    os.makedirs(se_dir, exist_ok=True)
    with open(os.path.join(se_dir, "requirements.yaml"), "w", encoding="utf-8") as f:
        yaml.safe_dump(data, f, sort_keys=False)


def test_main_returns_1_on_error(tmp_path, capsys):
    data = make_data([make_requirement(id="SYS-F-001", category="derived", rationale=None)])
    _write_requirements(tmp_path, data)
    exit_code = se_check.main([str(tmp_path)])
    assert exit_code == 1
    out = capsys.readouterr().out
    assert "SYS-F-001" in out


def test_main_returns_0_on_clean_project(tmp_path):
    data = make_data([make_requirement(id="SYS-F-001")])
    _write_requirements(tmp_path, data)
    assert se_check.main([str(tmp_path)]) == 0


def test_main_returns_2_on_malformed_yaml(tmp_path):
    os.makedirs(tmp_path, exist_ok=True)
    with open(os.path.join(tmp_path, "requirements.yaml"), "w", encoding="utf-8") as f:
        f.write("meta: [broken\nrequirements: [\n")
    assert se_check.main([str(tmp_path)]) == 2


def test_run_all_checks_aggregates_every_check(tmp_path):
    data = make_data([
        make_requirement(id="SYS-F-001"),
        make_requirement(id="SYS-F-001"),  # duplicate
    ])
    findings = se_check.run_all_checks(data, str(tmp_path))
    checks_seen = {f.check for f in findings}
    assert "check_duplicate_ids" in checks_seen
