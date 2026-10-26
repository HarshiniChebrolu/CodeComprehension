import re
from typing import Dict, Any, List


def generate_visualization_frames(code: str, language: str = "python") -> Dict[str, Any]:
    """
    Generates step-by-step visual execution frames with state, pointers,
    and explanatory annotations dynamically extracted from the user's code.
    """
    code_lower = code.lower()
    lang = language.lower()

    if any(k in code_lower for k in ("sort", "bubble", "swap", "selection")):
        return _generate_dynamic_sorting_frames(code, lang)
    elif any(k in code_lower for k in ("binary", "search", "mid", "low", "high")):
        return _generate_dynamic_binary_search_frames(code, lang)
    elif "sum" in code_lower and ("target" in code_lower or "nums" in code_lower or "twosum" in code_lower):
        return _generate_dynamic_two_sum_frames(code, lang)
    elif any(k in code_lower for k in ("fib", "factorial", "recur")):
        return _generate_dynamic_recursion_frames(code, lang)
    else:
        return _generate_dynamic_traversal_frames(code, lang)


def _extract_array_from_code(code: str) -> List[int]:
    """
    Extracts array or vector numbers from C++ ({3, 2, 4}), Python/JS ([3, 2, 4]), or C.
    """
    # Try C++ initializer list: = {3, 2, 4}
    brace_match = re.search(r'=\s*\{\s*([0-9\s,-]+)\s*\}', code)
    if brace_match:
        try:
            nums = [int(x.strip()) for x in brace_match.group(1).split(",") if x.strip()]
            if 2 <= len(nums) <= 15:
                return nums
        except Exception:
            pass

    # Try bracket array: = [3, 2, 4]
    bracket_match = re.search(r'\[\s*([0-9\s,-]+)\s*\]', code)
    if bracket_match:
        try:
            nums = [int(x.strip()) for x in bracket_match.group(1).split(",") if x.strip()]
            if 2 <= len(nums) <= 15:
                return nums
        except Exception:
            pass

    return [3, 2, 4]


def _extract_target_from_code(code: str, default: int = 6) -> int:
    match = re.search(r'(?:target|sum)\s*=\s*([0-9]+)', code)
    if match:
        try:
            return int(match.group(1))
        except Exception:
            pass
    return default


def _generate_dynamic_two_sum_frames(code: str, language: str) -> Dict[str, Any]:
    nums = _extract_array_from_code(code)
    target = _extract_target_from_code(code, default=6 if nums == [3, 2, 4] else 9)
    frames = []
    n = len(nums)

    is_cpp = language in ("cpp", "c++", "c")
    has_nested = "for" in code and code.count("for") >= 2

    step = 0
    init_code = "for (int i = 0; i < nums.size(); i++)" if is_cpp else "for i in range(len(nums)):"
    inner_code = "if (nums[i] + nums[j] == target)" if is_cpp else "if nums[i] + nums[j] == target:"

    frames.append({
        "step": step,
        "type": "two_sum",
        "array": list(nums),
        "target": target,
        "current_index": 0,
        "pointer_j": None,
        "hashmap": {},
        "found_pair": None,
        "message": f"Input array: {nums}, Target: {target}. Beginning search.",
        "code_line": f"vector<int> nums = {{{', '.join(map(str, nums))}}}; target = {target};" if is_cpp else f"nums = {nums}, target = {target}"
    })

    if has_nested:
        # Check if code allows i == j bug (starts j at 0 instead of i + 1)
        j_starts_at_zero = "j = 0" in code or "j=0" in code
        found = False

        for i in range(n):
            j_start = 0 if j_starts_at_zero else i + 1
            for j in range(j_start, n):
                step += 1
                curr_sum = nums[i] + nums[j]
                is_match = (curr_sum == target)

                msg = f"Testing pair: nums[{i}] ({nums[i]}) + nums[{j}] ({nums[j]}) = {curr_sum} (Target: {target})."
                if i == j and is_match:
                    msg = f"DEFECT DETECTED: Index {i} paired with itself! nums[{i}] ({nums[i]}) + nums[{j}] ({nums[j]}) = {target}. Returning premature [{i}, {j}]."

                frames.append({
                    "step": step,
                    "type": "two_sum",
                    "array": list(nums),
                    "target": target,
                    "current_index": i,
                    "pointer_j": j,
                    "complement": target - nums[i],
                    "hashmap": {"i": i, "j": j, "sum": curr_sum},
                    "found_pair": [i, j] if is_match else None,
                    "message": msg,
                    "code_line": inner_code
                })

                if is_match:
                    found = True
                    break
            if found:
                break
    else:
        # Hash map O(n) approach
        seen = {}
        for i, val in enumerate(nums):
            comp = target - val
            step += 1
            frames.append({
                "step": step,
                "type": "two_sum",
                "array": list(nums),
                "target": target,
                "current_index": i,
                "pointer_j": seen.get(comp),
                "complement": comp,
                "hashmap": dict(seen),
                "found_pair": None,
                "message": f"Index {i} has value {val}. Looking for complement {target} - {val} = {comp}.",
                "code_line": f"seen.has({comp})" if is_cpp else f"if {comp} in seen:"
            })

            if comp in seen:
                step += 1
                frames.append({
                    "step": step,
                    "type": "two_sum",
                    "array": list(nums),
                    "target": target,
                    "current_index": i,
                    "pointer_j": seen[comp],
                    "complement": comp,
                    "hashmap": dict(seen),
                    "found_pair": [seen[comp], i],
                    "message": f"Match Found! Complement {comp} exists at index {seen[comp]}. Solved in O(n)!",
                    "code_line": f"return {{{seen[comp]}, {i}}};" if is_cpp else f"return [{seen[comp]}, {i}]"
                })
                break

            seen[val] = i

    return {
        "algorithm": f"Two-Sum Execution Trace ({language.upper()})",
        "visual_type": "two_sum",
        "total_steps": len(frames),
        "initial_data": nums,
        "frames": frames
    }


