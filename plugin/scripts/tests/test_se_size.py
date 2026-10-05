"""BLOAT warnings (v2 design spec section 6.4)."""

import se_lib
import se_size
from helpers import make_data, make_requirement

LIMITS = dict(se_lib.DEFAULT_SIZE_LIMITS)


def test_short_rationale_is_clean():
    data = make_data([make_requirement(rationale="x" * 400)])
    assert se_size.check_rationale_length(data, LIMITS) == []


def test_long_rationale_warns():
    data = make_data([make_requirement(rationale="x" * 401)])
    findings = se_size.check_rationale_length(data, LIMITS)
    assert len(findings) == 1
    assert findings[0].level == "WARNING" and findings[0].message.startswith("BLOAT:")
    assert findings[0].req_id == "SYS-F-001"


def test_small_se_dir_is_clean(tmp_path):
    (tmp_path / "CONOPS.md").write_text("purpose", encoding="utf-8")
    assert se_size.check_artifact_sizes(str(tmp_path), LIMITS) == []


def test_large_conops_and_architecture_warn(tmp_path):
    (tmp_path / "CONOPS.md").write_text("x" * (16 * 1024), encoding="utf-8")
    (tmp_path / "architecture.md").write_text("x" * (41 * 1024), encoding="utf-8")
    msgs = [f.message for f in se_size.check_artifact_sizes(str(tmp_path), LIMITS)]
    assert any("CONOPS.md" in m for m in msgs)
    assert any("architecture.md" in m for m in msgs)


def test_generated_and_evidence_do_not_count(tmp_path):
    for sub in ("generated", "evidence"):
        (tmp_path / sub).mkdir()
        (tmp_path / sub / "big.txt").write_text("x" * (200 * 1024), encoding="utf-8")
    assert se_size.check_artifact_sizes(str(tmp_path), LIMITS) == []


def test_whole_dir_limit(tmp_path):
    (tmp_path / "requirements.yaml").write_text("x" * (101 * 1024), encoding="utf-8")
    msgs = [f.message for f in se_size.check_artifact_sizes(str(tmp_path), LIMITS)]
    assert any(m.startswith("BLOAT: se/") for m in msgs)


def test_limits_follow_config(tmp_path):
    (tmp_path / "CONOPS.md").write_text("x" * 2048, encoding="utf-8")
    limits = se_lib.effective_size_limits({"size_limits": {"conops_kb": 1}})
    assert se_size.check_artifact_sizes(str(tmp_path), limits)
