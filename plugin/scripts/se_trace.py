"""se_trace.py - scans a test tree for VERIFIES: annotations, populates
verified_by on each requirement, and writes the generated traceability matrix
and text-hash snapshot (spec sections 3 rule 7 and 4).

--strict is the final verification gate (spec section 7): it does not change
what is computed, only which findings block. trace_undetailed stays a
WARNING even under --strict — it fires on shapes the gate already judges
through their children. The gate believes the JUnit results over the
status field on both sides: a FAILing linked test is an error even at
status: verified, and so is an UNKNOWN one — verified_by test evidence that
no results confirm actually ran, whether because --results was omitted or
because the linked test's name is absent from the results that were given.

Usage:
    python se_trace.py <se-dir> --tests <test-dir> [--results <junit.xml>] [--strict]
"""

from __future__ import annotations

import argparse
import copy
import fnmatch
import hashlib
import json
import os
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import se_lib

TEST_FILE_GLOBS = ("*.py", "*.cpp", "*.hpp", "*.js", "*.ts")

VERIFIES_RE = re.compile(r"(?:#|//)\s*VERIFIES:\s*(.+)")
PY_TEST_RE = re.compile(r"^\s*def\s+(test_\w+)\s*\(")
CPP_TEST_RE = re.compile(r"^\s*TEST(?:_F)?\(\s*(\w+)\s*,\s*(\w+)\s*\)")
JS_TEST_RE = re.compile(r"^\s*it\(\s*['\"]([^'\"]+)['\"]")

MAX_LOOKAHEAD = 5


@dataclass
class TestDef:
    file: str
    name: str
    line: int
    req_ids: List[str] = field(default_factory=list)


def _iter_test_files(test_dir):
    for root, _dirs, files in os.walk(test_dir):
        for fname in files:
            if any(fnmatch.fnmatch(fname, pat) for pat in TEST_FILE_GLOBS):
                full = os.path.join(root, fname)
                rel = os.path.relpath(full, test_dir).replace(os.sep, "/")
                yield full, rel


def _match_test_def(line):
    m = PY_TEST_RE.match(line)
    if m:
        return m.group(1)
    m = CPP_TEST_RE.match(line)
    if m:
        return f"{m.group(1)}.{m.group(2)}"
    m = JS_TEST_RE.match(line)
    if m:
        return m.group(1)
    return None


def scan_tests(test_dir: str) -> List[TestDef]:
    """Scan *.py, *.cpp, *.hpp, *.js, *.ts files under test_dir for VERIFIES:
    annotations attached to the next test definition."""
    test_defs: List[TestDef] = []
    for full_path, rel_path in _iter_test_files(test_dir):
        with open(full_path, "r", encoding="utf-8") as f:
            lines = f.readlines()

        pending_req_ids = None
        pending_line = None
        for idx, line in enumerate(lines):
            m = VERIFIES_RE.search(line)
            if m:
                pending_req_ids = [s.strip() for s in m.group(1).split(",") if s.strip()]
                pending_line = idx
                continue

            name = _match_test_def(line)
            if name is not None:
                if pending_req_ids is not None and idx - pending_line <= MAX_LOOKAHEAD:
                    test_defs.append(TestDef(rel_path, name, idx + 1, pending_req_ids))
                else:
                    test_defs.append(TestDef(rel_path, name, idx + 1, []))
                pending_req_ids = None
                pending_line = None
    return test_defs


def truncate(text: str, n: int = 60) -> str:
    return text if len(text) <= n else text[: n - 3] + "..."


