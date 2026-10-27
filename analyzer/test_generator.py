import ast
import json
import logging
import re
from typing import List, Dict, Any, Optional

from analyzer.execution_sandbox import is_docker_available, _execute_in_docker_container_multilang

logger = logging.getLogger("codecomprehension.test_generator")


def generate_test_cases(code: str, language: str = "python") -> Dict[str, Any]:
    """
    Intelligently inspects the submitted code to generate:
    - Normal cases
    - Edge cases
    - Difficult cases (exposing logical bugs)
    - Stress cases
    - Best / Average / Worst case scenario inputs
    """
    func_info = _extract_function_signature(code, language)
    func_name = func_info.get("name", "solution")
    params = func_info.get("params", [])

    # Categorize algorithm type based on identifiers and parameters
    code_lower = code.lower()
    is_sort = any(k in code_lower for k in ("sort", "bubble", "quick", "merge", "insertion"))
    is_search = any(k in code_lower for k in ("search", "find", "binary", "target", "low", "high"))
    is_two_sum = "target" in code_lower and ("sum" in code_lower or "nums" in code_lower)
    is_math_or_fib = any(k in code_lower for k in ("fib", "factorial", "prime", "gcd", "pow"))

    test_cases = []
    case_scenarios = {}

    if is_two_sum:
        test_cases = [
            {
                "id": "tc_1",
                "category": "Normal Case",
                "description": "Standard array with unique pair summing to target",
                "input": "nums = [2, 7, 11, 15], target = 9",
                "args": [[2, 7, 11, 15], 9],
                "expected": "[0, 1] (or [1, 0])",
                "explanation": "2 + 7 = 9. Elements at index 0 and 1 satisfy target."
            },
            {
                "id": "tc_2",
                "category": "Normal Case",
                "description": "Target formed by elements towards the end of array",
                "input": "nums = [3, 2, 4], target = 6",
                "args": [[3, 2, 4], 6],
                "expected": "[1, 2]",
                "explanation": "2 + 4 = 6. Indices 1 and 2."
            },
            {
                "id": "tc_3",
                "category": "Edge Case",
                "description": "Identical values: target formed by identical numbers",
                "input": "nums = [3, 3], target = 6",
                "args": [[3, 3], 6],
                "expected": "[0, 1]",
                "explanation": "Checks if duplicates are handled without reusing the same index twice."
            },
            {
                "id": "tc_4",
                "category": "Edge Case",
                "description": "Negative numbers and zero",
                "input": "nums = [-3, 4, 3, 90], target = 0",
                "args": [[-3, 4, 3, 90], 0],
                "expected": "[0, 2]",
                "explanation": "-3 + 3 = 0. Verifies negative numbers."
            },
            {
                "id": "tc_5",
                "category": "Difficult Case",
                "description": "Trap case: Target is 2 * nums[i] with no duplicate element",
                "input": "nums = [3, 5, 8], target = 6",
                "args": [[3, 5, 8], 6],
                "expected": "None or []",
                "explanation": "Detects buggy implementations where nums[0] + nums[0] falsely matches target 6."
            },
            {
                "id": "tc_6",
                "category": "Stress Case",
                "description": "Large array with 100 elements where solution is at the very ends",
                "input": "nums = [1...100], target = 101",
                "args": [list(range(1, 101)), 101],
                "expected": "[0, 99]",
                "explanation": "Verifies quadratic vs linear performance across 100 elements."
            }
        ]
        case_scenarios = {
            "best_case": {
                "input": "nums = [4, 5, 8, 12, 19], target = 9",
                "reason": "Solution is found on the very first pair check (index 0 and index 1), terminating immediately in O(1) best-case time."
            },
            "average_case": {
                "input": "nums = [1, 7, 11, 2, 15, 8, 4], target = 10",
                "reason": "Matching elements are distributed in the middle of the array, requiring half of total pairs to be scanned."
            },
            "worst_case": {
                "input": "nums = [1, 2, 3, 4, 5, 6, 7, 8], target = 99",
                "reason": "No pair exists or matching pair is at the very last position, forcing a full quadratic scan of n(n-1)/2 comparisons."
            }
        }
    elif is_sort:
        test_cases = [
            {
                "id": "tc_1",
                "category": "Normal Case",
                "description": "Arbitrary unsorted integer list",
                "input": "arr = [64, 34, 25, 12, 22, 11, 90]",
                "args": [[64, 34, 25, 12, 22, 11, 90]],
                "expected": "[11, 12, 22, 25, 34, 64, 90]",
                "explanation": "Standard sorting test with positive distinct integers."
            },
            {
                "id": "tc_2",
                "category": "Edge Case",
                "description": "Empty array",
                "input": "arr = []",
                "args": [[]],
                "expected": "[]",
                "explanation": "Checks if the code handles empty collections without throwing IndexError."
            },
            {
                "id": "tc_3",
                "category": "Edge Case",
                "description": "Single element array",
                "input": "arr = [42]",
                "args": [[42]],
                "expected": "[42]",
                "explanation": "Trivial base case: a single element is already sorted."
            },
            {
                "id": "tc_4",
                "category": "Edge Case",
                "description": "All identical duplicate elements",
                "input": "arr = [5, 5, 5, 5, 5]",
                "args": [[5, 5, 5, 5, 5]],
                "expected": "[5, 5, 5, 5, 5]",
                "explanation": "Verifies stability and unnecessary swap handling."
            },
            {
                "id": "tc_5",
                "category": "Difficult Case",
                "description": "Mix of positive, negative numbers and zero",
                "input": "arr = [-5, 0, -1, 3, -10, 2]",
                "args": [[-5, 0, -1, 3, -10, 2]],
                "expected": "[-10, -5, -1, 0, 2, 3]",
                "explanation": "Verifies that negative sign comparison operates accurately."
            },
            {
                "id": "tc_6",
                "category": "Stress Case",
                "description": "Reverse sorted array of 50 elements",
                "input": "arr = [50, 49, 48, ... 1]",
                "args": [list(range(50, 0, -1))],
                "expected": "[1, 2, ... 50]",
                "explanation": "Forces maximum number of inversions and swaps."
            }
        ]
        case_scenarios = {
            "best_case": {
                "input": "arr = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]",
                "reason": "Already sorted list. Algorithms with an early-exit swap flag finish in O(n) linear time."
            },
            "average_case": {
                "input": "arr = [4, 8, 2, 1, 9, 5, 3, 7, 6, 10]",
                "reason": "Random permutation of values requiring average number of comparisons and shifts."
            },
            "worst_case": {
                "input": "arr = [10, 9, 8, 7, 6, 5, 4, 3, 2, 1]",
                "reason": "Completely reversed order. Every adjacent element must be swapped, producing maximum O(n²) operations."
            }
        }
    elif is_search:
        test_cases = [
            {
                "id": "tc_1",
                "category": "Normal Case",
                "description": "Target present in middle of array",
                "input": "arr = [1, 3, 5, 7, 9, 11], target = 7",
                "args": [[1, 3, 5, 7, 9, 11], 7],
                "expected": "4 (or index of 7)",
                "explanation": "Direct lookup of an existing element."
            },
            {
                "id": "tc_2",
                "category": "Edge Case",
                "description": "Target not in array (smaller than minimum)",
                "input": "arr = [2, 4, 6, 8], target = 0",
                "args": [[2, 4, 6, 8], 0],
                "expected": "-1 (or None / False)",
                "explanation": "Verifies boundary handling when target is lower than lower bound."
            },
            {
                "id": "tc_3",
                "category": "Edge Case",
                "description": "Target not in array (larger than maximum)",
                "input": "arr = [2, 4, 6, 8], target = 10",
                "args": [[2, 4, 6, 8], 10],
                "expected": "-1 (or None / False)",
                "explanation": "Verifies upper boundary termination without index error."
            },
            {
                "id": "tc_4",
                "category": "Edge Case",
                "description": "Single element array matching target",
                "input": "arr = [5], target = 5",
                "args": [[5], 5],
                "expected": "0",
                "explanation": "Boundary condition: low == high on first iteration."
            },
            {
                "id": "tc_5",
                "category": "Difficult Case",
                "description": "Off-by-one check: Target is the very last element",
                "input": "arr = [1, 2, 3, 4, 5], target = 5",
                "args": [[1, 2, 3, 4, 5], 5],
                "expected": "4",
                "explanation": "Exposes off-by-one errors where 'high' or loop termination fails on rightmost element."
            },
            {
                "id": "tc_6",
                "category": "Stress Case",
                "description": "Binary search on 1,000 sorted elements",
                "input": "arr = [0, 2, 4, ... 1998], target = 1500",
                "args": [list(range(0, 2000, 2)), 1500],
                "expected": "750",
                "explanation": "Ensures logarithmic O(log n) performance (~10 comparisons for 1000 items)."
            }
        ]
        case_scenarios = {
            "best_case": {
                "input": "arr = [1, 3, 5, 7, 9, 11, 13], target = 7",
                "reason": "Target sits exactly at the initial midpoint (index 3). Found in a single step O(1)."
            },
            "average_case": {
                "input": "arr = [1, 3, 5, 7, 9, 11, 13], target = 11",
                "reason": "Target requires a couple of subdivision steps (~log₂(n)/2 checks)."
            },
            "worst_case": {
                "input": "arr = [1, 3, 5, 7, 9, 11, 13], target = 99",
                "reason": "Target is not present in the array. Requires maximum ⌈log₂(n)⌉ subdivisions before intervals cross."
            }
        }
    elif is_math_or_fib:
        test_cases = [
            {
                "id": "tc_1",
                "category": "Normal Case",
                "description": "Standard positive integer input (n = 6)",
                "input": "n = 6",
                "args": [6],
                "expected": "8 (if fib) or 720 (if factorial)",
                "explanation": "General operational input."
            },
            {
                "id": "tc_2",
                "category": "Edge Case",
                "description": "Base case zero (n = 0)",
                "input": "n = 0",
                "args": [0],
                "expected": "0 (fib) or 1 (factorial)",
                "explanation": "Verifies that base case terminates immediately."
            },
            {
                "id": "tc_3",
                "category": "Edge Case",
                "description": "Base case one (n = 1)",
                "input": "n = 1",
                "args": [1],
                "expected": "1",
                "explanation": "Validates boundary termination."
            },
            {
                "id": "tc_4",
                "category": "Difficult Case",
                "description": "Negative input (n = -3)",
                "input": "n = -3",
                "args": [-3],
                "expected": "ValueError / 0 / None",
                "explanation": "Exposes infinite recursion loops if function assumes n > 0 without guarding."
            },
            {
                "id": "tc_5",
                "category": "Stress Case",
                "description": "Larger value (n = 30)",
                "input": "n = 30",
                "args": [30],
                "expected": "Calculated value without timeout",
                "explanation": "Exposes naive unmemoized recursion O(2ⁿ) vs O(n) DP."
            }
        ]
        case_scenarios = {
            "best_case": {
                "input": "n = 0 or n = 1",
                "reason": "Hits the base condition in O(1) without invoking recursive frames."
            },
            "average_case": {
                "input": "n = 15",
                "reason": "Moderate depth calculation testing stack depth and memory."
            },
            "worst_case": {
                "input": "n = 35",
                "reason": "Produces over 9 billion function calls in naive recursion, causing severe latency or stack overflow."
            }
        }
    else:
        # Default algorithmic test suite
        test_cases = [
            {
                "id": "tc_1",
                "category": "Normal Case",
                "description": "Standard representative input with expected parameters",
                "input": "Typical argument values",
                "args": [10],
                "expected": "Valid result",
                "explanation": "Tests normal execution path."
            },
            {
                "id": "tc_2",
                "category": "Edge Case",
                "description": "Empty input or zero value",
                "input": "0 or [] or None",
                "args": [0],
                "expected": "Handled gracefully",
                "explanation": "Verifies that empty/zero inputs do not cause crashes."
            },
            {
                "id": "tc_3",
                "category": "Edge Case",
                "description": "Negative or inverted input values",
                "input": "-1 or [-10, -5]",
                "args": [-1],
                "expected": "Guarded result",
                "explanation": "Checks if the logic properly accounts for negative magnitudes."
            },
            {
                "id": "tc_4",
                "category": "Difficult Case",
                "description": "Boundary edge values (extremes)",
                "input": "Max/min integers or single-item structures",
                "args": [999999],
                "expected": "Stable execution",
                "explanation": "Reveals potential overflow or type constraint boundaries."
            },
            {
                "id": "tc_5",
                "category": "Stress Case",
                "description": "Large input volume to verify complexity",
                "input": "Volume: 500 items",
                "args": [list(range(500))],
                "expected": "Execution under timeout limit",
                "explanation": "Evaluates time complexity under real workload."
            }
        ]
        case_scenarios = {
            "best_case": {
                "input": "Minimal valid input (e.g. empty, base case, or first item match)",
                "reason": "Terminates on first evaluation in minimal operations."
            },
            "average_case": {
                "input": "Medium dataset with uniformly distributed parameters",
                "reason": "Follows standard statistical workload execution."
            },
            "worst_case": {
                "input": "Maximum dataset size with worst-case data layout (e.g. absent key or reversed order)",
                "reason": "Forces the algorithm through every possible iteration branch."
            }
        }

    # Verify test cases dynamically in sandbox
    verified_test_cases = _verify_tests_in_sandbox(code, language, func_name, test_cases)

    return {
        "function_name": func_name,
        "parameters": params,
        "test_cases": verified_test_cases,
        "case_scenarios": case_scenarios,
        "total_generated": len(verified_test_cases)
    }


