"""BLOAT checks (v2 design spec section 6.4). v1's artifacts grew to 1.8 MB and
every cold agent paid to read them; these WARNINGs make growth visible early."""

from __future__ import annotations

import os
from typing import Any, Dict, List

import se_lib

_EXCLUDED_DIRS = {"generated", se_lib.EVIDENCE_SUBDIR}


def check_rationale_length(data: Dict[str, Any], limits: Dict[str, int]) -> List[se_lib.Finding]:
    cap = limits["rationale_chars"]
    findings = []
    for r in data.get("requirements", []):
        if not isinstance(r, dict):
            continue
        rationale = r.get("rationale")
        if isinstance(rationale, str) and len(rationale) > cap:
            findings.append(se_lib.Finding("WARNING", "check_bloat", se_lib.str_id(r),
                             f"BLOAT: rationale is {len(rationale)} characters (limit {cap}); "
                             f"move the reasoning to a D-nn decision or an evidence file "
                             f"and reference it"))
    return findings


def _dir_bytes(se_dir: str) -> int:
    total = 0
    top = os.path.abspath(se_dir)
    for root, dirs, files in os.walk(se_dir):
        if os.path.abspath(root) == top:
            dirs[:] = [d for d in dirs if d not in _EXCLUDED_DIRS]
        for name in files:
            total += os.path.getsize(os.path.join(root, name))
    return total


def check_artifact_sizes(se_dir: str, limits: Dict[str, int]) -> List[se_lib.Finding]:
    findings = []
    for filename, key in (("CONOPS.md", "conops_kb"), ("architecture.md", "architecture_kb")):
        path = os.path.join(se_dir, filename)
        if os.path.isfile(path):
            size = os.path.getsize(path)
            if size > limits[key] * 1024:
                findings.append(se_lib.Finding("WARNING", "check_bloat", None,
                                 f"BLOAT: {filename} is {size // 1024} KB (limit {limits[key]} KB)"))
    total = _dir_bytes(se_dir)
    if total > limits["se_dir_kb"] * 1024:
        findings.append(se_lib.Finding("WARNING", "check_bloat", None,
                         f"BLOAT: se/ is {total // 1024} KB excluding generated/ and evidence/ "
                         f"(limit {limits['se_dir_kb']} KB)"))
    return findings