def build_verified_by(data: dict, test_defs: List[TestDef]) -> Tuple[Dict[str, List[str]], List[Tuple[str, str, int]]]:
    """Map each known requirement ID to its sorted 'file::name' references.
    Returns (verified_by_map, unknown_refs) where unknown_refs lists
    (req_id, file, line) for VERIFIES ids that don't exist in requirements.yaml."""
    known_ids = {se_lib.str_id(r) for r in data.get("requirements", [])
                 if se_lib.str_id(r) is not None}
    verified_by_map: Dict[str, List[str]] = {}
    unknown_refs: List[Tuple[str, str, int]] = []
    for t in test_defs:
        for rid in t.req_ids:
            if rid not in known_ids:
                unknown_refs.append((rid, t.file, t.line))
                continue
            verified_by_map.setdefault(rid, []).append(f"{t.file}::{t.name}")
    for rid in verified_by_map:
        verified_by_map[rid] = sorted(set(verified_by_map[rid]))
    return verified_by_map, unknown_refs


def apply_verified_by(data: dict, verified_by_map: Dict[str, List[str]]) -> dict:
    """Return a new requirements dict with verified_by set from the test scan.
    Only moc: test requirements are touched — for analysis/inspection/
    demonstration, verified_by holds evidence references owned by agents or
    the user, never by the scanner (spec section 3, rule 4).
    Does not mutate the input `data`."""
    new_data = copy.deepcopy(data)
    for r in new_data.get("requirements", []):
        rid = se_lib.str_id(r)
        if rid is not None and r.get("moc") == "test":
            r["verified_by"] = verified_by_map.get(rid, [])
    return new_data


def compute_req_hashes(data: dict) -> Dict[str, str]:
    return {se_lib.str_id(r): hashlib.sha256(r["text"].encode("utf-8")).hexdigest()
            for r in data.get("requirements", [])
            if se_lib.str_id(r) is not None and isinstance(r.get("text"), str) and r["text"]}


def _row_result(verified_by: List[str], junit_results: Optional[Dict[str, str]]) -> str:
    if not verified_by:
        return "UNVERIFIED"
    if junit_results is None:
        return "UNKNOWN"
    statuses = [junit_results.get(vb.split("::")[-1]) for vb in verified_by]
    if any(s == "fail" for s in statuses):
        return "FAIL"
    if all(s == "pass" for s in statuses):
        return "PASS"
    return "UNKNOWN"


def _decomposed_ids(data: dict) -> set:
    """IDs that at least one other requirement names as its parent. Such a
    requirement is verified through its children; it has no test of its own.

    A non-string 'parent' is skipped rather than added to the set: it is
    unhashable in the list/dict case, and validate_schema is what reports it."""
    parents = (se_lib.str_parent(r) for r in data.get("requirements", []))
    return {p for p in parents if p is not None}


def build_matrix_rows(data: dict, junit_results: Optional[Dict[str, str]] = None) -> List[dict]:
    decomposed = _decomposed_ids(data)
    rows = []
    for r in data.get("requirements", []):
        rid = se_lib.str_id(r)
        verified_by = r.get("verified_by") or []
        if not isinstance(verified_by, list):
            verified_by = []
        if not verified_by and rid is not None and rid in decomposed:
            # Verified through decomposition: the children carry the evidence.
            # UNVERIFIED here would put a permanent floor under the matrix and
            # make se:verification's 100% exit gate unreachable in full mode.
            result = "NESTED"
        elif r.get("moc") == "test":
            result = _row_result(verified_by, junit_results)
        else:
            result = "EVIDENCE" if verified_by else "UNVERIFIED"
        text = r.get("text")
        rows.append({
            "id": rid if rid is not None else r.get("id"),
            "increment": r.get("increment"),
            "text": truncate(text) if isinstance(text, str) else "",
            "criticality": r.get("criticality"),
            "moc": r.get("moc"),
            "status": r.get("status"),
            "verified_by": verified_by,
            "result": result,
        })
    return rows


def _escape_cell(value) -> str:
    """Render a matrix cell so its content cannot break the table's column
    structure. A '|' inside requirement text would otherwise be read by every
    Markdown renderer as a column separator, and a newline inside it would end
    the row outright — a Markdown table row is exactly one line, so a two-line
    requirement text turns one row into one row plus one line of garbage that
    terminates the table."""
    if value is None:
        return ""
    return (str(value)
            .replace("\r\n", " ")
            .replace("\r", " ")
            .replace("\n", " ")
            .replace("|", r"\|"))