def _generate_dynamic_sorting_frames(code: str, language: str) -> Dict[str, Any]:
    arr = _extract_array_from_code(code)
    if arr == [3, 2, 4]:
        arr = [64, 34, 25, 12, 22, 11, 90]

    n = len(arr)
    working_arr = list(arr)
    frames = []
    step_num = 0
    is_cpp = language in ("cpp", "c++", "c")

    frames.append({
        "step": step_num,
        "type": "sorting",
        "array": list(working_arr),
        "comparing": [],
        "swapping": False,
        "sorted_indices": [],
        "message": f"Initial unsorted collection: {working_arr}",
        "code_line": "void bubbleSort(vector<int>& arr)" if is_cpp else "def bubble_sort(arr):"
    })

    sorted_indices = []
    for i in range(n):
        swapped = False
        for j in range(0, n - i - 1):
            step_num += 1
            frames.append({
                "step": step_num,
                "type": "sorting",
                "array": list(working_arr),
                "comparing": [j, j + 1],
                "swapping": False,
                "sorted_indices": list(sorted_indices),
                "message": f"Comparing index [{j}] ({working_arr[j]}) and [{j+1}] ({working_arr[j+1]})",
                "code_line": "if (arr[j] > arr[j + 1])" if is_cpp else "if arr[j] > arr[j + 1]:"
            })

            if working_arr[j] > working_arr[j + 1]:
                working_arr[j], working_arr[j + 1] = working_arr[j + 1], working_arr[j]
                swapped = True
                step_num += 1
                frames.append({
                    "step": step_num,
                    "type": "sorting",
                    "array": list(working_arr),
                    "comparing": [j, j + 1],
                    "swapping": True,
                    "sorted_indices": list(sorted_indices),
                    "message": f"Swap! Out of order: swapped positions {j} and {j+1}",
                    "code_line": "swap(arr[j], arr[j + 1]);" if is_cpp else "arr[j], arr[j+1] = arr[j+1], arr[j]"
                })

        sorted_indices.append(n - i - 1)
        step_num += 1
        frames.append({
            "step": step_num,
            "type": "sorting",
            "array": list(working_arr),
            "comparing": [],
            "swapping": False,
            "sorted_indices": list(sorted_indices),
            "message": f"Pass complete. Value {working_arr[n - i - 1]} permanently settled.",
            "code_line": "// Pass finished" if is_cpp else "# Pass finished"
        })
        if not swapped:
            break

    return {
        "algorithm": f"Bubble Sort Execution Trace ({language.upper()})",
        "visual_type": "array_bars",
        "total_steps": len(frames),
        "initial_data": arr,
        "frames": frames
    }


