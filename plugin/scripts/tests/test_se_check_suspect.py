import hashlib
import json
import os

import se_check
from helpers import make_requirement, make_data


def test_check_suspect_cascade_marks_subtree(tmp_path):
    generated_dir = tmp_path / "generated"
    generated_dir.mkdir()
    old_hashes = {
        "SYS-F-001": hashlib.sha256(b"Old text.").hexdigest(),
        "SYS-F-002": hashlib.sha256(b"Child text.").hexdigest(),
    }
    (generated_dir / "req_hashes.json").write_text(json.dumps(old_hashes))

    data = make_data([
        make_requirement(id="SYS-F-001", text="New text.", parent=None, suspect=False),
        make_requirement(id="SYS-F-002", text="Child text.", parent="SYS-F-001", suspect=False),
    ])
    findings, updated, changed = se_check.check_suspect_cascade(data, str(tmp_path))
    assert changed is True
    by_id = {r["id"]: r for r in updated["requirements"]}
    assert by_id["SYS-F-002"]["suspect"] is True
    assert any(f.req_id == "SYS-F-002" for f in findings)


def test_check_suspect_cascade_no_snapshot_is_noop(tmp_path):
    data = make_data([make_requirement(id="SYS-F-001")])
    findings, updated, changed = se_check.check_suspect_cascade(data, str(tmp_path))
    assert findings == []
    assert changed is False


def test_check_suspect_cascade_unchanged_text_is_noop(tmp_path):
    generated_dir = tmp_path / "generated"
    generated_dir.mkdir()
    hashes = {"SYS-F-001": hashlib.sha256(b"Same text.").hexdigest()}
    (generated_dir / "req_hashes.json").write_text(json.dumps(hashes))
    data = make_data([make_requirement(id="SYS-F-001", text="Same text.")])
    findings, updated, changed = se_check.check_suspect_cascade(data, str(tmp_path))
    assert findings == []
    assert changed is False


def test_mark_suspect_explicit_cascade():
    data = make_data([
        make_requirement(id="SYS-F-001", parent=None),
        make_requirement(id="SYS-F-002", parent="SYS-F-001"),
        make_requirement(id="SYS-F-003", parent="SYS-F-002"),
    ])
    updated, subtree = se_check.mark_suspect(data, "SYS-F-001")
    by_id = {r["id"]: r for r in updated["requirements"]}
    assert by_id["SYS-F-001"]["suspect"] is True
    assert by_id["SYS-F-002"]["suspect"] is True
    assert by_id["SYS-F-003"]["suspect"] is True
    assert set(subtree) == {"SYS-F-001", "SYS-F-002", "SYS-F-003"}


def test_main_mark_suspect_flag_writes_yaml(tmp_path):
    import yaml
    data = make_data([
        make_requirement(id="SYS-F-001", parent=None),
        make_requirement(id="SYS-F-002", parent="SYS-F-001"),
    ])
    os.makedirs(tmp_path, exist_ok=True)
    with open(tmp_path / "requirements.yaml", "w", encoding="utf-8") as f:
        yaml.safe_dump(data, f, sort_keys=False)

    exit_code = se_check.main([str(tmp_path), "--mark-suspect", "SYS-F-001"])
    assert exit_code == 0

    with open(tmp_path / "requirements.yaml", encoding="utf-8") as f:
        reloaded = yaml.safe_load(f)
    by_id = {r["id"]: r for r in reloaded["requirements"]}
    assert by_id["SYS-F-002"]["suspect"] is True
