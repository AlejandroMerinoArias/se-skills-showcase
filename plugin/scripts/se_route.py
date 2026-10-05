"""The v2 router (design spec section 8) and stall detector (section 5.6).

compute_state is pure: everything it knows comes from the parsed artifacts
and the findings the caller already computed, so the state is re-derived from
files every time and survives any crash. The stall detector reads one extra
input, the route log, and apply_stall is pure over it; only the CLI appends."""

from __future__ import annotations

import hashlib
import json
import os
from typing import Any, Dict, List, Optional, Tuple

import se_items
import se_lib

ROUTE_STATES = [
    "greenfield",
    "blocked_invalid",
    "stalled",
    "suspects_pending",
    "items_unapplied",
    "awaiting_customer",
    "no_requirements",
    "draft_top_level",
    "no_increment_plan",
    "experiments_open",
    "increment_design",
    "ready_to_build",
    "implementing",
    "increment_unverified",
    "final_validation",
    "complete",
]

ROUTE_LOG = os.path.join("generated", "route-log.jsonl")
# States that never stall: nothing is being dispatched in them. Waiting for
# the customer hands work to the user, not to a phase agent.
_UNSTALLABLE = {"greenfield", "blocked_invalid", "awaiting_customer", "complete"}


def is_dispatch(state: str) -> bool:
    """Whether routing to this state sends work to a phase agent, and so
    counts as a dispatch for the stall detector."""
    return state not in _UNSTALLABLE and state != "stalled"


def is_settled(req: dict) -> bool:
    """Verified, or carrying an explicit user-approved waiver."""
    if req.get("status") == "verified":
        return True
    waiver = req.get("waiver")
    return isinstance(waiver, str) and bool(waiver.strip())


def _ids(entries) -> str:
    return ", ".join(sorted(str(e.get("id")) for e in entries))


def compute_state(data: Optional[dict], cfg: Optional[dict],
                  findings: List[se_lib.Finding],
                  items: Optional[List[Any]] = None,
                  increments: Optional[Dict[str, Any]] = None) -> Tuple[str, str]:
    """Where is this project? Returns (state, reason); first match wins.

    'stalled' is not produced here: it depends on the route log, and
    apply_stall layers it over this result."""
    if cfg is None:
        return ("greenfield", "no se-config.yaml: the project has not been tailored")

    errors = [f for f in findings if f.level == "ERROR"]
    if errors:
        return ("blocked_invalid",
                f"{len(errors)} ERROR-level finding(s): the artifacts cannot be "
                f"routed on until they validate")

    reqs = [r for r in (data or {}).get("requirements", []) if isinstance(r, dict)]
    live = [r for r in reqs if r.get("status") != "retired"]

    suspects = sorted(s for s in (se_lib.str_id(r) for r in live if r.get("suspect") is True) if s)
    if suspects:
        return ("suspects_pending",
                f"{len(suspects)} requirement(s) marked suspect: {', '.join(suspects)}")

    items = [i for i in (items or []) if isinstance(i, dict)]
    answered = [i for i in items if i.get("status") == "answered"]
    if answered:
        owners = ", ".join(sorted(f"{i.get('id')} (owner {i.get('owner')})" for i in answered))
        return ("items_unapplied", f"{len(answered)} item(s) answered but not applied: {owners}")

    open_q = [i for i in items if i.get("kind") == "customer_question" and i.get("status") == "open"]
    if open_q:
        return ("awaiting_customer",
                f"{len(open_q)} open customer question(s) for the next gate: {_ids(open_q)}")

    if not live:
        return ("no_requirements", "requirements.yaml holds no live requirements")

    levels = ((data or {}).get("meta") or {}).get("levels") or []
    top = levels[0] if levels else None
    top_drafts = [r for r in live if r.get("status") == "draft"
                  and se_lib.level_prefix(se_lib.str_id(r)) == top]
    if top_drafts:
        return ("draft_top_level",
                f"{len(top_drafts)} requirement(s) at status draft on the top level ({top})")

    full = cfg.get("mode") == "full"
    if full:
        if increments is None:
            return ("no_increment_plan",
                    "the top level is validated and there is no increments.yaml yet")
        active = se_items.active_increment(increments)
        if active is None:
            if not increments.get("final_validation"):
                return ("final_validation", "every increment is verified or failed")
            return ("complete", "final validation is recorded in increments.yaml")
        active_id = active.get("id")
        scope = [r for r in live if r.get("increment") == active_id]
        label = f"increment {active_id}"
    else:
        # Lite mode: the whole requirement set is one implicit increment.
        active_id = None
        scope = live
        label = "the project"

    scope_ids = {se_lib.str_id(r) for r in scope}
    blocking = []
    for i in items:
        if i.get("kind") != "experiment" or i.get("status") != "open":
            continue
        blocks = i.get("blocks") if isinstance(i.get("blocks"), list) else []
        if (active_id is not None and i.get("owner") == active_id) or scope_ids.intersection(blocks):
            blocking.append(i)
    if blocking:
        return ("experiments_open",
                f"{len(blocking)} open experiment(s) block {label}: {_ids(blocking)}")

    drafts = [r for r in scope if r.get("status") == "draft"]
    unallocated = [r for r in scope if full and r.get("status") == "validated"
                   and not r.get("allocated_to")]
    if drafts or unallocated:
        return ("increment_design",
                f"{label}: {len(drafts)} draft and {len(unallocated)} unallocated requirement(s)")

    # A decomposed requirement (one with live children) is met through its
    # children: it is never built or verified itself, so only its children
    # count as work. se_trace already renders such a row NESTED.
    parents = {se_lib.str_parent(r) for r in live} - {None}
    unsettled = [r for r in scope
                 if se_lib.str_id(r) not in parents and not is_settled(r)]
    if not unsettled:
        if full:
            return ("increment_unverified",
                    f"every requirement of {label} is verified or waived; "
                    f"close {active_id} in increments.yaml")
        return ("complete", f"all {len(live)} live requirement(s) are verified or waived")

    statuses = {r.get("status") for r in unsettled}
    to_build = sum(1 for r in unsettled if r.get("status") == "validated")
    if "implemented" in statuses and "validated" in statuses:
        return ("implementing", f"{label}: {to_build} requirement(s) still to implement")
    if "validated" in statuses:
        return ("ready_to_build", f"{label}: {to_build} validated requirement(s) to build")
    return ("increment_unverified",
            f"{label}: {len(unsettled)} implemented requirement(s) not yet verified")


