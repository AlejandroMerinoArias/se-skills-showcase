"""se_check.py - validates se/requirements.yaml against the se-skills data model
(spec section 3) and manages the suspect cascade (spec section 3, rule 5).

Usage:
    python se_check.py <se-dir>
    python se_check.py <se-dir> --mark-suspect <REQ-ID> [<REQ-ID> ...]
    python se_check.py <se-dir> --route [--record] [--ack-stall]
    python se_check.py <se-dir> --changed
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
from datetime import datetime, timezone
from typing import List, Optional, Tuple

import se_items
import se_lib
import se_route
import se_size


def check_duplicate_ids(data: dict) -> list:
    """Flag requirement IDs that appear more than once."""
    findings = []
    counts: dict = {}
    for r in data.get("requirements", []):
        rid = se_lib.str_id(r)
        if rid is None:
            continue
        counts[rid] = counts.get(rid, 0) + 1
    for rid, count in counts.items():
        if count > 1:
            findings.append(se_lib.Finding("ERROR", "check_duplicate_ids", rid,
                             f"duplicate ID: appears {count} times"))
    return findings


def check_orphans_and_cycles(data: dict) -> list:
    """Parent-exists, no-cycles, and orphan (non-top-level w/o parent) checks.

    A requirement is top-level iff parent is null AND its ID's level-prefix
    equals meta.levels[0] (levels store literal ID prefixes, top-to-bottom)."""
    findings = []
    levels = data.get("meta", {}).get("levels", [])
    top_level = levels[0] if levels else None
    reqs = data.get("requirements", [])
    # Wrong-typed ids and parents are reported by validate_schema; here they
    # are skipped rather than hashed, so a bad field is a finding and not a
    # traceback.
    by_id = {se_lib.str_id(r): r for r in reqs if se_lib.str_id(r) is not None}

    for r in reqs:
        rid = se_lib.str_id(r)
        if rid is None:
            continue
        raw_parent = r.get("parent")
        if raw_parent is not None and not isinstance(raw_parent, str):
            continue
        parent = raw_parent
        if parent is not None and parent not in by_id:
            findings.append(se_lib.Finding("ERROR", "check_orphans_and_cycles", rid,
                             f"parent '{parent}' does not exist"))
        if parent is None and se_lib.level_prefix(rid) != top_level:
            findings.append(se_lib.Finding("ERROR", "check_orphans_and_cycles", rid,
                             "non-top-level requirement has no parent (orphan)"))

    reported_cycle_ids = set()
    for r in reqs:
        rid = se_lib.str_id(r)
        if rid is None or rid in reported_cycle_ids:
            continue
        seen = []
        current = rid
        while current is not None:
            if current in seen:
                cycle_ids = seen[seen.index(current):]
                reported_cycle_ids.update(cycle_ids)
                findings.append(se_lib.Finding("ERROR", "check_orphans_and_cycles", rid,
                                 f"parent cycle detected: {' -> '.join(cycle_ids + [current])}"))
                break
            seen.append(current)
            current_req = by_id.get(current)
            current = se_lib.str_parent(current_req) if current_req else None

    return findings


def check_derived_rationale(data: dict) -> list:
    """category: derived requires a non-empty rationale (ARP4754B rule)."""
    findings = []
    for r in data.get("requirements", []):
        if r.get("category") == "derived":
            rationale = r.get("rationale")
            if not rationale or not str(rationale).strip():
                findings.append(se_lib.Finding("ERROR", "check_derived_rationale", r.get("id"),
                                 "category 'derived' requires a non-empty rationale"))
    return findings


FORBIDDEN_WORDS = [
    "user-friendly", "fast", "quick", "rapid", "adequate", "appropriate",
    "satisfactory", "minimize", "maximize", "etc.", "support",
    "high fidelity", "fault tolerant", "adaptable",
]

_FORBIDDEN_PATTERNS = [
    (w, re.compile(r"(?<![A-Za-z])" + re.escape(w) + r"(?![A-Za-z])", re.IGNORECASE))
    for w in FORBIDDEN_WORDS
]


def check_forbidden_words(data: dict) -> list:
    """Lint requirement text for vague/unverifiable words (course Chapter 3 list)."""
    findings = []
    for r in data.get("requirements", []):
        text = r.get("text")
        if not isinstance(text, str):
            continue  # a wrong-typed 'text' is validate_schema's finding, not a regex crash
        for word, pattern in _FORBIDDEN_PATTERNS:
            if pattern.search(text):
                findings.append(se_lib.Finding("WARNING", "check_forbidden_words", r.get("id"),
                                 f"forbidden word/phrase '{word}' found in text"))
    return findings


EVIDENCE_SUBDIR = se_lib.EVIDENCE_SUBDIR
_resolve_evidence = se_lib.resolve_evidence


def check_moc_evidence(data: dict, se_dir: str) -> list:
    """moc: analysis|inspection|demonstration at status: verified requires
    verified_by to reference an existing evidence file under se/evidence/
    (path relative to se_dir).

    These three plus check_test_moc_verified's `test` are the whole of
    se_lib.MOC_ENUM, and the partition is deliberate: every member of the
    enum is covered by one check or the other, so no MoC value can reach
    status: verified with nothing behind it. `demonstration` was missing here
    until the final branch review, and because nothing else covered it and
    _gate_findings renders an evidence-less non-test row UNVERIFIED (neither
    FAIL nor UNKNOWN nor NESTED), a demonstration project with no evidence at
    all passed se_check.py, se_trace.py --strict, and --route as `complete`.
    If MOC_ENUM ever gains a fifth member, it belongs in one of these two
    checks before it is legal in a file."""
    findings = []
    for r in data.get("requirements", []):
        if r.get("moc") in ("analysis", "inspection", "demonstration") and r.get("status") == "verified":
            verified_by = r.get("verified_by") or []
            if not verified_by:
                findings.append(se_lib.Finding("ERROR", "check_moc_evidence", r.get("id"),
                                 f"moc '{r.get('moc')}' at status 'verified' requires a verified_by evidence reference"))
                continue
            if not isinstance(verified_by, list):
                continue  # validate_schema reports the wrong type; do not join it
            for entry in verified_by:
                if not isinstance(entry, str):
                    continue  # likewise: os.path.join would raise on a non-str entry
                evidence_path = _resolve_evidence(se_dir, entry)
                if evidence_path is None:
                    findings.append(se_lib.Finding("ERROR", "check_moc_evidence", r.get("id"),
                                     f"evidence reference '{entry}' resolves outside {os.path.join(se_dir, EVIDENCE_SUBDIR)}"))
                    continue
                if not os.path.isfile(evidence_path):
                    findings.append(se_lib.Finding("ERROR", "check_moc_evidence", r.get("id"),
                                     f"evidence file '{entry}' referenced in verified_by does not exist under {se_dir}"))
    return findings


def check_test_moc_verified(data: dict) -> list:
    """moc: test at status: verified requires at least one linked test in
    verified_by — the symmetric counterpart of check_moc_evidence, which
    enforces the same for analysis, inspection and demonstration. Between
    them the two checks cover every member of se_lib.MOC_ENUM.

    Whether those tests PASS is deliberately not checked here: se_check.py
    never reads test results. se_trace.py --results is that gate, via the
    matrix's PASS/FAIL column."""
    findings = []
    for r in data.get("requirements", []):
        if r.get("moc") == "test" and r.get("status") == "verified":
            if not (r.get("verified_by") or []):
                findings.append(se_lib.Finding("ERROR", "check_test_moc_verified", r.get("id"),
                                 "moc 'test' at status 'verified' requires at least one linked test in verified_by"))
    return findings


