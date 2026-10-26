import pytest
from analyzer.syntax_analyzer import analyze_syntax
from analyzer.bug_detector import detect_bugs
from analyzer.complexity_analyzer import analyze_complexity
from analyzer.test_generator import generate_test_cases
from analyzer.optimizer import analyze_optimization
from analyzer.topology_3d import generate_3d_topology


def test_syntax_analyzer_valid_code():
    res = analyze_syntax("def foo():\n    return 42\n", "python")
    assert res["valid"] is True
    assert res["error"] is None


def test_syntax_analyzer_invalid_code():
    res = analyze_syntax("def foo(:\n    return 42\n", "python")
    assert res["valid"] is False
    assert res["error"] is not None
    assert "SyntaxError" in res["error"]
    assert res["line"] is not None


def test_bug_detector_two_sum():
    code = """def two_sum(nums, target):
    for i in range(len(nums)):
        for j in range(len(nums)):
            if nums[i] + nums[j] == target:
                return [i, j]
"""
    res = detect_bugs(code, "python")
    assert "issues" in res
    assert len(res["issues"]) > 0
    # Should detect the self-pairing bug (i == j)
    has_two_sum_issue = any("two_sum" in iss.get("rule_id", "") or "pair" in iss.get("problem", "").lower() for iss in res["issues"])
    assert has_two_sum_issue is True


def test_complexity_analyzer():
    code = """def bubble_sort(arr):
    n = len(arr)
    for i in range(n):
        for j in range(0, n - i - 1):
            if arr[j] > arr[j + 1]:
                arr[j], arr[j + 1] = arr[j + 1], arr[j]
"""
    res = analyze_complexity(code, "python")
    assert "time_complexity" in res
    assert "space_complexity" in res
    assert "O(n²)" in res["time_complexity"] or "O(n^2)" in res["time_complexity"]
    assert "reasoning" in res


def test_test_case_generator():
    code = """def multiply(x, y):
    return x * y
"""
    res = generate_test_cases(code, "python")
    assert "test_cases" in res
    assert len(res["test_cases"]) >= 3


def test_topology_generator():
    code = """def check(val):
    if val > 0:
        return True
    return False
"""
    ast_mock = {"nodes": [], "control_flow": []}
    comp_mock = {"time_complexity": "O(1)", "space_complexity": "O(1)"}
    topo = generate_3d_topology(code, "python", ast_mock, comp_mock)
    assert "nodes" in topo
    assert "edges" in topo
    assert "execution_steps" in topo
    assert len(topo["nodes"]) > 0