def _generate_dynamic_binary_search_frames(code: str, language: str) -> Dict[str, Any]:
    arr = [2, 5, 8, 12, 16, 23, 38, 56, 72, 91]
    target = _extract_target_from_code(code, default=23)
    frames = []
    step = 0
    low = 0
    high = len(arr) - 1
    is_cpp = language in ("cpp", "c++", "c")

    frames.append({
        "step": step,
        "type": "binary_search",
        "array": list(arr),
        "target": target,
        "low": low,
        "high": high,
        "mid": None,
        "found": False,
        "message": f"Searching for target {target} in sorted array of {len(arr)} elements.",
        "code_line": "int low = 0, high = arr.size() - 1;" if is_cpp else "low = 0; high = len(arr) - 1"
    })

    while low <= high:
        mid = (low + high) // 2
        step += 1
        frames.append({
            "step": step,
            "type": "binary_search",
            "array": list(arr),
            "target": target,
            "low": low,
            "high": high,
            "mid": mid,
            "found": False,
            "message": f"Evaluated mid index {mid} (value {arr[mid]}). Search range: [{low} ... {high}].",
            "code_line": "int mid = (low + high) / 2;" if is_cpp else "mid = (low + high) // 2"
        })

        if arr[mid] == target:
            step += 1
            frames.append({
                "step": step,
                "type": "binary_search",
                "array": list(arr),
                "target": target,
                "low": low,
                "high": high,
                "mid": mid,
                "found": True,
                "message": f"Target {target} located at index {mid}! Completed in O(log n).",
                "code_line": "return mid;" if is_cpp else "return mid"
            })
            break
        elif arr[mid] < target:
            low = mid + 1
            step += 1
            frames.append({
                "step": step,
                "type": "binary_search",
                "array": list(arr),
                "target": target,
                "low": low,
                "high": high,
                "mid": mid,
                "found": False,
                "message": f"{arr[mid]} < {target}. Discarding left subarray; moving low to {low}.",
                "code_line": "low = mid + 1;" if is_cpp else "low = mid + 1"
            })
        else:
            high = mid - 1
            step += 1
            frames.append({
                "step": step,
                "type": "binary_search",
                "array": list(arr),
                "target": target,
                "low": low,
                "high": high,
                "mid": mid,
                "found": False,
                "message": f"{arr[mid]} > {target}. Discarding right subarray; moving high to {high}.",
                "code_line": "high = mid - 1;" if is_cpp else "high = mid - 1"
            })

    return {
        "algorithm": f"Binary Search Trace ({language.upper()})",
        "visual_type": "binary_search",
        "total_steps": len(frames),
        "initial_data": arr,
        "frames": frames
    }


def _generate_dynamic_recursion_frames(code: str, language: str) -> Dict[str, Any]:
    frames = []
    stack = []
    step = 0
    is_cpp = language in ("cpp", "c++", "c")

    def fib_sim(n, depth=0):
        nonlocal step
        frame_name = f"fib({n})"
        stack.append(frame_name)
        step += 1
        frames.append({
            "step": step,
            "type": "call_stack",
            "stack": list(stack),
            "action": "PUSH",
            "current_val": n,
            "message": f"Stack PUSH: Invoking {frame_name} at recursion depth {depth}.",
            "code_line": f"int fib({n})" if is_cpp else f"def fibonacci({n}):"
        })

        if n <= 1:
            step += 1
            frames.append({
                "step": step,
                "type": "call_stack",
                "stack": list(stack),
                "action": "BASE_CASE",
                "current_val": n,
                "message": f"Base case reached: {frame_name} returns {n}.",
                "code_line": "if (n <= 1) return n;" if is_cpp else "if n <= 1: return n"
            })
            stack.pop()
            return n

        val1 = fib_sim(n - 1, depth + 1)
        val2 = fib_sim(n - 2, depth + 1)
        res = val1 + val2

        step += 1
        frames.append({
            "step": step,
            "type": "call_stack",
            "stack": list(stack),
            "action": "POP",
            "current_val": res,
            "message": f"Stack POP: {frame_name} returns {val1} + {val2} = {res}.",
            "code_line": "return fib(n-1) + fib(n-2);" if is_cpp else "return fib(n-1) + fib(n-2)"
        })
        stack.pop()
        return res

    fib_sim(3)

    return {
        "algorithm": f"Recursion Call Stack Trace ({language.upper()})",
        "visual_type": "call_stack",
        "total_steps": len(frames),
        "initial_data": 3,
        "frames": frames
    }


def _generate_dynamic_traversal_frames(code: str, language: str) -> Dict[str, Any]:
    arr = _extract_array_from_code(code)
    is_cpp = language in ("cpp", "c++", "c")
    frames = []

    for idx, val in enumerate(arr):
        frames.append({
            "step": idx,
            "type": "traversal",
            "array": arr,
            "current_index": idx,
            "message": f"Traversing index [{idx}]: current element value is {val}.",
            "code_line": f"for (int i = 0; i < {len(arr)}; i++)" if is_cpp else f"for item in collection:"
        })

    return {
        "algorithm": f"Sequential Collection Trace ({language.upper()})",
        "visual_type": "traversal",
        "total_steps": len(frames),
        "initial_data": arr,
        "frames": frames
    }
