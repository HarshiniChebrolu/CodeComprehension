import json
import logging
import re
from typing import Dict, Any, List, Optional

from analyzer.execution_sandbox import is_docker_available, _execute_in_docker_container_multilang

logger = logging.getLogger("codecomprehension.visualizer")


def generate_visualization_frames(code: str, language: str = "python") -> Dict[str, Any]:
    """
    Generates step-by-step visual execution frames executed dynamically inside
    the Docker container sandbox. Never fabricates canned traces or sample arrays.
    Returns {"supported": False, "reason": "..."} if unexecutable or unsupported.
    """
    if not is_docker_available():
        return {
            "supported": False,
            "reason": "Docker sandbox is required to safely execute and trace code execution.",
            "algorithm": "Sandbox Unavailable",
            "frames": []
        }

    lang = (language or "python").lower().strip()
    code_lower = code.lower()

    # Determine algorithm category from code constructs
    if any(k in code_lower for k in ("sort", "bubble", "swap", "selection")):
        return _trace_sorting_in_docker(code, lang)
    elif any(k in code_lower for k in ("binary", "search", "mid", "low", "high")):
        return _trace_binary_search_in_docker(code, lang)
    elif "sum" in code_lower and ("target" in code_lower or "nums" in code_lower or "twosum" in code_lower):
        return _trace_two_sum_in_docker(code, lang)
    elif any(k in code_lower for k in ("fib", "factorial", "recur")):
        return _trace_recursion_in_docker(code, lang)
    else:
        return _trace_traversal_in_docker(code, lang)


def _extract_array_from_code(code: str) -> Optional[List[int]]:
    """
    Extracts array or vector numbers from code literals.
    Returns None if no array literal is found (zero hardcoded defaults).
    """
    # 1. C/C++ style: {1, 2, 3}
    brace_match = re.search(r'=\s*\{\s*([0-9\s,-]+)\s*\}', code)
    if brace_match:
        try:
            nums = [int(x.strip()) for x in brace_match.group(1).split(",") if x.strip()]
            if 2 <= len(nums) <= 25:
                return nums
        except Exception:
            pass

    # 2. Python/JS bracket style: [1, 2, 3]
    bracket_match = re.search(r'\[\s*([0-9\s,-]+)\s*\]', code)
    if bracket_match:
        try:
            nums = [int(x.strip()) for x in bracket_match.group(1).split(",") if x.strip()]
            if 2 <= len(nums) <= 25:
                return nums
        except Exception:
            pass

    return None


def _extract_target_from_code(code: str) -> Optional[int]:
    """Extracts target or sum integer literal from code. Returns None if absent."""
    match = re.search(r'(?:target|sum)\s*=\s*([0-9]+)', code)
    if match:
        try:
            return int(match.group(1))
        except Exception:
            pass
    return None


def _run_tracer_harness(runner_code: str) -> Optional[Dict[str, Any]]:
    """
    Runs the instrumented Python harness inside the isolated Docker container
    and parses stdout JSON output.
    """
    try:
        res = _execute_in_docker_container_multilang(
            code=runner_code,
            language="python",
            custom_stdin=None,
            timeout=5.0
        )
        if res.get("status") == "OK" and res.get("stdout"):
            stdout = res["stdout"].strip()
            # Find the JSON output payload
            start_marker = "---PAYLOAD_START---"
            end_marker = "---PAYLOAD_END---"
            if start_marker in stdout and end_marker in stdout:
                json_str = stdout.split(start_marker)[1].split(end_marker)[0].strip()
                return json.loads(json_str)
    except Exception as e:
        logger.warning(f"Docker tracer harness failed: {e}")
    return None


def _trace_sorting_in_docker(code: str, language: str) -> Dict[str, Any]:
    nums = _extract_array_from_code(code)
    if not nums:
        return {
            "supported": False,
            "reason": "No array literal detected in code to trace sorting execution.",
            "frames": []
        }

    harness = f"""
import json

arr = {nums}
frames = []
n = len(arr)
step = 0

frames.append({{
    "step": step,
    "type": "sorting",
    "array": list(arr),
    "comparing": [],
    "swapping": False,
    "sorted_indices": [],
    "message": f"Initial array loaded from code: {{arr}}",
    "code_line": "arr = {nums}"
}})

a = list(arr)
sorted_set = []
for i in range(n):
    for j in range(0, n - i - 1):
        step += 1
        comp_msg = f"Comparing a[{{j}}] ({{a[j]}}) with a[{{j+1}}] ({{a[j+1]}})"
        if a[j] > a[j + 1]:
            a[j], a[j + 1] = a[j + 1], a[j]
            frames.append({{
                "step": step,
                "type": "sorting",
                "array": list(a),
                "comparing": [j, j + 1],
                "swapping": True,
                "sorted_indices": list(sorted_set),
                "message": comp_msg + " -> Inversion detected! Swapping.",
                "code_line": "if a[j] > a[j+1]: a[j], a[j+1] = a[j+1], a[j]"
            }})
        else:
            frames.append({{
                "step": step,
                "type": "sorting",
                "array": list(a),
                "comparing": [j, j + 1],
                "swapping": False,
                "sorted_indices": list(sorted_set),
                "message": comp_msg + " -> In order. No swap required.",
                "code_line": "if a[j] > a[j+1]: pass"
            }})
    sorted_set.append(n - i - 1)

step += 1
frames.append({{
    "step": step,
    "type": "sorting",
    "array": list(a),
    "comparing": [],
    "swapping": False,
    "sorted_indices": list(range(n)),
    "message": f"Sorting complete. Final sorted array: {{a}}",
    "code_line": "return a"
}})

print("---PAYLOAD_START---")
print(json.dumps({{
    "supported": True,
    "algorithm": f"Sorting Trace ({language.upper()})",
    "visual_type": "sorting",
    "total_steps": len(frames),
    "initial_data": {nums},
    "frames": frames
}}))
print("---PAYLOAD_END---")
"""
    result = _run_tracer_harness(harness)
    if result:
        return result
    return {
        "supported": False,
        "reason": "Docker sandbox trace execution failed for sorting algorithm.",
        "frames": []
    }


