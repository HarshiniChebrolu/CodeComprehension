import ast
import re
from typing import Dict, Any


def analyze_complexity(code: str, language: str = "python") -> Dict[str, Any]:
    """
    Performs static algorithmic time and space complexity analysis
    using AST structural analysis (for Python) and pattern inspection (for all languages).
    """
    lang = language.lower()

    if not code or not code.strip():
        return {
            "time_complexity": "O(1)",
            "space_complexity": "O(1)",
            "reasoning": "No operations found.",
            "best_case": "O(1)",
            "average_case": "O(1)",
            "worst_case": "O(1)",
            "space_details": "No auxiliary memory allocated.",
            "is_estimate": False,
            "hotspots": []
        }

    # Python AST complexity analysis
    if lang in ("python", "py"):
        try:
            tree = ast.parse(code)
            return _analyze_python_ast_complexity(tree, code)
        except Exception:
            pass

    # Fallback pattern-based analysis for non-Python or syntax-error code
    return _analyze_pattern_complexity(code)


def _analyze_python_ast_complexity(tree: ast.AST, code: str) -> Dict[str, Any]:
    max_loop_depth = 0
    loop_details = []
    recursion_found = False
    recursive_branching = 1
    has_sorting = False
    has_binary_search = False
    has_dict_map = False
    auxiliary_allocations = 0

    # Function names to detect self-recursion
    func_names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            func_names.add(node.name)

    # Detect recursive calls and sorting inside functions
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            call_name = ""
            if isinstance(node.func, ast.Name):
                call_name = node.func.id
            elif isinstance(node.func, ast.Attribute):
                call_name = node.func.attr

            if call_name in ("sort", "sorted"):
                has_sorting = True
            if call_name in func_names:
                recursion_found = True

    # Detect recursive branching factor
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            rec_calls = 0
            for child in ast.walk(node):
                if isinstance(child, ast.Call):
                    c_name = child.func.id if isinstance(child.func, ast.Name) else ""
                    if c_name == node.name:
                        rec_calls += 1
            if rec_calls > 1:
                recursive_branching = max(recursive_branching, rec_calls)

    # Walk loops and compute nesting depth
    def walk_loop_depth(node, current_depth):
        nonlocal max_loop_depth
        if isinstance(node, (ast.For, ast.While)):
            current_depth += 1
            max_loop_depth = max(max_loop_depth, current_depth)
            loop_details.append({
                "line": node.lineno,
                "depth": current_depth,
                "type": "for" if isinstance(node, ast.For) else "while"
            })

        for child in ast.iter_child_nodes(node):
            walk_loop_depth(child, current_depth)

    for node in ast.iter_child_nodes(tree):
        walk_loop_depth(node, 0)

    # Detect binary halving patterns (e.g. while low <= high: mid = (low+high)//2)
    code_lower = code.lower()
    if ("low <= high" in code_lower or "left <= right" in code_lower) and "// 2" in code_lower:
        has_binary_search = True

    # Detect auxiliary space allocations
    for node in ast.walk(tree):
        if isinstance(node, (ast.ListComp, ast.DictComp, ast.SetComp)):
            auxiliary_allocations += 1
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "append":
            auxiliary_allocations += 1
        elif isinstance(node, (ast.Dict, ast.Set)):
            has_dict_map = True

    # Determine Time Complexity
    time_comp = "O(1)"
    best_case = "O(1)"
    avg_case = "O(1)"
    worst_case = "O(1)"
    reasoning = "Performs constant time sequential statements with no loops or recursion."
    hotspots = []

    if recursion_found:
        if recursive_branching >= 2:
            time_comp = "O(2ⁿ)"
            best_case = "O(1)"
            avg_case = "O(2ⁿ)"
            worst_case = "O(2ⁿ)"
            reasoning = f"Multiple recursive branches (branching factor ~ {recursive_branching}) generate an exponential recursion tree."
            hotspots.append(f"Recursive branching with {recursive_branching} self-calls")
        else:
            time_comp = "O(n)"
            best_case = "O(1)"
            avg_case = "O(n)"
            worst_case = "O(n)"
            reasoning = "Single recursive call reduces input size linearly on each recursive step."
            hotspots.append("Linear recursive call chain")
    elif has_binary_search:
        time_comp = "O(log n)"
        best_case = "O(1)"
        avg_case = "O(log n)"
        worst_case = "O(log n)"
        reasoning = "Search space is halved on each iteration (divide-and-conquer strategy)."
        hotspots.append("Binary halving loop: midpoint division")
    elif max_loop_depth >= 3:
        time_comp = "O(n³)"
        best_case = "O(n)"
        avg_case = "O(n³)"
        worst_case = "O(n³)"
        reasoning = f"Found {max_loop_depth} nested loop layers leading to cubic iteration count."
        hotspots.append(f"Triple-nested loops at depth {max_loop_depth}")
    elif max_loop_depth == 2:
        time_comp = "O(n²)"
        best_case = "O(n)"
        avg_case = "O(n²)"
        worst_case = "O(n²)"
        reasoning = "Nested loops detected: inner loop executes up to n times for each of the outer loop's n iterations."
        hotspots.append("Nested loop execution (n × n operations)")
    elif max_loop_depth == 1:
        if has_sorting:
            time_comp = "O(n log n)"
            best_case = "O(n)"
            avg_case = "O(n log n)"
            worst_case = "O(n log n)"
            reasoning = "Combines a single linear loop with a sorting pass (Timsort O(n log n))."
            hotspots.append("Sorting combined with linear scan")
        else:
            time_comp = "O(n)"
            best_case = "O(1) (if early return occurs)"
            avg_case = "O(n)"
            worst_case = "O(n)"
            reasoning = "Single linear loop traverses the input collection once."
            hotspots.append("Linear loop iteration")
    elif has_sorting:
        time_comp = "O(n log n)"
        best_case = "O(n)"
        avg_case = "O(n log n)"
        worst_case = "O(n log n)"
        reasoning = "Utilizes sorting algorithm (Timsort: average O(n log n))."
        hotspots.append("Collection sorting call")

    # Space Complexity
    space_comp = "O(1)"
    space_details = "Auxiliary space is constant O(1); modifications are performed in-place."

    if recursion_found:
        if recursive_branching >= 2:
            space_comp = "O(n)"
            space_details = "Call stack depth reaches up to O(n) simultaneous frames."
        else:
            space_comp = "O(n)"
            space_details = "Linear recursion consumes O(n) activation stack memory."
    elif auxiliary_allocations > 0 or has_dict_map:
        space_comp = "O(n)"
        space_details = "Allocates auxiliary data structures (hash table, dynamic list, or comprehension) proportional to input size."

    return {
        "time_complexity": time_comp,
        "space_complexity": space_comp,
        "reasoning": reasoning,
        "best_case": best_case,
        "average_case": avg_case,
        "worst_case": worst_case,
        "space_details": space_details,
        "is_estimate": True,
        "max_loop_depth": max_loop_depth,
        "hotspots": hotspots
    }


