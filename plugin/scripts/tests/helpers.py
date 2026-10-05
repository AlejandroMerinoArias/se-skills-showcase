"""Shared synthetic-fixture builders for the se_check.py / se_trace.py test suite."""


def make_requirement(**overrides):
    req = {
        "id": "SYS-F-001",
        "text": "When the trigger occurs, the system shall respond within 100 ms.",
        "category": "functional",
        "criticality": "B",
        "rationale": None,
        "source": None,
        "parent": None,
        "allocated_to": None,
        "moc": "test",
        "verified_by": [],
        "status": "draft",
        "waiver": None,
        "suspect": False,
        "target": None,
        "threshold": None,
        "history": [{"date": "2026-07-25", "change": "created", "why": "initial capture"}],
    }
    req.update(overrides)
    return req


def make_data(requirements, levels=None):
    return {
        "meta": {
            "project": "demo-project",
            "mode": "lite",
            "levels": list(levels) if levels else ["SYS"],
        },
        "requirements": requirements,
    }