def render_matrix_md(rows: List[dict]) -> str:
    lines = [
        "| ID | Inc | Text | CRIT | MoC | Status | Verified By | Result |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for row in rows:
        # str() per entry: a wrong-typed verified_by element is validate_schema's
        # finding, and the matrix must still render rather than raise here.
        vb = "; ".join(str(e) for e in row["verified_by"]) if row["verified_by"] else "-"
        cells = [
            _escape_cell(row["id"]),
            _escape_cell(row.get("increment")),
            _escape_cell(row["text"]),
            _escape_cell(row["criticality"]),
            _escape_cell(row["moc"]),
            _escape_cell(row["status"]),
            _escape_cell(vb),
            _escape_cell(row["result"]),
        ]
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines) + "\n"


def _gate_findings(data: dict, junit_results: Optional[Dict[str, str]]) -> list:
    """The verification gate: every live requirement is verified, waived, or
    verified through its children (spec section 7).

    The waiver rule is duplicated from se_check._is_settled rather than
    imported: se_trace has never imported se_check, and reversing that
    dependency to share four lines would couple the tracer to the validator.
    If the rule changes, it changes in both places.

    A requirement whose verified_by is non-empty but whose matrix result is
    UNKNOWN (no --results given, or the linked test's name is absent from the
    results that were given) is also an error, checked alongside FAIL and
    before the NESTED/status checks: the requirement claims test evidence
    that nothing confirms actually ran, and status: verified must not be
    enough to launder that past the gate. A requirement with no verified_by
    at all (moc: analysis/inspection/demonstration, or a decomposed parent)
    never produces UNKNOWN, so this never fires for a project with no test
    evidence to confirm in the first place."""
    findings = []
    decomposed = _decomposed_ids(data)
    rows = {row["id"]: row for row in build_matrix_rows(data, junit_results)}
    for r in data.get("requirements", []):
        rid = se_lib.str_id(r)
        if rid is None or r.get("status") == "retired":
            continue
        waiver = r.get("waiver")
        if isinstance(waiver, str) and waiver.strip():
            continue
        row = rows.get(rid, {})
        result = row.get("result")
        if result == "FAIL":
            findings.append(se_lib.Finding("ERROR", "gate_failed", rid,
                             "a test linked to this requirement failed"))
            continue
        if result == "UNKNOWN" and row.get("verified_by"):
            findings.append(se_lib.Finding("ERROR", "gate_unknown", rid,
                             "requirement has verified_by test evidence, but the "
                             "results do not confirm any linked test ran"))
            continue
        if rid in decomposed and result == "NESTED":
            continue
        if r.get("status") != "verified":
            findings.append(se_lib.Finding("ERROR", "gate_unverified", rid,
                             f"status is '{r.get('status')}', not 'verified', and no "
                             f"waiver is recorded"))
    return findings