def check_allocation(data: dict) -> list:
    """Allocation completeness: who is responsible for building each requirement.

    The two directions are deliberately asymmetric.

    A `validated` requirement with no `allocated_to` is a **WARNING**. It is a
    legal intermediate state — exactly what a project looks like after
    se:requirements-validation and before se:architecture has run — so it is
    reported without failing the run. An ERROR here would fail a state the
    pipeline is designed to pass through.

    A `retired` requirement with a non-null `allocated_to` is an **ERROR**. It
    is wrong in every phase: a retired requirement was struck, and allocating
    it makes a module responsible for building something nobody agreed to
    build, then puts that row in architecture.md for the plan to read.

    Deliberately silent on `draft`: requirements are unallocated by definition
    before architecture runs, and the derived children se:architecture writes
    enter at `draft` too. Covering those inside that phase is what
    se-architecture's Step 2 completeness command is for."""
    findings = []
    for r in data.get("requirements", []):
        if not isinstance(r, dict):
            continue
        status = r.get("status")
        allocated = r.get("allocated_to")
        if status == "validated" and not allocated:
            findings.append(se_lib.Finding("WARNING", "check_allocation", se_lib.str_id(r),
                             "status 'validated' but allocated_to is empty: "
                             "no module has been made responsible for building it"))
        elif status == "retired" and allocated:
            findings.append(se_lib.Finding("ERROR", "check_allocation", se_lib.str_id(r),
                             f"status 'retired' must not be allocated to a module "
                             f"(allocated_to: {allocated!r})"))
    return findings