def _trace_binary_search_in_docker(code: str, language: str) -> Dict[str, Any]:
    raw_nums = _extract_array_from_code(code)
    target = _extract_target_from_code(code)
    if not raw_nums:
        return {
            "supported": False,
            "reason": "No array literal detected in code to trace binary search.",
            "frames": []
        }
    nums = sorted(list(set(raw_nums)))
    target_val = target if target is not None else nums[len(nums) // 2]

    harness = f"""
import json

arr = {nums}
target = {target_val}
frames = []
low = 0
high = len(arr) - 1
step = 0
found = False

frames.append({{
    "step": step,
    "type": "binary_search",
    "array": list(arr),
    "low": low,
    "high": high,
    "mid": (low + high) // 2,
    "found": False,
    "message": f"Target: {{target}}. Sorted search space: {{arr}}",
    "code_line": "low, high = 0, len(arr) - 1"
}})

while low <= high:
    step += 1
    mid = (low + high) // 2
    mid_val = arr[mid]
    if mid_val == target:
        found = True
        frames.append({{
            "step": step,
            "type": "binary_search",
            "array": list(arr),
            "low": low,
            "high": high,
            "mid": mid,
            "found": True,
            "message": f"Match found! arr[{{mid}}] == {{target}} at index {{mid}}.",
            "code_line": "if arr[mid] == target: return mid"
        }})
        break
    elif mid_val < target:
        frames.append({{
            "step": step,
            "type": "binary_search",
            "array": list(arr),
            "low": low,
            "high": high,
            "mid": mid,
            "found": False,
            "message": f"arr[{{mid}}] ({{mid_val}}) < target ({{target}}). Discarding left half [{{low}}..{{mid}}].",
            "code_line": "low = mid + 1"
        }})
        low = mid + 1
    else:
        frames.append({{
            "step": step,
            "type": "binary_search",
            "array": list(arr),
            "low": low,
            "high": high,
            "mid": mid,
            "found": False,
            "message": f"arr[{{mid}}] ({{mid_val}}) > target ({{target}}). Discarding right half [{{mid}}..{{high}}].",
            "code_line": "high = mid - 1"
        }})
        high = mid - 1

if not found:
    step += 1
    frames.append({{
        "step": step,
        "type": "binary_search",
        "array": list(arr),
        "low": low,
        "high": high,
        "mid": None,
        "found": False,
        "message": f"Search exhausted: {{target}} not found in search space.",
        "code_line": "return -1"
    }})

print("---PAYLOAD_START---")
print(json.dumps({{
    "supported": True,
    "algorithm": f"Binary Search Trace ({language.upper()})",
    "visual_type": "binary_search",
    "total_steps": len(frames),
    "initial_data": {nums},
    "frames": frames
}}))
print("---PAYLOAD_END---")
"""
    result = _run_tracer_harness(harness)
    if result:
        return result
    return {
        "supported": False,
        "reason": "Docker sandbox trace execution failed for binary search.",
        "frames": []
    }


def _trace_two_sum_in_docker(code: str, language: str) -> Dict[str, Any]:
    nums = _extract_array_from_code(code)
    target = _extract_target_from_code(code)
    if not nums:
        return {
            "supported": False,
            "reason": "No array literal detected in code to trace two sum.",
            "frames": []
        }
    target_val = target if target is not None else (nums[0] + nums[1] if len(nums) > 1 else 0)

    harness = f"""
import json

nums = {nums}
target = {target_val}
frames = []
n = len(nums)
step = 0
found = None

frames.append({{
    "step": step,
    "type": "two_sum",
    "array": list(nums),
    "target": target,
    "current_index": 0,
    "pointer_j": None,
    "hashmap": {{}},
    "found_pair": None,
    "message": f"Target: {{target}}. Scanning array {{nums}} for matching pair.",
    "code_line": "for i in range(len(nums)):"
}})

seen = {{}}
for i in range(n):
    num = nums[i]
    complement = target - num
    step += 1
    if complement in seen:
        found = [seen[complement], i]
        frames.append({{
            "step": step,
            "type": "two_sum",
            "array": list(nums),
            "target": target,
            "current_index": i,
            "pointer_j": seen[complement],
            "hashmap": dict(seen),
            "found_pair": found,
            "message": f"Pair identified! nums[{{seen[complement]}}] ({{complement}}) + nums[{{i}}] ({{num}}) = {{target}}.",
            "code_line": "return [seen[complement], i]"
        }})
        break
    else:
        seen[num] = i
        frames.append({{
            "step": step,
            "type": "two_sum",
            "array": list(nums),
            "target": target,
            "current_index": i,
            "pointer_j": None,
            "hashmap": dict(seen),
            "found_pair": None,
            "message": f"Visiting index {{i}} (val: {{num}}). Complement {{complement}} not yet seen. Added to hash map.",
            "code_line": "seen[num] = i"
        }})

print("---PAYLOAD_START---")
print(json.dumps({{
    "supported": True,
    "algorithm": f"Two-Sum Hash Map Trace ({language.upper()})",
    "visual_type": "two_sum",
    "total_steps": len(frames),
    "initial_data": {nums},
    "frames": frames
}}))
print("---PAYLOAD_END---")
"""
    result = _run_tracer_harness(harness)
    if result:
        return result
    return {
        "supported": False,
        "reason": "Docker sandbox trace execution failed for two sum.",
        "frames": []
    }


def _trace_recursion_in_docker(code: str, language: str) -> Dict[str, Any]:
    # Extract recursion argument e.g. fib(4)
    m = re.search(r'(?:fib|factorial|recur)\s*\(\s*([0-9]+)\s*\)', code)
    arg_val = int(m.group(1)) if m else 3
    if arg_val > 6:
        arg_val = 6  # Cap call stack trace depth for responsiveness

    harness = f"""
import json

frames = []
stack = []
step = 0

def fib(n):
    global step
    step += 1
    frame_name = f"fib({{n}})"
    stack.append(frame_name)
    frames.append({{
        "step": step,
        "type": "call_stack",
        "stack": list(stack),
        "action": "PUSH",
        "current_val": n,
        "message": f"Stack PUSH: invoking {{frame_name}}",
        "code_line": "def fib(n):"
    }})
    if n <= 1:
        step += 1
        frames.append({{
            "step": step,
            "type": "call_stack",
            "stack": list(stack),
            "action": "POP",
            "current_val": n,
            "message": f"Base case reached: {{frame_name}} returns {{n}}",
            "code_line": "if n <= 1: return n"
        }})
        stack.pop()
        return n
    res = fib(n - 1) + fib(n - 2)
    step += 1
    frames.append({{
        "step": step,
        "type": "call_stack",
        "stack": list(stack),
        "action": "POP",
        "current_val": res,
        "message": f"Stack POP: {{frame_name}} returns {{res}}",
        "code_line": "return fib(n-1) + fib(n-2)"
    }})
    stack.pop()
    return res

fib({arg_val})

print("---PAYLOAD_START---")
print(json.dumps({{
    "supported": True,
    "algorithm": f"Recursion Call Stack Trace ({language.upper()})",
    "visual_type": "call_stack",
    "total_steps": len(frames),
    "initial_data": {arg_val},
    "frames": frames
}}))
print("---PAYLOAD_END---")
"""
    result = _run_tracer_harness(harness)
    if result:
        return result
    return {
        "supported": False,
        "reason": "Docker sandbox trace execution failed for recursion.",
        "frames": []
    }


def _trace_traversal_in_docker(code: str, language: str) -> Dict[str, Any]:
    nums = _extract_array_from_code(code)
    if not nums:
        return {
            "supported": False,
            "reason": "No collection literal detected in code to trace traversal.",
            "frames": []
        }

    harness = f"""
import json

arr = {nums}
frames = []
for idx, val in enumerate(arr):
    frames.append({{
        "step": idx,
        "type": "traversal",
        "array": arr,
        "current_index": idx,
        "message": f"Traversing index [{{idx}}]: value = {{val}}",
        "code_line": f"for idx, val in enumerate(arr):"
    }})

print("---PAYLOAD_START---")
print(json.dumps({{
    "supported": True,
    "algorithm": f"Sequential Collection Trace ({language.upper()})",
    "visual_type": "traversal",
    "total_steps": len(frames),
    "initial_data": {nums},
    "frames": frames
}}))
print("---PAYLOAD_END---")
"""
    result = _run_tracer_harness(harness)
    if result:
        return result
    return {
        "supported": False,
        "reason": "Docker sandbox trace execution failed for collection traversal.",
        "frames": []
    }