def _analyze_pattern_complexity(code: str) -> Dict[str, Any]:
    lines = code.split("\n")
    loop_keywords = ["for (", "for(", "while (", "while(", "for ", "while "]
    nested_count = 0
    current_depth = 0

    for line in lines:
        stripped = line.strip()
        if any(stripped.startswith(k) for k in loop_keywords):
            current_depth += 1
            nested_count = max(nested_count, current_depth)
        if "}" in stripped and current_depth > 0:
            current_depth -= 1

    if nested_count >= 2:
        return {
            "time_complexity": "O(n²)",
            "space_complexity": "O(1)",
            "reasoning": "Detected nested iteration patterns producing quadratic work.",
            "best_case": "O(n)",
            "average_case": "O(n²)",
            "worst_case": "O(n²)",
            "space_details": "In-place iteration with minimal additional variables.",
            "is_estimate": True,
            "max_loop_depth": nested_count,
            "hotspots": ["Nested iteration loop"]
        }
    elif nested_count == 1:
        return {
            "time_complexity": "O(n)",
            "space_complexity": "O(1)",
            "reasoning": "Single loop traversing elements sequentially.",
            "best_case": "O(1)",
            "average_case": "O(n)",
            "worst_case": "O(n)",
            "space_details": "Constant auxiliary memory.",
            "is_estimate": True,
            "max_loop_depth": 1,
            "hotspots": ["Sequential loop"]
        }

    return {
        "time_complexity": "O(1)",
        "space_complexity": "O(1)",
        "reasoning": "Constant time sequential operations.",
        "best_case": "O(1)",
        "average_case": "O(1)",
        "worst_case": "O(1)",
        "space_details": "Fixed primitive storage.",
        "is_estimate": False,
        "max_loop_depth": 0,
        "hotspots": []
    }