def fingerprint(se_dir: str) -> str:
    """One hash over the three files whose change counts as progress."""
    h = hashlib.sha256()
    for name in ("requirements.yaml", se_items.ITEMS_FILENAME, se_items.INCREMENTS_FILENAME):
        h.update(name.encode("utf-8") + b"\0")
        path = os.path.join(se_dir, name)
        if os.path.isfile(path):
            with open(path, "rb") as f:
                h.update(f.read())
        h.update(b"\0")
    return h.hexdigest()


def read_route_log(se_dir: str) -> List[dict]:
    """Records from generated/route-log.jsonl, oldest first. The log is a
    generated file; an unparseable line is skipped, never fatal."""
    path = os.path.join(se_dir, ROUTE_LOG)
    if not os.path.isfile(path):
        return []
    records = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(rec, dict):
                records.append(rec)
    return records


def append_route_record(se_dir: str, record: dict) -> None:
    path = os.path.join(se_dir, ROUTE_LOG)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "a", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps(record, sort_keys=True) + "\n")


def apply_stall(state: str, reason: str, history: List[dict], fp: str,
                increment_id: Optional[str], dispatch_budget: int) -> Tuple[str, str]:
    """Layer 'stalled' over compute_state's result.

    Only dispatch records after the most recent acknowledgement count, so a
    user's "continue" at a stall gate resets both tests."""
    if state in _UNSTALLABLE:
        return state, reason
    since: List[dict] = []
    for rec in reversed(history):
        if rec.get("kind") == "ack":
            break
        if rec.get("kind") == "dispatch":
            since.append(rec)
    since.reverse()

    last_two = since[-2:]
    if len(last_two) == 2 and all(r.get("state") == state and r.get("fingerprint") == fp
                                  for r in last_two):
        return ("stalled",
                f"no progress: state '{state}' with unchanged artifacts across the last "
                f"two routed dispatches")
    if increment_id is not None:
        used = sum(1 for r in since if r.get("increment") == increment_id)
        if used >= dispatch_budget:
            return ("stalled",
                    f"increment {increment_id} has used {used} of {dispatch_budget} dispatches")
    return state, reason
