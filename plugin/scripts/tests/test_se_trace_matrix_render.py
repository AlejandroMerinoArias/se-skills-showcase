"""Markdown cell escaping in the generated matrix, and the VERIFIES scanner's
lookahead boundary (both deferred minors from the Plan A final review)."""

import re

import se_trace


def _unescaped_pipes(line: str) -> int:
    """Count only the pipes that act as column separators. An escaped '\\|' is
    cell content, and counting it as a delimiter is how a naive assertion here
    passes before the fix and fails after it."""
    return len(re.findall(r"(?<!\\)\|", line))


def _row(**overrides):
    row = {
        "id": "SYS-F-001",
        "text": "the system shall do a thing",
        "criticality": "A",
        "moc": "test",
        "status": "draft",
        "verified_by": [],
        "result": "UNVERIFIED",
    }
    row.update(overrides)
    return row


def test_pipe_in_text_is_escaped_and_column_count_preserved():
    md = se_trace.render_matrix_md([_row(text="hover | land within 200 ms")])
    header, _sep, body = md.splitlines()[:3]
    assert _unescaped_pipes(body) == _unescaped_pipes(header) == 9
    assert r"hover \| land within 200 ms" in body


def test_pipe_in_verified_by_is_escaped():
    md = se_trace.render_matrix_md([_row(verified_by=["a|b.py::test_x"])])
    body = md.splitlines()[2]
    assert r"a\|b.py::test_x" in body
    assert _unescaped_pipes(body) == 9


def test_newline_in_text_does_not_break_the_row_into_several_lines():
    """A '\\n' inside requirement text produced a multi-line block where a
    valid table row needs exactly one line, breaking the same column structure
    the pipe escape exists to protect. truncate() does not help: the newline
    can sit well inside the first 60 characters."""
    md = se_trace.render_matrix_md([
        _row(text="the system shall do a thing\nand then another thing")])
    assert len(md.splitlines()) == 3, md
    body = md.splitlines()[2]
    assert _unescaped_pipes(body) == 9
    assert "do a thing and then another thing" in body


def test_carriage_return_in_text_does_not_survive_into_the_row():
    md = se_trace.render_matrix_md([_row(text="first\r\nsecond")])
    assert len(md.splitlines()) == 3, md
    assert "\r" not in md


def test_newline_in_verified_by_does_not_break_the_row():
    md = se_trace.render_matrix_md([_row(verified_by=["a.py::test_x\ninjected"])])
    assert len(md.splitlines()) == 3, md
    assert _unescaped_pipes(md.splitlines()[2]) == 9


def test_none_cell_renders_empty_not_the_word_none():
    md = se_trace.render_matrix_md([_row(criticality=None)])
    body = md.splitlines()[2]
    assert "None" not in body


def test_annotation_attaches_at_exactly_max_lookahead(tmp_path):
    gap = "\n" * (se_trace.MAX_LOOKAHEAD - 1)
    (tmp_path / "test_edge.py").write_text(
        "# VERIFIES: SYS-F-001\n" + gap + "def test_at_boundary():\n    pass\n",
        encoding="utf-8",
    )
    defs = se_trace.scan_tests(str(tmp_path))
    assert [d.req_ids for d in defs] == [["SYS-F-001"]]


def test_annotation_does_not_attach_one_line_past_max_lookahead(tmp_path):
    gap = "\n" * se_trace.MAX_LOOKAHEAD
    (tmp_path / "test_edge.py").write_text(
        "# VERIFIES: SYS-F-001\n" + gap + "def test_past_boundary():\n    pass\n",
        encoding="utf-8",
    )
    defs = se_trace.scan_tests(str(tmp_path))
    assert [d.req_ids for d in defs] == [[]]
