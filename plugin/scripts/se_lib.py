"""Shared YAML loading, schema validation, and atomic-write helpers for the
se-skills verification scripts (se_check.py, se_trace.py)."""

from __future__ import annotations

import io
import os
import re
import tempfile
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from ruamel.yaml import YAML
from ruamel.yaml.error import YAMLError

CATEGORY_ENUM = {"functional", "performance", "interface", "safety", "derived", "constraint"}
CRITICALITY_ENUM = {"A", "B", "C"}
MOC_ENUM = {"test", "analysis", "inspection", "demonstration"}
STATUS_ENUM = {"draft", "validated", "implemented", "verified", "retired"}

REQUIRED_FIELDS = [
    "id", "text", "category", "criticality", "rationale", "source",
    "parent", "allocated_to", "moc", "verified_by", "status", "waiver",
    "suspect", "target", "threshold",
]

# v2: 'history' is no longer required (git is the history) but is still
# accepted, so v1 files load unchanged. 'increment' and 'open_items' are new.
OPTIONAL_FIELDS = ["history", "increment", "open_items"]

ID_PATTERN = re.compile(r"^[A-Z]+(-[A-Z]+)?-[A-Z]-\d{3}$")
INCREMENT_ID_PATTERN = re.compile(r"^I\d+$")
ITEM_ID_PATTERN = re.compile(r"^(Q|E|D)-\d{2,3}$")


def _yaml() -> YAML:
    y = YAML(typ="rt")
    y.width = 1 << 20
    y.preserve_quotes = True
    y.indent(mapping=2, sequence=2, offset=0)
    y.representer.ignore_aliases = lambda data: True
    return y


class SeYamlError(Exception):
    """Raised when requirements.yaml is missing, malformed, or the wrong shape."""