# The router lives in se_route.py; these names stay importable from here
# because skills and tests address them as se_check.*.
ROUTE_STATES = se_route.ROUTE_STATES
_is_settled = se_route.is_settled
compute_state = se_route.compute_state


def run_all_checks(data: dict, se_dir: str) -> list:
    """Run schema validation plus every non-writing check from spec section 3:
    duplicate IDs, orphans and cycles, derived rationale, the forbidden-word
    lint, MoC evidence, test-MoC linkage, and allocation completeness.

    The suspect cascade is not here because it is the one check that *writes*:
    main() runs it separately so the write stays visible at the call site."""
    findings = []
    findings.extend(se_lib.validate_schema(data))
    findings.extend(check_duplicate_ids(data))
    findings.extend(check_orphans_and_cycles(data))
    findings.extend(check_derived_rationale(data))
    findings.extend(check_forbidden_words(data))
    findings.extend(check_moc_evidence(data, se_dir))
    findings.extend(check_test_moc_verified(data))
    findings.extend(check_allocation(data))
    return findings


def run_v2_checks(data: dict, se_dir: str, cfg: Optional[dict],
                  items: list, increments: Optional[dict]) -> list:
    """The v2 checks: open items, open values, the customer-question budget,
    increments (full mode only) and BLOAT."""
    req_ids = {se_lib.str_id(r) for r in data.get("requirements", [])
               if se_lib.str_id(r) is not None}
    findings = []
    findings.extend(se_items.validate_items(items, req_ids, se_dir))
    findings.extend(se_items.check_open_values(data, items))
    findings.extend(se_items.check_question_budget(items, cfg))
    if increments is not None and (cfg or {}).get("mode") == "full":
        findings.extend(se_items.validate_increments(increments, data))
    limits = se_lib.effective_size_limits(cfg)
    findings.extend(se_size.check_rationale_length(data, limits))
    findings.extend(se_size.check_artifact_sizes(se_dir, limits))
    return findings


def changed_requirements(data: dict, se_dir: str) -> List[str]:
    """Live requirement IDs a review round must look at: text changed since the
    last se_trace snapshot, absent from it, or marked suspect. With no
    snapshot at all, every live requirement is new."""
    hashes_path = os.path.join(se_dir, "generated", "req_hashes.json")
    old_hashes = {}
    if os.path.isfile(hashes_path):
        with open(hashes_path, "r", encoding="utf-8") as f:
            old_hashes = json.load(f)
    changed = []
    for r in data.get("requirements", []):
        rid = se_lib.str_id(r)
        if rid is None or r.get("status") == "retired":
            continue
        text = r.get("text")
        new_hash = hashlib.sha256((text if isinstance(text, str) else "").encode("utf-8")).hexdigest()
        if old_hashes.get(rid) != new_hash or r.get("suspect") is True:
            changed.append(rid)
    return changed


def _print_findings(findings) -> None:
    for f in findings:
        print(f.format())


def _collect_descendants(by_id: dict, root_id: str) -> list:
    children_map: dict = {}
    for rid, r in by_id.items():
        parent = se_lib.str_parent(r)
        if parent is not None:
            children_map.setdefault(parent, []).append(rid)
    descendants = []
    stack = list(children_map.get(root_id, []))
    while stack:
        cid = stack.pop()
        descendants.append(cid)
        stack.extend(children_map.get(cid, []))
    return descendants


