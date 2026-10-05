"""se/open-items.yaml and se/increments.yaml: loading and validation
(v2 design spec sections 4 and 6.2).

Every unknown, pending question and design decision lives in open-items.yaml,
typed so the router can tell who owns it. increments.yaml orders the work into
slices. Both files are optional: absence means "none yet"."""

from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

import se_lib

ITEMS_FILENAME = "open-items.yaml"
INCREMENTS_FILENAME = "increments.yaml"

ITEM_KIND_BY_PREFIX = {"Q": "customer_question", "E": "experiment", "D": "design_decision"}
ITEM_STATUS_ENUM = {"open", "answered", "applied", "closed", "accepted_risk"}
# An open value stops blocking only once its item is closed or accepted as a risk.
RESOLVED_ITEM_STATUSES = {"closed", "accepted_risk"}
NEEDS_ANSWER_STATUSES = {"answered", "applied", "closed", "accepted_risk"}

INCREMENT_STATUS_ENUM = {"planned", "active", "verified", "failed"}
DONE_INCREMENT_STATUSES = {"verified", "failed"}


def _nonempty_str(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def load_items(se_dir: str) -> List[Any]:
    """The 'items' list of open-items.yaml, or [] when the file is absent or
    empty. Raises SeYamlError on malformed YAML or a wrong-shaped file."""
    path = os.path.join(se_dir, ITEMS_FILENAME)
    if not os.path.isfile(path):
        return []
    data = se_lib.load_yaml_mapping(path, allow_empty=True)
    items = data.get("items")
    if items is None:
        return []
    if not isinstance(items, list):
        raise se_lib.SeYamlError(f"{path}: 'items' must be a list")
    return items


def validate_items(items: List[Any], req_ids: set, se_dir: str) -> List[se_lib.Finding]:
    findings: List[se_lib.Finding] = []

    def err(item_id, message):
        findings.append(se_lib.Finding("ERROR", "check_open_items", item_id, message))

    seen = set()
    for idx, item in enumerate(items):
        if not isinstance(item, dict):
            err(None, f"open item at index {idx} is not a mapping")
            continue
        raw_id = item.get("id")
        iid = raw_id if isinstance(raw_id, str) else None
        if iid is None or not se_lib.ITEM_ID_PATTERN.match(iid):
            err(iid, f"item id {raw_id!r} must look like Q-01, E-01 or D-01")
        elif iid in seen:
            err(iid, "duplicate item id")
        else:
            seen.add(iid)
            expected = ITEM_KIND_BY_PREFIX[iid[0]]
            if item.get("kind") != expected:
                err(iid, f"id prefix '{iid[0]}' requires kind '{expected}', got {item.get('kind')!r}")

        if item.get("kind") not in ITEM_KIND_BY_PREFIX.values():
            err(iid, f"'kind' value {item.get('kind')!r} not in {sorted(ITEM_KIND_BY_PREFIX.values())}")
        status = item.get("status")
        if status not in ITEM_STATUS_ENUM:
            err(iid, f"'status' value {status!r} not in {sorted(ITEM_STATUS_ENUM)}")
        if not _nonempty_str(item.get("text")):
            err(iid, "'text' must be a non-empty string")

        owner = item.get("owner")
        if not (owner == "setup" or (isinstance(owner, str) and se_lib.INCREMENT_ID_PATTERN.match(owner))):
            err(iid, f"'owner' must be 'setup' or an increment ID like 'I0', got {owner!r}")

        blocks = item.get("blocks")
        if blocks is None:
            blocks = []
        if not isinstance(blocks, list) or not all(isinstance(b, str) for b in blocks):
            err(iid, "'blocks' must be a list of requirement IDs")
        else:
            for rid in blocks:
                if rid not in req_ids:
                    err(iid, f"'blocks' references unknown requirement '{rid}'")

        if status in NEEDS_ANSWER_STATUSES and not _nonempty_str(item.get("answer")):
            err(iid, f"status '{status}' requires a one-line 'answer'")

        evidence = item.get("evidence")
        if evidence is not None:
            if not isinstance(evidence, str):
                err(iid, "'evidence' must be a path string under se/evidence/ or null")
            else:
                resolved = se_lib.resolve_evidence(se_dir, evidence)
                if resolved is None:
                    err(iid, f"evidence '{evidence}' resolves outside se/{se_lib.EVIDENCE_SUBDIR}/")
                elif not os.path.isfile(resolved):
                    err(iid, f"evidence file '{evidence}' does not exist")
    return findings


def check_open_values(data: Dict[str, Any], items: List[Any]) -> List[se_lib.Finding]:
    """A requirement may be validated with an open value, but may not reach
    implemented or verified until every item it references is resolved."""
    findings: List[se_lib.Finding] = []
    by_id = {i["id"]: i for i in items if isinstance(i, dict) and isinstance(i.get("id"), str)}
    for r in data.get("requirements", []):
        if not isinstance(r, dict):
            continue
        refs = r.get("open_items") or []
        if not isinstance(refs, list):
            continue  # validate_schema reports the wrong type
        rid = se_lib.str_id(r)
        for ref in refs:
            if not isinstance(ref, str):
                continue
            item = by_id.get(ref)
            if item is None:
                findings.append(se_lib.Finding("ERROR", "check_open_values", rid,
                                 f"open_items references unknown item '{ref}'"))
                continue
            if r.get("status") in ("implemented", "verified") and item.get("status") not in RESOLVED_ITEM_STATUSES:
                findings.append(se_lib.Finding("ERROR", "check_open_values", rid,
                                 f"status '{r.get('status')}' but open item '{ref}' is "
                                 f"'{item.get('status')}', not closed or accepted_risk"))
    return findings


def check_question_budget(items: List[Any], cfg: Optional[Dict[str, Any]]) -> List[se_lib.Finding]:
    """Customer-question caps are WARNINGs: exceeding one is allowed only with a
    justification the reviewer checks, so the script flags, it does not block."""
    budgets = se_lib.effective_budgets(cfg)
    questions = [i for i in items if isinstance(i, dict) and i.get("kind") == "customer_question"]
    findings: List[se_lib.Finding] = []
    total_cap = budgets["customer_questions_total"]
    if len(questions) > total_cap:
        findings.append(se_lib.Finding("WARNING", "check_question_budget", None,
                         f"{len(questions)} customer questions exceed customer_questions_total "
                         f"({total_cap}); each extra one must show why it is not an experiment "
                         f"or a design decision"))
    open_q = [i for i in questions if i.get("status") == "open"]
    gate_cap = budgets["customer_questions_per_gate"]
    if len(open_q) > gate_cap:
        findings.append(se_lib.Finding("WARNING", "check_question_budget", None,
                         f"{len(open_q)} open customer questions exceed customer_questions_per_gate "
                         f"({gate_cap}) for the next gate batch"))
    return findings


def load_increments(se_dir: str) -> Optional[Dict[str, Any]]:
    """The parsed increments.yaml, or None when the file is absent or empty.
    Raises SeYamlError on malformed YAML or a missing 'increments' list."""
    path = os.path.join(se_dir, INCREMENTS_FILENAME)
    if not os.path.isfile(path):
        return None
    data = se_lib.load_yaml_mapping(path, allow_empty=True)
    if not data:
        return None
    if not isinstance(data.get("increments"), list):
        raise se_lib.SeYamlError(f"{path} is missing an 'increments' list")
    return data


def active_increment(increments: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """The first increment whose status is not verified or failed, else None."""
    if not increments:
        return None
    for inc in increments.get("increments", []):
        if isinstance(inc, dict) and inc.get("status") not in DONE_INCREMENT_STATUSES:
            return inc
    return None


def validate_increments(increments: Dict[str, Any], data: Dict[str, Any]) -> List[se_lib.Finding]:
    findings: List[se_lib.Finding] = []

    def err(ref, message):
        findings.append(se_lib.Finding("ERROR", "check_increments", ref, message))

    reqs = [r for r in data.get("requirements", []) if isinstance(r, dict)]
    by_id = {se_lib.str_id(r): r for r in reqs if se_lib.str_id(r) is not None}
    levels = (data.get("meta") or {}).get("levels") or []
    top = levels[0] if levels else None

    inc_ids = set()
    assigned: Dict[str, str] = {}
    for idx, inc in enumerate(increments.get("increments", [])):
        if not isinstance(inc, dict):
            err(None, f"increment at index {idx} is not a mapping")
            continue
        raw_id = inc.get("id")
        iid = raw_id if isinstance(raw_id, str) else None
        if iid is None or not se_lib.INCREMENT_ID_PATTERN.match(iid):
            err(iid, f"increment id {raw_id!r} must look like I0, I1, ...")
        elif iid in inc_ids:
            err(iid, "duplicate increment id")
        else:
            inc_ids.add(iid)
        if inc.get("status") not in INCREMENT_STATUS_ENUM:
            err(iid, f"'status' value {inc.get('status')!r} not in {sorted(INCREMENT_STATUS_ENUM)}")
        if not _nonempty_str(inc.get("goal")):
            err(iid, "'goal' must be a non-empty string")
        if inc.get("status") == "failed" and not _nonempty_str(inc.get("failure_cause")):
            err(iid, "status 'failed' requires a 'failure_cause'")
        listed = inc.get("requirements")
        if listed is None:
            listed = []
        if not isinstance(listed, list) or not all(isinstance(x, str) for x in listed):
            err(iid, "'requirements' must be a list of requirement IDs")
            continue
        for rid in listed:
            if rid not in by_id:
                err(iid, f"assigns unknown requirement '{rid}'")
            elif se_lib.level_prefix(rid) != top:
                err(iid, f"'{rid}' is not top-level; only top-level requirements are assigned here")
            elif rid in assigned:
                err(iid, f"'{rid}' is already assigned to {assigned[rid]}")
            else:
                assigned[rid] = iid

    for r in reqs:
        rid = se_lib.str_id(r)
        if rid is None or r.get("status") == "retired":
            continue
        inc = r.get("increment")
        if inc is None:
            err(rid, "increments.yaml exists, so every live requirement needs an 'increment'")
        elif inc not in inc_ids:
            err(rid, f"'increment' names unknown increment '{inc}'")
        elif se_lib.level_prefix(rid) == top and assigned.get(rid) != inc:
            err(rid, f"'increment' is '{inc}' but increments.yaml assigns it to "
                     f"{assigned.get(rid) or 'no increment'}")

    final = increments.get("final_validation")
    if final is not None and not (isinstance(final, dict) and _nonempty_str(final.get("result"))):
        err(None, "'final_validation' must be null or a mapping with a non-empty 'result'")
    return findings