def _read_text(path: str) -> str:
    """The file's text. A file that is not UTF-8 (Windows PowerShell 5.1
    Set-Content writes the ANSI code page) is a malformed file, reported
    through SeYamlError like any other, never a traceback."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except UnicodeDecodeError as exc:
        raise SeYamlError(f"{path} is not UTF-8 ({exc.reason} at byte {exc.start}); "
                          f"re-save it as UTF-8") from exc


@dataclass
class Finding:
    level: str          # "ERROR" | "WARNING"
    check: str           # name of the check function that produced this finding
    req_id: Optional[str]
    message: str

    def format(self) -> str:
        loc = self.req_id if self.req_id else "-"
        return f"[{self.level}] {self.check}: {loc}: {self.message}"


def load_requirements_yaml(path: str) -> Dict[str, Any]:
    """Load and minimally structurally validate requirements.yaml.

    Raises SeYamlError with a clear message on any malformed-YAML or
    wrong-shape condition. Never returns a partial result.
    """
    if not os.path.isfile(path):
        raise SeYamlError(f"requirements file not found: {path}")
    raw = _read_text(path)
    try:
        data = _yaml().load(raw)
    except YAMLError as exc:
        raise SeYamlError(f"malformed YAML in {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise SeYamlError(f"{path} must contain a YAML mapping at the top level")
    if "meta" not in data or not isinstance(data["meta"], dict):
        raise SeYamlError(f"{path} is missing a 'meta' mapping")
    if "requirements" not in data or not isinstance(data["requirements"], list):
        raise SeYamlError(f"{path} is missing a 'requirements' list")
    return data


def level_prefix(req_id: Any) -> str:
    """Extract the level-prefix portion of an ID, e.g. 'SYS' from 'SYS-F-012',
    'ITEM' from 'ITEM-P-004'. Returns '' if req_id doesn't match ID_PATTERN's
    shape, including when it is not a string at all."""
    if not isinstance(req_id, str):
        return ""
    m = re.match(r"^(.+)-[A-Z]-\d{3}$", req_id)
    return m.group(1) if m else ""


def str_id(req: Any) -> Optional[str]:
    """The requirement's 'id' when it is a usable string, else None.

    Wrong-typed fields are *reported* by validate_schema; every consumer that
    then hashes, joins or regexes an id must skip the ones that are not
    strings rather than crash on them. The exit-code contract is `0` clean,
    `1` any ERROR finding, `2` malformed YAML — a traceback is none of these,
    and a caller parsing stdout for '[ERROR]' sees nothing at all.
    """
    if not isinstance(req, dict):
        return None
    rid = req.get("id")
    return rid if isinstance(rid, str) and rid else None


def str_parent(req: Any) -> Optional[str]:
    """The requirement's 'parent' when it is a usable string, else None.

    Returning None for a wrong-typed parent is deliberate: None is the
    'no parent' value the tree walkers already handle, so a malformed parent
    degrades to a requirement that is simply not linked, and the schema
    finding is what tells the user why.
    """
    if not isinstance(req, dict):
        return None
    parent = req.get("parent")
    return parent if isinstance(parent, str) and parent else None


def validate_schema(data: Dict[str, Any]) -> List[Finding]:
    """Validate meta.levels presence and per-requirement field/enum/ID-format rules.

    Assumes `data` already passed load_requirements_yaml's structural checks
    (has a 'meta' dict and a 'requirements' list)."""
    findings: List[Finding] = []
    meta = data.get("meta", {})
    if not isinstance(meta.get("levels"), list) or not meta.get("levels"):
        findings.append(Finding("ERROR", "validate_schema", None,
                                 "meta.levels must be a non-empty list"))

    for idx, req in enumerate(data.get("requirements", [])):
        if not isinstance(req, dict):
            findings.append(Finding("ERROR", "validate_schema", None,
                                     f"requirement at index {idx} is not a mapping"))
            continue

        # Report against a printable id. A wrong-typed id is itself a finding
        # below; carrying the raw value into every other finding's location
        # field would put a list or a dict where a caller expects an ID.
        req_id = req.get("id") if isinstance(req.get("id"), str) else None

        missing = [fld for fld in REQUIRED_FIELDS if fld not in req]
        for fld in missing:
            findings.append(Finding("ERROR", "validate_schema", req_id,
                                     f"missing required field '{fld}'"))

        if not isinstance(req_id, str) or not req_id:
            findings.append(Finding("ERROR", "validate_schema", req_id,
                                     "requirement has no 'id'"))
        elif not ID_PATTERN.match(req_id):
            findings.append(Finding("ERROR", "validate_schema", req_id,
                                     f"id '{req_id}' does not match required format"))

        text = req.get("text")
        if not isinstance(text, str) or not text.strip():
            findings.append(Finding("ERROR", "validate_schema", req_id,
                                     "'text' must be a non-empty string"))

        category = req.get("category")
        if category not in CATEGORY_ENUM:
            findings.append(Finding("ERROR", "validate_schema", req_id,
                                     f"'category' value '{category}' not in {sorted(CATEGORY_ENUM)}"))

        criticality = req.get("criticality")
        if criticality not in CRITICALITY_ENUM:
            findings.append(Finding("ERROR", "validate_schema", req_id,
                                     f"'criticality' value '{criticality}' not in {sorted(CRITICALITY_ENUM)}"))

        moc = req.get("moc")
        if moc not in MOC_ENUM:
            findings.append(Finding("ERROR", "validate_schema", req_id,
                                     f"'moc' value '{moc}' not in {sorted(MOC_ENUM)}"))

        status = req.get("status")
        if status not in STATUS_ENUM:
            findings.append(Finding("ERROR", "validate_schema", req_id,
                                     f"'status' value '{status}' not in {sorted(STATUS_ENUM)}"))

        # 'parent' is a single ID string or null - never a list. A list here
        # is the commonest hand-edit mistake (it looks like allocated_to) and
        # it is unhashable, so every by_id lookup downstream would raise.
        parent = req.get("parent")
        if parent is not None and not isinstance(parent, str):
            findings.append(Finding("ERROR", "validate_schema", req_id,
                                     f"'parent' must be a single requirement ID string or null, "
                                     f"got {type(parent).__name__}"))

        # 'verified_by' is a list of strings: test references written by
        # se_trace.py, or evidence paths under se/evidence/. A non-string
        # element reaches os.path.join in check_moc_evidence.
        verified_by = req.get("verified_by")
        if verified_by is not None and not isinstance(verified_by, list):
            findings.append(Finding("ERROR", "validate_schema", req_id,
                                     f"'verified_by' must be a list, got {type(verified_by).__name__}"))
        elif isinstance(verified_by, list):
            for entry in verified_by:
                if not isinstance(entry, str):
                    findings.append(Finding("ERROR", "validate_schema", req_id,
                                             f"'verified_by' entries must be strings, "
                                             f"got {type(entry).__name__}"))

        increment = req.get("increment")
        if increment is not None and (not isinstance(increment, str)
                                      or not INCREMENT_ID_PATTERN.match(increment)):
            findings.append(Finding("ERROR", "validate_schema", req_id,
                                     f"'increment' must be an increment ID like 'I2', "
                                     f"got {increment!r}"))

        open_items = req.get("open_items")
        if open_items is not None and (
                not isinstance(open_items, list)
                or not all(isinstance(e, str) and ITEM_ID_PATTERN.match(e) for e in open_items)):
            findings.append(Finding("ERROR", "validate_schema", req_id,
                                     f"'open_items' must be a list of item IDs like 'E-02', "
                                     f"got {open_items!r}"))

    return findings


CONFIG_FILENAME = "se-config.yaml"
CONFIG_MODE_ENUM = {"lite", "full"}
CONFIG_RESEARCH_ENUM = {"enabled", "disabled", "ask"}
# One legal value, deliberately. `pytest-markers` was legal here and
# implemented nowhere: se_trace.py never reads the traceability key and
# scans only for VERIFIES annotations. Once se:verification began gating
# on `se_trace.py --strict`, a project that picked the offered option and
# wrote @pytest.mark.verifies(...) would have every moc: test requirement
# render UNVERIFIED and fail a gate for doing exactly what its own config
# told it to. Removing the value makes that config an ERROR at load time
# instead of an unexplained gate failure three phases later. Restore it
# only together with a scanner that reads markers.
CONFIG_TRACEABILITY_ENUM = {"annotation"}
CONFIG_MODEL_KEYS = ["crit_a", "crit_b", "crit_c", "architecture"]
CONFIG_TOP_LEVEL_KEYS = ["mode", "models", "research", "traceability", "test_command"]
CONFIG_OPTIONAL_KEYS = ["sim_command", "budgets", "size_limits"]

DEFAULT_BUDGETS = {
    "review_rounds_per_phase": 2,
    "customer_questions_per_gate": 5,
    "customer_questions_total": 15,
    "dispatches_per_increment": 8,
    "agent_soft_tokens": 150000,
}

DEFAULT_SIZE_LIMITS = {
    "conops_kb": 15,
    "architecture_kb": 40,
    "rationale_chars": 400,
    "se_dir_kb": 100,
}


def _is_positive_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 1


def _effective(cfg: Optional[Dict[str, Any]], key: str, defaults: Dict[str, int]) -> Dict[str, int]:
    """Defaults overlaid with the valid entries of cfg[key]. An invalid entry
    is validate_config's finding; here it simply does not override."""
    merged = dict(defaults)
    section = (cfg or {}).get(key)
    if isinstance(section, dict):
        for k, v in section.items():
            if k in defaults and _is_positive_int(v):
                merged[k] = v
    return merged