def check_suspect_cascade(data: dict, se_dir: str):
    """Compare each requirement's current text hash against the
    se/generated/req_hashes.json snapshot written by se_trace.py. If changed
    and the requirement has children or verified_by links, mark the entire
    downstream subtree suspect: true in the YAML (the one check that writes).
    Returns (findings, data, changed)."""
    hashes_path = os.path.join(se_dir, "generated", "req_hashes.json")
    if not os.path.isfile(hashes_path):
        return [], data, False

    with open(hashes_path, "r", encoding="utf-8") as f:
        old_hashes = json.load(f)

    findings = []
    by_id = {se_lib.str_id(r): r for r in data.get("requirements", [])
             if se_lib.str_id(r) is not None}
    changed = False

    for rid, req in by_id.items():
        old_hash = old_hashes.get(rid)
        text = req.get("text")
        new_hash = hashlib.sha256((text if isinstance(text, str) else "").encode("utf-8")).hexdigest()
        if old_hash is not None and old_hash != new_hash:
            subtree = _collect_descendants(by_id, rid)
            has_children = bool(subtree)
            has_verified_by = bool(req.get("verified_by"))
            if has_children or has_verified_by:
                for cid in subtree:
                    if not by_id[cid].get("suspect"):
                        by_id[cid]["suspect"] = True
                        changed = True
                        findings.append(se_lib.Finding(
                            "WARNING", "check_suspect_cascade", cid,
                            f"marked suspect: upstream requirement '{rid}' text changed"))
                findings.append(se_lib.Finding(
                    "WARNING", "check_suspect_cascade", rid,
                    "text changed since last se_trace snapshot; downstream subtree marked suspect"))

    return findings, data, changed


def mark_suspects(data: dict, req_ids: List[str]):
    """Explicit cascade for several requirements at once: mark each and its
    entire downstream subtree suspect: true. All IDs are checked before any is
    marked, so an unknown ID changes nothing. Returns (data, marked IDs in
    first-seen order)."""
    by_id = {se_lib.str_id(r): r for r in data.get("requirements", [])
             if se_lib.str_id(r) is not None}
    missing = [rid for rid in req_ids if rid not in by_id]
    if missing:
        raise KeyError(f"requirement(s) not found: {', '.join(missing)}")
    marked: List[str] = []
    for req_id in req_ids:
        for rid in [req_id] + _collect_descendants(by_id, req_id):
            if rid not in marked:
                marked.append(rid)
                by_id[rid]["suspect"] = True
    return data, marked


def mark_suspect(data: dict, req_id: str):
    """Single-ID form of mark_suspects. Returns (data, subtree_including_req_id)."""
    known = {se_lib.str_id(r) for r in data.get("requirements", [])}
    if req_id not in known:
        raise KeyError(f"requirement '{req_id}' not found")
    return mark_suspects(data, [req_id])


def _load_v2(se_dir: str):
    """(items, increments); raises SeYamlError on a malformed file."""
    return se_items.load_items(se_dir), se_items.load_increments(se_dir)


