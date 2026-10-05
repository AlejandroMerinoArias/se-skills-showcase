import os

README = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "README.md",
)


def test_readme_documents_both_clis():
    with open(README, encoding="utf-8") as f:
        content = f.read()
    for needle in [
        "se_check.py", "se_trace.py", "requirements.yaml",
        "--mark-suspect", "--tests", "--results",
        "requirements-dev.txt", "meta.levels", "open-items.yaml", "increments.yaml",
        "--record", "--ack-stall", "--changed", "ruamel.yaml",
    ]:
        assert needle in content, f"README.md is missing '{needle}'"