def effective_budgets(cfg: Optional[Dict[str, Any]]) -> Dict[str, int]:
    return _effective(cfg, "budgets", DEFAULT_BUDGETS)


def effective_size_limits(cfg: Optional[Dict[str, Any]]) -> Dict[str, int]:
    return _effective(cfg, "size_limits", DEFAULT_SIZE_LIMITS)


def load_config_yaml(path: str) -> Dict[str, Any]:
    """Load and structurally validate se-config.yaml.

    Raises SeYamlError on missing file, malformed YAML, or a non-mapping
    top level. An *absent* config is not this function's problem to excuse:
    callers decide whether absence is legal (for a new project it is — it is
    the state that routes to se:tailoring)."""
    if not os.path.isfile(path):
        raise SeYamlError(f"config file not found: {path}")
    raw = _read_text(path)
    try:
        data = _yaml().load(raw)
    except YAMLError as exc:
        raise SeYamlError(f"malformed YAML in {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise SeYamlError(f"{path} must contain a YAML mapping at the top level")
    return data


def validate_config(cfg: Dict[str, Any]) -> List[Finding]:
    """Validate se-config.yaml against spec section 5.

    Unknown top-level keys are a WARNING, not an ERROR: the config is
    user-editable and forward compatibility beats brittleness. Every value
    the plugin actually routes on is an ERROR when wrong."""
    findings: List[Finding] = []

    def err(message: str) -> None:
        findings.append(Finding("ERROR", "validate_config", None, message))

    for key in CONFIG_TOP_LEVEL_KEYS:
        if key not in cfg:
            err(f"missing required key '{key}'")

    for key in cfg:
        if key not in CONFIG_TOP_LEVEL_KEYS and key not in CONFIG_OPTIONAL_KEYS:
            findings.append(Finding("WARNING", "validate_config", None,
                                     f"unknown top-level key '{key}'"))

    if "mode" in cfg and (not isinstance(cfg["mode"], str) or cfg["mode"] not in CONFIG_MODE_ENUM):
        err(f"'mode' value '{cfg['mode']}' not in {sorted(CONFIG_MODE_ENUM)}")

    if "research" in cfg and (not isinstance(cfg["research"], str) or cfg["research"] not in CONFIG_RESEARCH_ENUM):
        err(f"'research' value '{cfg['research']}' not in {sorted(CONFIG_RESEARCH_ENUM)}")

    if "traceability" in cfg and (not isinstance(cfg["traceability"], str) or cfg["traceability"] not in CONFIG_TRACEABILITY_ENUM):
        err(f"'traceability' value '{cfg['traceability']}' not in {sorted(CONFIG_TRACEABILITY_ENUM)}")

    if "test_command" in cfg:
        cmd = cfg["test_command"]
        if not isinstance(cmd, str) or not cmd.strip():
            err("'test_command' must be a non-empty string")

    if "sim_command" in cfg:
        cmd = cfg["sim_command"]
        if not isinstance(cmd, str) or not cmd.strip():
            err("'sim_command' must be a non-empty string")

    for section, defaults in (("budgets", DEFAULT_BUDGETS), ("size_limits", DEFAULT_SIZE_LIMITS)):
        if section not in cfg:
            continue
        value = cfg[section]
        if not isinstance(value, dict):
            err(f"'{section}' must be a mapping")
            continue
        for k, v in value.items():
            if k not in defaults:
                findings.append(Finding("WARNING", "validate_config", None,
                                         f"unknown key '{k}' in '{section}'"))
            elif not _is_positive_int(v):
                err(f"{section}['{k}'] must be a positive integer")

    if "models" in cfg:
        models = cfg["models"]
        if not isinstance(models, dict):
            err("'models' must be a mapping")
        else:
            for key in CONFIG_MODEL_KEYS:
                if key not in models:
                    err(f"models is missing required key '{key}'")
                elif not isinstance(models[key], str) or not models[key].strip():
                    err(f"models['{key}'] must be a non-empty string")

    return findings


EVIDENCE_SUBDIR = "evidence"


def resolve_evidence(se_dir: str, entry: str) -> Optional[str]:
    """Resolve an evidence reference (relative to se_dir) to an absolute path.

    Returns the path only if it stays inside se_dir/evidence/. Returns None for
    absolute paths and for anything that escapes via '..' — evidence is project
    state, and a reference that reaches outside the se/ tree is a defect
    regardless of whether the file happens to exist."""
    if os.path.isabs(entry):
        return None
    root = os.path.realpath(os.path.join(se_dir, EVIDENCE_SUBDIR))
    candidate = os.path.realpath(os.path.join(se_dir, entry))
    if candidate != root and not candidate.startswith(root + os.sep):
        return None
    return candidate


def load_yaml_mapping(path: str, allow_empty: bool = False) -> Dict[str, Any]:
    """Load a YAML file whose top level must be a mapping. Raises SeYamlError
    on malformed YAML or a non-mapping top level. With allow_empty, an empty
    file is an empty mapping. The caller checks existence."""
    raw = _read_text(path)
    try:
        data = _yaml().load(raw)
    except YAMLError as exc:
        raise SeYamlError(f"malformed YAML in {path}: {exc}") from exc
    if data is None and allow_empty:
        return {}
    if not isinstance(data, dict):
        raise SeYamlError(f"{path} must contain a YAML mapping at the top level")
    return data


def atomic_write_text(path: str, content: str) -> None:
    """Write `content` to `path` atomically (temp file in the same directory,
    then os.replace). On any failure, the temp file is removed and no partial
    write to `path` ever occurs."""
    directory = os.path.dirname(os.path.abspath(path)) or "."
    os.makedirs(directory, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(prefix=".tmp-", dir=directory)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as f:
            f.write(content)
        os.replace(tmp_path, path)
    except BaseException:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
        raise


def dump_requirements_yaml(data: Dict[str, Any]) -> str:
    buf = io.StringIO()
    _yaml().dump(data, buf)
    return buf.getvalue()


def atomic_write_yaml(path: str, data: Dict[str, Any]) -> None:
    atomic_write_text(path, dump_requirements_yaml(data))