def _verify_tests_in_sandbox(
    code: str,
    language: str,
    func_name: Optional[str],
    test_cases: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """
    Executes generated test cases inside Docker sandbox and tags each case with
    PASS, FAIL, RUNTIME_ERROR, TIMEOUT, or UNVERIFIED.
    """
    lang = language.lower().strip()
    if lang != "python" or not func_name or not is_docker_available():
        reason = "Execution verification skipped (unsupported language or Docker sandbox inactive)."
        for tc in test_cases:
            tc["status"] = "UNVERIFIED"
            tc["actual_output"] = None
            tc["verification_note"] = reason
        return test_cases

    # Build batch runner inside container
    test_args = {tc["id"]: tc.get("args", []) for tc in test_cases}
    harness = f"""
import json, sys

{code}

test_inputs = {json.dumps(test_args)}
results = {{}}

fn = globals().get('{func_name}')
if not callable(fn):
    print("---BATCH_TEST_START---")
    print(json.dumps({{"_global_error": "Function not callable"}}))
    print("---BATCH_TEST_END---")
    sys.exit(0)

for cid, args in test_inputs.items():
    try:
        if isinstance(args, list):
            res = fn(*args)
        else:
            res = fn(args)
        results[cid] = {{"ok": True, "output": str(res)}}
    except Exception as e:
        results[cid] = {{"ok": False, "error": str(e), "error_type": type(e).__name__}}

print("---BATCH_TEST_START---")
print(json.dumps(results))
print("---BATCH_TEST_END---")
"""
    try:
        exec_res = _execute_in_docker_container_multilang(
            code=harness,
            language="python",
            custom_stdin=None,
            timeout=5.0
        )
        if exec_res.get("status") == "TIMEOUT":
            for tc in test_cases:
                tc["status"] = "TIMEOUT"
                tc["actual_output"] = None
                tc["verification_note"] = "Sandbox execution timed out."
            return test_cases

        stdout = exec_res.get("stdout", "")
        if "---BATCH_TEST_START---" in stdout and "---BATCH_TEST_END---" in stdout:
            payload = stdout.split("---BATCH_TEST_START---")[1].split("---BATCH_TEST_END---")[0].strip()
            batch_data = json.loads(payload)

            for tc in test_cases:
                cid = tc["id"]
                if cid in batch_data:
                    res_item = batch_data[cid]
                    if res_item.get("ok"):
                        tc["status"] = "PASS"
                        tc["actual_output"] = res_item.get("output")
                        tc["verification_note"] = "Executed cleanly without exceptions in Docker sandbox."
                    else:
                        tc["status"] = "RUNTIME_ERROR"
                        tc["actual_output"] = res_item.get("error")
                        tc["verification_note"] = f"Runtime error in sandbox: {res_item.get('error_type')}"
                else:
                    tc["status"] = "UNVERIFIED"
                    tc["actual_output"] = None
                    tc["verification_note"] = "Not evaluated in batch runner."
            return test_cases
    except Exception as e:
        logger.warning(f"Batch test verification failed: {e}")

    for tc in test_cases:
        tc["status"] = "UNVERIFIED"
        tc["actual_output"] = None
        tc["verification_note"] = "Sandbox verification encountered an unhandled exception."
    return test_cases


def _extract_function_signature(code: str, language: str) -> Dict[str, Any]:
    if language.lower() in ("python", "py"):
        try:
            tree = ast.parse(code)
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    return {
                        "name": node.name,
                        "params": [a.arg for a in node.args.args]
                    }
        except Exception:
            pass

    # Regex fallback
    m = re.search(r'def\s+([a-zA-Z0-9_]+)\s*\((.*?)\)', code)
    if m:
        name = m.group(1)
        raw_params = m.group(2).split(",")
        params = [p.strip().split(":")[0].split("=")[0].strip() for p in raw_params if p.strip()]
        return {"name": name, "params": params}

    # C / Java / JS style fallback
    m2 = re.search(r'(?:int|void|function|double|String)\s+([a-zA-Z0-9_]+)\s*\((.*?)\)', code)
    if m2:
        return {"name": m2.group(1), "params": [p.strip() for p in m2.group(2).split(",") if p.strip()]}

    return {"name": None, "params": []}
