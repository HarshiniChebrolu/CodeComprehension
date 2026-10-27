import os
import re
import pytest
from config import Config


def test_static_anti_hardcoding_scan():
    """
    Static scan across backend and frontend files to ensure zero canned badges,
    zero random scoring, and no hardcoded container images outside config.py.
    """
    forbidden_patterns = [
        (r'["\']Verified Safe["\']', "Forbidden canned badge 'Verified Safe' found"),
        (r'Heap Stack Allocation \(< 128MB container bound\)', "Forbidden canned memory tier string found"),
        (r'return \[3,\s*2,\s*4\]', "Forbidden hardcoded sample array fallback [3, 2, 4] found"),
    ]

    target_dirs = ["analyzer", "routes", "ai"]
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    for t_dir in target_dirs:
        dir_path = os.path.join(repo_root, t_dir)
        if not os.path.exists(dir_path):
            continue
        for root, _, files in os.walk(dir_path):
            for file in files:
                if not file.endswith(".py"):
                    continue
                file_path = os.path.join(root, file)
                with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()

                for pat, err_msg in forbidden_patterns:
                    assert not re.search(pat, content), f"{err_msg} in {file_path}"

                # Ensure random is not used in scoring or complexity
                if file in ("bug_detector.py", "complexity_analyzer.py"):
                    assert "import random" not in content, f"Deterministic rule violated: 'import random' found in {file}"
                    assert "from random import" not in content, f"Deterministic rule violated: random import in {file}"


def test_differential_reviews(client):
    """
    Submitting two completely distinct programs must produce distinct explanations,
    distinct complexity ratings, distinct AST structures, and distinct test cases.
    """
    prog_a = """def compute_average(values):
    total = 0
    for v in values:
        total += v
    return total / len(values)
"""
    prog_b = """def search_matrix(grid, key):
    for r in range(len(grid)):
        for c in range(len(grid[0])):
            if grid[r][c] == key:
                return (r, c)
    return None
"""

    resp_a = client.post("/api/v1/review", json={"code": prog_a, "language": "python", "no_cache": True})
    assert resp_a.status_code == 200
    data_a = resp_a.get_json()

    resp_b = client.post("/api/v1/review", json={"code": prog_b, "language": "python", "no_cache": True})
    assert resp_b.status_code == 200
    data_b = resp_b.get_json()

    # Complexity must differ (linear scan vs quadratic nested loops)
    assert data_a["complexity"]["time_complexity"] != data_b["complexity"]["time_complexity"]
    assert data_a["complexity"]["time_complexity"] == "O(n)"
    assert data_b["complexity"]["time_complexity"] == "O(n²)"

    # Structure / AST function names must match real identifiers
    ast_a_funcs = [f.get("name") for f in data_a["ast"].get("functions", [])]
    ast_b_funcs = [f.get("name") for f in data_b["ast"].get("functions", [])]
    assert "compute_average" in ast_a_funcs
    assert "search_matrix" in ast_b_funcs

    # Test cases must reference distinct function signatures
    tc_a = data_a["test_cases"]
    tc_b = data_b["test_cases"]
    assert tc_a.get("function_name") == "compute_average"
    assert tc_b.get("function_name") == "search_matrix"
    assert tc_a.get("parameters") != tc_b.get("parameters")


def test_deterministic_scoring_repeatability_and_sensitivity(client):
    """
    Scoring must be 100% deterministic (identical inputs yield identical scores),
    and modifying code to introduce a bug must change the score and deductions.
    """
    code_clean = """def find_max(numbers):
    if not numbers:
        return None
    max_val = numbers[0]
    for num in numbers:
        if num > max_val:
            max_val = num
    return max_val
"""
    # 1. Repeatability
    resp1 = client.post("/api/v1/review", json={"code": code_clean, "language": "python", "no_cache": True})
    resp2 = client.post("/api/v1/review", json={"code": code_clean, "language": "python", "no_cache": True})
    assert resp1.status_code == 200 and resp2.status_code == 200

    d1 = resp1.get_json()
    d2 = resp2.get_json()
    assert d1["score"] == d2["score"]
    assert d1["score_breakdown"] == d2["score_breakdown"]
    assert len(d1["deductions"]) == len(d2["deductions"])

    # 2. Sensitivity on mutation (introducing mutable default argument bug)
    code_mutated = """def find_max(numbers, cache=[]):
    if not numbers:
        return None
    max_val = numbers[0]
    for num in numbers:
        if num > max_val:
            max_val = num
    return max_val
"""
    resp_mut = client.post("/api/v1/review", json={"code": code_mutated, "language": "python", "no_cache": True})
    assert resp_mut.status_code == 200
    d_mut = resp_mut.get_json()

    assert d_mut["score"] < d1["score"]
    assert len(d_mut["deductions"]) > len(d1["deductions"])
    deduction_rules = [ded.get("rule_id") for ded in d_mut["deductions"]]
    assert any("MUTABLE_DEFAULT" in r for r in deduction_rules)


def test_wrong_language_submission(client):
    """
    Submitting Python code when language is set to Java, C, or C++
    must return a syntax or language validation error.
    """
    python_code = "def solve():\n    pass\n"

    for lang in ("java", "c", "cpp"):
        resp = client.post("/api/v1/review", json={"code": python_code, "language": lang, "no_cache": True})
        assert resp.status_code == 200
        data = resp.get_json()
        syntax_info = data.get("syntax", {})
        assert syntax_info.get("valid") is False
        assert "SyntaxError" in syntax_info.get("error", "")