def generate_trace_findings(data: dict, test_defs: List[TestDef],
                             unknown_refs: List[Tuple[str, str, int]],
                             strict: bool = False) -> list:
    """spec section 3 rules 6 and 7: unknown-ID annotations (ERROR), tests with
    no VERIFIES annotation (WARNING unless --strict), moc: test requirements
    with no linked test *excluding decomposed parents* (WARNING unless
    --strict), and requirements with no downstream trace at all — no children
    and empty verified_by — flagged 'undetailed' (WARNING, always — see the
    module docstring for why --strict does not elevate it).

    A decomposed parent is excluded from the untested-requirement warning for
    the same reason it renders NESTED in the matrix: it is verified through its
    children, so it has no test of its own by design and warning about one
    would put a permanent floor under a properly decomposed tree.

    `data` must already reflect the post-scan verified_by state."""
    findings = []
    # Spec section 3 rule 7: these two are WARNING during development, because
    # tests are written progressively and failing every intermediate run would
    # make the checker something to switch off. --strict is the final gate,
    # where the same facts are blocking.
    level = "ERROR" if strict else "WARNING"
    decomposed = _decomposed_ids(data)
    for rid, file, line in unknown_refs:
        findings.append(se_lib.Finding("ERROR", "trace_unknown_id", rid,
                         f"VERIFIES annotation at {file}:{line} references nonexistent requirement ID"))
    for t in test_defs:
        if not t.req_ids:
            findings.append(se_lib.Finding(level, "trace_missing_annotation", None,
                             f"test '{t.name}' in {t.file}:{t.line} has no VERIFIES annotation"))
    for r in data.get("requirements", []):
        rid = se_lib.str_id(r)
        if rid is None:
            continue
        if (r.get("moc") == "test" and not r.get("verified_by")
                and rid not in decomposed and r.get("status") != "retired"):
            findings.append(se_lib.Finding(level, "trace_untested_req", rid,
                             "requirement has moc: test but no linked test"))
    ids_with_children = decomposed
    for r in data.get("requirements", []):
        rid = se_lib.str_id(r)
        if rid is None or r.get("status") == "retired":
            continue
        if rid not in ids_with_children and not r.get("verified_by"):
            findings.append(se_lib.Finding("WARNING", "trace_undetailed", rid,
                             "requirement has no downstream trace (no children, no verified_by)"))
    return findings


def parse_junit(xml_path: str) -> Dict[str, str]:
    """Parse a JUnit XML file into {testcase name attribute: 'pass'|'fail'}.
    A testcase is 'fail' if it has a <failure> or <error> child, else 'pass'."""
    tree = ET.parse(xml_path)
    root = tree.getroot()
    results: Dict[str, str] = {}
    for tc in root.iter("testcase"):
        name = tc.get("name")
        if name is None:
            continue
        failed = tc.find("failure") is not None or tc.find("error") is not None
        results[name] = "fail" if failed else "pass"
    return results


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="se_trace.py")
    parser.add_argument("se_dir", help="path to the project's se/ directory")
    parser.add_argument("--tests", default=None,
                         help="directory to scan for VERIFIES-annotated tests (omit before any tests exist)")
    parser.add_argument("--results", default=None, help="optional JUnit XML results file")
    parser.add_argument("--strict", action="store_true",
                         help="the final verification gate: unverified requirements, "
                              "failing linked tests and unannotated tests become errors")
    args = parser.parse_args(argv)

    req_path = os.path.join(args.se_dir, "requirements.yaml")
    try:
        data = se_lib.load_requirements_yaml(req_path)
    except se_lib.SeYamlError as exc:
        print(f"ERROR: {exc}")
        return 2

    schema_findings = se_lib.validate_schema(data)
    if any(f.level == "ERROR" for f in schema_findings):
        for f in schema_findings:
            print(f.format())
        return 1

    # Without --tests there is nothing to link against: keep the existing
    # verified_by links and only refresh the generated views. Rewriting them
    # from an empty scan would silently erase every test link.
    test_defs = scan_tests(args.tests) if args.tests else []
    verified_by_map, unknown_refs = build_verified_by(data, test_defs)
    if args.tests:
        updated = apply_verified_by(data, verified_by_map)
        se_lib.atomic_write_yaml(req_path, updated)
    else:
        updated = data

    generated_dir = os.path.join(args.se_dir, "generated")
    os.makedirs(generated_dir, exist_ok=True)

    hashes = compute_req_hashes(updated)
    se_lib.atomic_write_text(os.path.join(generated_dir, "req_hashes.json"),
                              json.dumps(hashes, indent=2, sort_keys=True))

    junit_results = parse_junit(args.results) if args.results else None
    rows = build_matrix_rows(updated, junit_results)
    se_lib.atomic_write_text(os.path.join(generated_dir, "matrix.md"), render_matrix_md(rows))

    findings = generate_trace_findings(updated, test_defs, unknown_refs,
                                        strict=args.strict)
    if args.strict:
        findings.extend(_gate_findings(updated, junit_results))
    for f in findings:
        print(f.format())
    if any(f.level == "ERROR" for f in findings):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
