import os

import se_trace

FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures", "scan_samples")


def test_scan_tests_python_annotation():
    defs = se_trace.scan_tests(FIXTURES)
    by_name = {d.name: d for d in defs}
    assert by_name["test_start_triggers_capture"].req_ids == ["SYS-F-001"]
    assert by_name["test_start_triggers_capture"].file == "sample_test.py"
    assert by_name["test_start_triggers_capture"].line == 2
    assert by_name["test_no_annotation_here"].req_ids == []


def test_scan_tests_cpp_annotation():
    defs = se_trace.scan_tests(FIXTURES)
    by_name = {d.name: d for d in defs}
    assert by_name["CaptureModule.StartsWithinBudget"].req_ids == ["SYS-F-002", "SYS-F-003"]
    assert by_name["CaptureFixture.HandlesRetry"].req_ids == []


def test_scan_tests_returns_testdef_instances():
    defs = se_trace.scan_tests(FIXTURES)
    assert all(isinstance(d, se_trace.TestDef) for d in defs)
    assert len(defs) == 4
