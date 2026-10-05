"""se-config.yaml schema (spec section 5) — the contract se:tailoring writes
and every later phase skill reads."""

import pytest

import se_check
import se_lib


def _cfg(**overrides):
    cfg = {
        "mode": "full",
        "models": {"crit_a": "opus", "crit_b": "sonnet",
                   "crit_c": "sonnet", "architecture": "opus"},
        "research": "ask",
        "traceability": "annotation",
        "test_command": "python -m pytest",
    }
    cfg.update(overrides)
    return cfg


def _messages(findings):
    return " | ".join(f.message for f in findings)


def test_valid_config_has_no_findings():
    assert se_lib.validate_config(_cfg()) == []


def test_lite_mode_is_valid():
    assert se_lib.validate_config(_cfg(mode="lite")) == []


def test_unknown_mode_is_an_error():
    findings = se_lib.validate_config(_cfg(mode="medium"))
    assert [f.level for f in findings] == ["ERROR"]
    assert "mode" in _messages(findings)


def test_unknown_research_value_is_an_error():
    findings = se_lib.validate_config(_cfg(research="maybe"))
    assert [f.level for f in findings] == ["ERROR"]


def test_unknown_traceability_value_is_an_error():
    findings = se_lib.validate_config(_cfg(traceability="test-names"))
    assert [f.level for f in findings] == ["ERROR"]


def test_pytest_markers_is_rejected():
    """`pytest-markers` was a legal value with no implementation anywhere:
    se_trace.py does not read the traceability key and scans only for
    VERIFIES annotations, so a project that took the option se:tailoring
    offered would see every moc: test requirement render UNVERIFIED and fail
    se:verification's --strict gate, with the skill best placed to explain it
    blaming annotation placement. The value is removed; a config still
    carrying it must fail loudly at load time rather than three phases
    later."""
    findings = se_lib.validate_config(_cfg(traceability="pytest-markers"))
    assert [f.level for f in findings] == ["ERROR"]
    assert "pytest-markers" in _messages(findings)


def test_annotation_is_the_only_legal_traceability_value():
    assert se_lib.CONFIG_TRACEABILITY_ENUM == {"annotation"}


def test_missing_model_key_is_an_error():
    models = {"crit_a": "opus", "crit_b": "sonnet", "crit_c": "sonnet"}
    findings = se_lib.validate_config(_cfg(models=models))
    assert [f.level for f in findings] == ["ERROR"]
    assert "architecture" in _messages(findings)


def test_empty_model_value_is_an_error():
    models = {"crit_a": "", "crit_b": "sonnet",
              "crit_c": "sonnet", "architecture": "opus"}
    findings = se_lib.validate_config(_cfg(models=models))
    assert [f.level for f in findings] == ["ERROR"]


def test_models_not_a_mapping_is_an_error():
    findings = se_lib.validate_config(_cfg(models="opus"))
    assert [f.level for f in findings] == ["ERROR"]


def test_empty_test_command_is_an_error():
    findings = se_lib.validate_config(_cfg(test_command="   "))
    assert [f.level for f in findings] == ["ERROR"]


def test_non_string_mode_is_an_error():
    findings = se_lib.validate_config(_cfg(mode=["full"]))
    assert [f.level for f in findings] == ["ERROR"]


def test_non_string_research_is_an_error():
    findings = se_lib.validate_config(_cfg(research=["ask"]))
    assert [f.level for f in findings] == ["ERROR"]


def test_non_string_traceability_is_an_error():
    findings = se_lib.validate_config(_cfg(traceability=["annotation"]))
    assert [f.level for f in findings] == ["ERROR"]


def test_missing_top_level_key_is_an_error():
    cfg = _cfg()
    del cfg["test_command"]
    findings = se_lib.validate_config(cfg)
    assert [f.level for f in findings] == ["ERROR"]


def test_unknown_top_level_key_is_a_warning_not_an_error():
    findings = se_lib.validate_config(_cfg(future_option="x"))
    assert [f.level for f in findings] == ["WARNING"]
    assert "future_option" in _messages(findings)


def test_load_config_rejects_malformed_yaml(tmp_path):
    path = tmp_path / "se-config.yaml"
    path.write_text("mode: [unclosed\n", encoding="utf-8")
    with pytest.raises(se_lib.SeYamlError):
        se_lib.load_config_yaml(str(path))


def test_load_config_rejects_non_mapping(tmp_path):
    path = tmp_path / "se-config.yaml"
    path.write_text("- a\n- b\n", encoding="utf-8")
    with pytest.raises(se_lib.SeYamlError):
        se_lib.load_config_yaml(str(path))


def test_load_config_rejects_missing_file(tmp_path):
    with pytest.raises(se_lib.SeYamlError):
        se_lib.load_config_yaml(str(tmp_path / "nope.yaml"))


def _write_minimal_project(tmp_path, config_text=None):
    se_dir = tmp_path / "se"
    se_dir.mkdir()
    (se_dir / "requirements.yaml").write_text(
        "meta:\n  project: p\n  mode: lite\n  levels: [SYS]\nrequirements: []\n",
        encoding="utf-8")
    if config_text is not None:
        (se_dir / "se-config.yaml").write_text(config_text, encoding="utf-8")
    return se_dir


def test_se_check_passes_when_config_absent(tmp_path, capsys):
    se_dir = _write_minimal_project(tmp_path)
    assert se_check.main([str(se_dir)]) == 0


def test_se_check_reports_invalid_config(tmp_path, capsys):
    se_dir = _write_minimal_project(tmp_path, "mode: medium\n")
    assert se_check.main([str(se_dir)]) == 1
    assert "validate_config" in capsys.readouterr().out


def test_se_check_exits_2_on_malformed_config(tmp_path, capsys):
    se_dir = _write_minimal_project(tmp_path, "mode: [unclosed\n")
    assert se_check.main([str(se_dir)]) == 2
