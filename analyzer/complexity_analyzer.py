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

    # Check for early returns or breaks inside loops to justify distinct best/worst cases
    has_early_exit = False
    for node in ast.walk(tree):
        if isinstance(node, (ast.For, ast.While)):
            for child in ast.walk(node):
                if isinstance(child, (ast.Break, ast.Return)):
                    has_early_exit = True
                    break

    # Determine Time Complexity
    time_comp = "O(1)"
    best_case = "O(1)"
    avg_case = "O(1)"
    worst_case = "O(1)"
    reasoning = "Performs constant time sequential statements with no loops or recursion."
    hotspots = []
    evidence = []
    assumptions = ["Execution finishes without external interruption", "Basic arithmetic operations are O(1)"]
    confidence = "high"
    limitations = "Static analysis inspects control flow AST without evaluating input data distribution or runtime caching."

    # Check for constant loop bounds
    def is_constant_bound_loop(node):
        if isinstance(node, ast.For) and isinstance(node.iter, ast.Call):
            if isinstance(node.iter.func, ast.Name) and node.iter.func.id == "range":
                if node.iter.args and all(isinstance(arg, ast.Constant) and isinstance(arg.value, int) for arg in node.iter.args):
                    return True
        return False

    variable_nested_depth = 0
    for l in loop_details:
        evidence.append(f"Line {l['line']}: {l['type']} loop at nesting depth {l['depth']}")

    # Calculate actual variable loop depth
    if max_loop_depth > 0:
        variable_nested_depth = max_loop_depth
        for node in ast.walk(tree):
            if isinstance(node, (ast.For, ast.While)):
                for child in node.body:
                    if isinstance(child, (ast.For, ast.While)) and is_constant_bound_loop(child):
                        variable_nested_depth = min(variable_nested_depth, 1)
                        evidence.append(f"Inner loop at line {child.lineno} has constant bounds; effective scaling depth reduced to 1.")

    if recursion_found:
        evidence.append(f"Recursive call detected (branching factor: {recursive_branching})")
        if recursive_branching >= 2:
            time_comp = "O(2ⁿ)"
            avg_case = "O(2ⁿ)"
            worst_case = "O(2ⁿ)"
            best_case = "O(1)" if has_early_exit else "O(2ⁿ)"
            reasoning = f"Multiple recursive branches (branching factor ~ {recursive_branching}) generate an exponential recursion tree."
            hotspots.append(f"Recursive branching with {recursive_branching} self-calls")
            assumptions.append("Subproblems are not memoized, resulting in overlapping recursive calls")
        else:
            time_comp = "O(n)"
            avg_case = "O(n)"
            worst_case = "O(n)"
            best_case = "O(1)" if has_early_exit else "O(n)"
            reasoning = "Single recursive call reduces input size linearly on each recursive step."
            hotspots.append("Linear recursive call chain")
            assumptions.append("Recursion decreases problem size by a constant amount each step")
    elif has_binary_search:
        time_comp = "O(log n)"
        avg_case = "O(log n)"
        worst_case = "O(log n)"
        best_case = "O(1)" if has_early_exit else "O(log n)"
        reasoning = "Search space is halved on each iteration (divide-and-conquer strategy)."
        hotspots.append("Binary halving loop: midpoint division")
        evidence.append("Loop condition and midpoint division halve remaining search space")
        assumptions.append("Input collection is sorted")
    elif variable_nested_depth >= 3:
        time_comp = "O(n³)"
        avg_case = "O(n³)"
        worst_case = "O(n³)"
        best_case = "O(1)" if has_early_exit else "O(n³)"
        reasoning = f"Found {variable_nested_depth} nested loop layers with dynamic bounds leading to cubic iteration count."
        hotspots.append(f"Triple-nested loops at depth {variable_nested_depth}")
        assumptions.append("All 3 loop bounds scale proportionally with input size n")
    elif variable_nested_depth == 2:
        time_comp = "O(n²)"
        avg_case = "O(n²)"
        worst_case = "O(n²)"
        best_case = "O(1)" if has_early_exit else "O(n²)"
        reasoning = "Nested loops with input-dependent bounds detected: inner loop executes up to n times for outer iterations."
        hotspots.append("Nested loop execution (n × n operations)")
        assumptions.append("Both outer and inner loop bounds scale with collection size n")
    elif max_loop_depth == 1 or variable_nested_depth == 1:
        if has_sorting:
            time_comp = "O(n log n)"
            avg_case = "O(n log n)"
            worst_case = "O(n log n)"
            best_case = "O(n)" if has_early_exit else "O(n log n)"
            reasoning = "Combines a linear loop with a sorting pass (Timsort O(n log n))."
            hotspots.append("Sorting combined with linear scan")
            evidence.append("Sorting invocation detected inside or alongside linear iteration")
        else:
            time_comp = "O(n)"
            avg_case = "O(n)"
            worst_case = "O(n)"
            best_case = "O(1)" if has_early_exit else "O(n)"
            reasoning = "Single linear loop traverses the input collection once."
            hotspots.append("Linear loop iteration")
            assumptions.append("Loop traverses elements sequentially from start to end")
    elif has_sorting:
        time_comp = "O(n log n)"
        avg_case = "O(n log n)"
        worst_case = "O(n log n)"
        best_case = "O(n)"
        reasoning = "Utilizes sorting algorithm (Timsort: average O(n log n))."
        hotspots.append("Collection sorting call")
        evidence.append("Built-in sort() or sorted() invoked on dataset")

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
        evidence.append(f"Detected {auxiliary_allocations} dynamic allocations or hash map structures")

    return {
        "time_complexity": time_comp,
        "space_complexity": space_comp,
        "reasoning": reasoning,
        "evidence": evidence,
        "assumptions": assumptions,
        "confidence": confidence,
        "limitations": limitations,
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
    evidence = []
    has_early_exit = any("return " in line or "break;" in line for line in lines)

    for idx, line in enumerate(lines, start=1):
        stripped = line.strip()
        if any(stripped.startswith(k) for k in loop_keywords):
            current_depth += 1
            nested_count = max(nested_count, current_depth)
            evidence.append(f"Line {idx}: iteration construct at depth {current_depth}")
        if "}" in stripped and current_depth > 0:
            current_depth -= 1

    # Check if inner loop has constant bound like (int j = 0; j < 5; j++)
    if nested_count >= 2:
        constant_inner = re.search(r'for\s*\([^;]+;\s*[a-zA-Z0-9_]+\s*<\s*\d+\s*;', code)
        if constant_inner:
            nested_count = 1
            evidence.append("Inner loop bound is constant numeric literal; effective complexity is O(n)")

    if nested_count >= 2:
        return {
            "time_complexity": "O(n²)",
            "space_complexity": "O(1)",
            "reasoning": "Detected nested iteration patterns producing quadratic work.",
            "evidence": evidence,
            "assumptions": ["Both loop bounds scale linearly with input size n"],
            "confidence": "heuristic",
            "limitations": "Heuristic pattern scan without complete compiler intermediate representation.",
            "best_case": "O(1)" if has_early_exit else "O(n²)",
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
            "evidence": evidence,
            "assumptions": ["Loop condition evaluates up to n times"],
            "confidence": "heuristic",
            "limitations": "Heuristic pattern scan without compiler AST.",
            "best_case": "O(1)" if has_early_exit else "O(n)",
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
        "evidence": ["No loop or recursive constructs detected"],
        "assumptions": ["All invoked statements execute in O(1) time"],
        "confidence": "high",
        "limitations": "Assumes underlying library calls are constant time.",
        "best_case": "O(1)",
        "average_case": "O(1)",
        "worst_case": "O(1)",
        "space_details": "Fixed primitive storage.",
        "is_estimate": False,
        "max_loop_depth": 0,
        "hotspots": []
    }
