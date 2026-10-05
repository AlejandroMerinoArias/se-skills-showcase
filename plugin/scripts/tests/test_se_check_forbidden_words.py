import se_check
from helpers import make_requirement, make_data


def test_forbidden_words_flagged_as_warnings():
    data = make_data([make_requirement(
        id="SYS-F-001",
        text="The system shall provide fast and adequate response to user input.")])
    findings = se_check.check_forbidden_words(data)
    words_found = {f.message.split("'")[1] for f in findings}
    assert words_found == {"fast", "adequate"}
    assert all(f.level == "WARNING" for f in findings)


def test_clean_text_has_no_findings():
    data = make_data([make_requirement(
        id="SYS-F-001",
        text="When the trigger occurs, the system shall respond within 100 ms.")])
    assert se_check.check_forbidden_words(data) == []


def test_etc_and_phrase_detected():
    data = make_data([make_requirement(
        id="SYS-F-001",
        text="The system shall be fault tolerant against sensor noise, glitches, etc.")])
    findings = se_check.check_forbidden_words(data)
    words_found = {f.message.split("'")[1] for f in findings}
    assert "fault tolerant" in words_found
    assert "etc." in words_found


def test_forbidden_word_does_not_match_inside_a_longer_word():
    data = {"meta": {"project": "p", "mode": "lite", "levels": ["SYS"]},
            "requirements": [{"id": "SYS-F-001",
                              "text": "The system shall log supportive feedback entries."}]}
    assert se_check.check_forbidden_words(data) == []


def test_forbidden_word_matches_when_hyphen_adjacent():
    data = {"meta": {"project": "p", "mode": "lite", "levels": ["SYS"]},
            "requirements": [{"id": "SYS-F-001",
                              "text": "The system shall be user-friendly."}]}
    findings = se_check.check_forbidden_words(data)
    assert [f.check for f in findings] == ["check_forbidden_words"]


def test_repeated_forbidden_word_reports_once_per_requirement():
    data = {"meta": {"project": "p", "mode": "lite", "levels": ["SYS"]},
            "requirements": [{"id": "SYS-F-001",
                              "text": "The system shall be fast, and the report shall be fast."}]}
    findings = se_check.check_forbidden_words(data)
    assert len(findings) == 1


def test_two_distinct_forbidden_words_report_separately():
    data = {"meta": {"project": "p", "mode": "lite", "levels": ["SYS"]},
            "requirements": [{"id": "SYS-F-001",
                              "text": "The system shall minimize latency and be quick."}]}
    findings = se_check.check_forbidden_words(data)
    assert len(findings) == 2
