import os

import se_lib
from helpers import make_requirement, make_data

VALID_YAML = """
meta:
  project: demo
  mode: lite
  levels: [SYS]
requirements:
  - id: SYS-F-001
    text: "Sample requirement text."
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
    history: []
"""


def test_load_requirements_yaml_valid(tmp_path):
    path = tmp_path / "requirements.yaml"
    path.write_text(VALID_YAML)
    data = se_lib.load_requirements_yaml(str(path))
    assert data["meta"]["project"] == "demo"
    assert data["requirements"][0]["id"] == "SYS-F-001"


def test_load_requirements_yaml_missing_file(tmp_path):
    missing = tmp_path / "does_not_exist.yaml"
    try:
        se_lib.load_requirements_yaml(str(missing))
        assert False, "expected SeYamlError"
    except se_lib.SeYamlError as exc:
        assert "not found" in str(exc)


def test_load_requirements_yaml_malformed(tmp_path):
    path = tmp_path / "requirements.yaml"
    path.write_text("meta: [broken\nrequirements: [\n")
    try:
        se_lib.load_requirements_yaml(str(path))
        assert False, "expected SeYamlError"
    except se_lib.SeYamlError as exc:
        assert "malformed YAML" in str(exc)


def test_load_requirements_yaml_not_a_mapping(tmp_path):
    path = tmp_path / "requirements.yaml"
    path.write_text("- system\n- item\n")
    try:
        se_lib.load_requirements_yaml(str(path))
        assert False, "expected SeYamlError"
    except se_lib.SeYamlError as exc:
        assert "mapping" in str(exc)


def test_load_requirements_yaml_missing_meta(tmp_path):
    path = tmp_path / "requirements.yaml"
    path.write_text("requirements: []\n")
    try:
        se_lib.load_requirements_yaml(str(path))
        assert False, "expected SeYamlError"
    except se_lib.SeYamlError as exc:
        assert "meta" in str(exc)


def test_validate_schema_valid_has_no_findings():
    data = make_data([make_requirement(id="SYS-F-001")])
    assert se_lib.validate_schema(data) == []


def test_validate_schema_missing_field():
    req = make_requirement(id="SYS-F-001")
    del req["rationale"]
    data = make_data([req])
    findings = se_lib.validate_schema(data)
    assert any(f.message == "missing required field 'rationale'" for f in findings)


def test_validate_schema_bad_id_format():
    data = make_data([make_requirement(id="sys-f-1")])
    findings = se_lib.validate_schema(data)
    assert any("does not match required format" in f.message for f in findings)


def test_validate_schema_bad_enums():
    data = make_data([make_requirement(
        id="SYS-F-001", category="speedy", criticality="Z", moc="manual", status="done")])
    findings = se_lib.validate_schema(data)
    messages = " ".join(f.message for f in findings)
    assert "category" in messages
    assert "criticality" in messages
    assert "moc" in messages
    assert "status" in messages


def test_validate_schema_missing_levels():
    data = {"meta": {"project": "demo", "mode": "lite"}, "requirements": []}
    findings = se_lib.validate_schema(data)
    assert any("meta.levels" in f.message for f in findings)


def test_level_prefix():
    assert se_lib.level_prefix("SYS-F-012") == "SYS"
    assert se_lib.level_prefix("ITEM-P-004") == "ITEM"
    assert se_lib.level_prefix("not-an-id") == ""


def test_atomic_write_yaml_roundtrip(tmp_path):
    data = make_data([make_requirement(id="SYS-F-001")])
    path = str(tmp_path / "requirements.yaml")
    se_lib.atomic_write_yaml(path, data)
    reloaded = se_lib.load_requirements_yaml(path)
    assert reloaded == data
    leftovers = [p for p in os.listdir(tmp_path) if p.startswith(".tmp-")]
    assert leftovers == []


def test_dump_requirements_yaml_preserves_field_order():
    data = make_data([make_requirement(id="SYS-F-001")])
    dumped = se_lib.dump_requirements_yaml(data)
    id_pos = dumped.index("id: SYS-F-001")
    text_pos = dumped.index("text:")
    category_pos = dumped.index("category:")
    assert id_pos < text_pos < category_pos