def _route(se_dir: str, record: bool = False, ack_stall: bool = False) -> int:
    """--route: print where this project is, and exit 0.

    Never writes the artifacts. With --record it appends one dispatch record
    to generated/route-log.jsonl; with --ack-stall it first appends an
    acknowledgement, which resets the stall detector."""
    config_path = os.path.join(se_dir, se_lib.CONFIG_FILENAME)
    if not os.path.isfile(config_path):
        state, reason = compute_state(None, None, [])
        print(f"state: {state}")
        print("mode: -")
        print("increment: -")
        print(f"reason: {reason}")
        return 0

    try:
        cfg = se_lib.load_config_yaml(config_path)
        data = se_lib.load_requirements_yaml(os.path.join(se_dir, "requirements.yaml"))
        items, increments = _load_v2(se_dir)
    except se_lib.SeYamlError as exc:
        print(f"ERROR: {exc}")
        return 2

    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    if ack_stall:
        se_route.append_route_record(se_dir, {"kind": "ack", "time": now})

    findings = list(se_lib.validate_config(cfg))
    findings.extend(run_all_checks(data, se_dir))
    findings.extend(run_v2_checks(data, se_dir, cfg, items, increments))
    base_state, base_reason = compute_state(data, cfg, findings, items, increments)

    active = se_items.active_increment(increments) if cfg.get("mode") == "full" else None
    # Dispatches before the first increment (and all of a lite project) share
    # one budget under the key "setup".
    scope_key = active.get("id") if active else "setup"
    fp = se_route.fingerprint(se_dir)
    budget = se_lib.effective_budgets(cfg)["dispatches_per_increment"]
    state, reason = se_route.apply_stall(base_state, base_reason,
                                         se_route.read_route_log(se_dir),
                                         fp, scope_key, budget)
    if record and se_route.is_dispatch(state):
        se_route.append_route_record(se_dir, {"kind": "dispatch", "state": base_state,
                                              "fingerprint": fp, "increment": scope_key,
                                              "time": now})
    print(f"state: {state}")
    print(f"mode: {cfg.get('mode', '-')}")
    print(f"increment: {active.get('id') if active else '-'}")
    print(f"reason: {reason}")
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="se_check.py")
    parser.add_argument("se_dir", help="path to the project's se/ directory")
    parser.add_argument("--mark-suspect", dest="mark_suspect", nargs="+", default=None,
                         help="explicitly cascade-mark one or more requirement IDs and their subtrees as suspect")
    parser.add_argument("--route", action="store_true",
                         help="print the project's pipeline state and exit 0")
    parser.add_argument("--record", action="store_true",
                         help="with --route: append this routing decision to generated/route-log.jsonl")
    parser.add_argument("--ack-stall", dest="ack_stall", action="store_true",
                         help="with --route: record the user's decision to continue past a stall")
    parser.add_argument("--changed", action="store_true",
                         help="print the live requirement IDs changed since the last se_trace snapshot, and exit 0")
    args = parser.parse_args(argv)

    modes = [flag for flag, on in (("--route", args.route), ("--mark-suspect", args.mark_suspect),
                                   ("--changed", args.changed)) if on]
    if len(modes) > 1:
        parser.error(f"{' and '.join(modes)} cannot be combined")
    if (args.record or args.ack_stall) and not args.route:
        parser.error("--record and --ack-stall only apply with --route")

    if args.route:
        return _route(args.se_dir, record=args.record, ack_stall=args.ack_stall)

    req_path = os.path.join(args.se_dir, "requirements.yaml")
    try:
        data = se_lib.load_requirements_yaml(req_path)
    except se_lib.SeYamlError as exc:
        print(f"ERROR: {exc}")
        return 2

    if args.changed:
        for rid in changed_requirements(data, args.se_dir):
            print(rid)
        return 0

    config_path = os.path.join(args.se_dir, se_lib.CONFIG_FILENAME)
    config_findings = []
    cfg = None
    if os.path.isfile(config_path):
        try:
            cfg = se_lib.load_config_yaml(config_path)
        except se_lib.SeYamlError as exc:
            print(f"ERROR: {exc}")
            return 2
        config_findings = se_lib.validate_config(cfg)

    if args.mark_suspect:
        # A writing path must not run on a file whose schema does not validate.
        # The defensive guards in mark_suspect skip requirements whose 'id' is
        # missing or not a string, which is right for a *reporting* check but
        # turns this path into a silent success: it would write requirements.yaml
        # back to disk at exit 0 with an unrelated malformed requirement never
        # reported. Validate first, refuse the write, honour the exit code.
        #
        # Deliberately schema only. An invalid *config* is still not this path's
        # business — --mark-suspect is a targeted write, not a validation run,
        # and config findings it will not act on would be noise.
        schema_findings = se_lib.validate_schema(data)
        if any(f.level == "ERROR" for f in schema_findings):
            _print_findings(schema_findings)
            return 1
        try:
            data, subtree = mark_suspects(data, args.mark_suspect)
        except KeyError as exc:
            print(f"ERROR: {exc}")
            return 2
        se_lib.atomic_write_yaml(req_path, data)
        print(f"marked suspect: {', '.join(subtree)}")
        return 0

    try:
        items, increments = _load_v2(args.se_dir)
    except se_lib.SeYamlError as exc:
        print(f"ERROR: {exc}")
        return 2

    findings = list(config_findings)
    findings.extend(run_all_checks(data, args.se_dir))
    findings.extend(run_v2_checks(data, args.se_dir, cfg, items, increments))
    cascade_findings, data, changed = check_suspect_cascade(data, args.se_dir)
    findings.extend(cascade_findings)

    # The cascade is the other writing path, and it refuses on the same
    # grounds. A cascade computed over a file whose ids and parents did not all
    # parse is a *half-computed* cascade — it silently skipped the requirements
    # it could not read — so persisting its conclusion would write a subtree
    # marking that was never fully determined.
    #
    # The gate is on schema errors specifically, not on any ERROR. A dangling
    # parent or a missing evidence file is an ERROR, but every id and parent in
    # the file is still well-formed, so the cascade's computation is complete
    # and correct and its result should persist.
    schema_invalid = any(f.level == "ERROR" and f.check == "validate_schema"
                          for f in findings)
    if changed and not schema_invalid:
        se_lib.atomic_write_yaml(req_path, data)

    _print_findings(findings)
    if any(f.level == "ERROR" for f in findings):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
