import ast
import re
import logging
from typing import List, Dict, Any

logger = logging.getLogger("codecomprehension.analyzer.bug_detector")


class BugDetectorVisitor(ast.NodeVisitor):
    def __init__(self, code: str):
        self.code = code
        self.lines = code.split("\n")
        self.issues = []
        self._issue_counter = 0

        # Scope tracking
        self.defined_globals = set()
        self.current_function = None
        self.local_vars = set()
        self.used_vars = set()
        self.assigned_vars = set()

    def _add_issue(self, rule_id: str, severity: str, category: str, line: int, problem: str,
                   explanation: str, hint1: str, hint2: str, hint3: str,
                   solution_code: str, why_original_failed: str, why_new_works: str):
        self._issue_counter += 1
        self.issues.append({
            "id": f"bug_{self._issue_counter}", # Unique ID for this specific instance of the issue
            "rule_id": rule_id, # Identifier for the type of rule triggered
            "severity": severity,  # CRITICAL, HIGH, MEDIUM, LOW, INFO
            "category": category,
            "line": line,
            "problem": problem,
            "explanation": explanation,
            "hints": {
                "hint1": hint1,
                "hint2": hint2,
                "hint3": hint3
            },
            "solution": {
                "code": solution_code,
                "explanation": explanation, # Default to general explanation if specific solution exp not provided
                "why_original_failed": why_original_failed,
                "why_new_works": why_new_works
            }
        })

    def visit_FunctionDef(self, node):
        prev_func = self.current_function
        prev_locals = set(self.local_vars)
        self.current_function = node.name
        self.local_vars = set(a.arg for a in node.args.args)

        # 1. Mutable default arguments check
        for default in node.args.defaults:
            if isinstance(default, (ast.List, ast.Dict, ast.Set)):
                self._add_issue(
                    rule_id="BUG_MUTABLE_DEFAULT_ARG",
                    severity="HIGH",
                    category="Dangerous Pattern",
                    line=node.lineno,
                    problem=f"Mutable default argument in function '{node.name}'",
                    explanation="Default arguments are evaluated once when the function is defined, not each time it is called. Mutating this default modifies it across all subsequent function calls.",
                    hint1="Look at the parameter list of your function definition. Do any parameters initialize directly to an empty container?",
                    hint2="In Python, lists/dictionaries given as default values persist their state between calls.",
                    hint3="Set default to None, and inside the function body initialize: if param is None: param = []",
                    solution_code=f"def {node.name}(..., param=None):\n    if param is None:\n        param = []",
                    why_original_failed="A single list object was shared across all invocations, leading to unexpected state accumulation.",
                    why_new_works="Using `None` as a sentinel and initializing a new mutable object inside the function body ensures each call gets a fresh instance."
                )

        # 2. Check for missing return values in branches
        has_returns = []
        for stmt in ast.walk(node):
            if isinstance(stmt, ast.Return):
                has_returns.append(stmt)

        if has_returns and len(node.body) > 1:
            # If function has returns inside conditionals but last statement is not a return
            last_stmt = node.body[-1]
            if not isinstance(last_stmt, (ast.Return, ast.Raise)):
                # If there's an if with return
                if any(isinstance(s, ast.If) for s in node.body):
                    self._add_issue(
                        severity="MEDIUM",
                        category="Logic Bug",
                        line=node.lineno,
                        problem=f"Potential implicit 'None' return path in '{node.name}'",
                        explanation="The function returns a specific value in some execution paths, but falls off the end without an explicit return statement, returning None by default.",
                        hint1="Trace all possible branches in your function. What is returned if none of the if conditions match?",
                        hint2="Notice the end of the function body. Is there an explicit fallback return value?",
                        hint3="Add an explicit 'return None' or return a default fallback value at the end of the function.",
                        solution_code=f"    # At the end of {node.name}\n    return None  # or appropriate fallback/raise error",
                        solution_exp="Ensure every execution path terminates with an explicit return statement or exception.",
                        why_failed="Implicit None returns can cause subtle NoneType attribute or indexing errors downstream.",
                        why_works="Explicit returns make the function contract clear and predictable."
                    )

        # 3. Unreachable code after return or raise
        # Only check the current level of the function body, not nested blocks
        for i, stmt in enumerate(node.body[:-1]):
            if isinstance(stmt, (ast.Return, ast.Raise)):
                next_stmt = node.body[i + 1]
                # Ensure the unreachable code is not a docstring or type comment
                if not (isinstance(next_stmt, ast.Expr) and isinstance(next_stmt.value, ast.Constant) and isinstance(next_stmt.value.value, str)):
                    self._add_issue(
                        rule_id="BUG_UNREACHABLE_CODE",
                        severity="LOW",
                        category="Dead Code",
                        line=next_stmt.lineno,
                        problem="Unreachable code detected",
                        explanation=f"Statements starting at line {next_stmt.lineno} in this block will never be executed because a `return` or `raise` statement on line {stmt.lineno} terminates the execution flow prematurely.",
                        hint1="Examine the sequence of statements in your function. Is there any code positioned immediately after an unconditional `return` or `raise`?",
                        hint2="Code placed after a `return` or `raise` within the same block will never be executed. Review the control flow at line " + str(stmt.lineno) + ".",
                        hint3="Relocate the unreachable statements to before the `return`/`raise` statement, or remove them if they are no longer needed, to maintain a clean and logical control flow.",
                        solution_code="# Move or remove statements below the return/raise",
                        why_original_failed="Code placed after an unconditional `return` or `raise` statement is never reached by the program's execution flow.",
                        why_new_works="Ensuring all necessary logic executes *before* a terminal statement guarantees its intended operation and prevents dead code."
                    )
                    break # Only report the first block of unreachable code immediately after the first terminal statement

        self.generic_visit(node)
        self.current_function = prev_func
        self.local_vars = prev_locals

    def visit_Subscript(self, node):
        # 4. Unsafe dict or list indexing (e.g., `user['name']` without checking existence)
        if isinstance(node.slice, ast.Constant) and isinstance(node.slice.value, str):
            key_name = node.slice.value
            # Check if it's within a try-except block or preceded by a check for the key
            # This is a heuristic and might have false positives/negatives, focus on common patterns
            is_guarded = False
            # Check for 'in' operator check before the subscript (simple heuristic)
            current_line = self.lines[node.lineno - 1]
            if f"'{key_name}' in" in current_line or f'"{key_name}" in' in current_line:
                is_guarded = True
            # More complex checks would involve AST analysis of preceding statements

            if not is_guarded:
                self._add_issue(
                    rule_id="BUG_UNSAFE_DICT_ACCESS",
                    severity="MEDIUM",
                    category="Runtime Risk",
                    line=node.lineno,
                    problem=f"Unsafe dictionary or list access with key/index '{key_name}'",
                    explanation=f"Directly accessing a dictionary key or list index using bracket notation (e.g., `data['{key_name}']`) will raise a `KeyError` or `IndexError` if the key/index is missing or out of bounds. This can lead to unhandled crashes.",
                    hint1="Consider how your code handles situations where the dictionary might not contain the expected key or the list index is invalid.",
                    hint2="Python dictionaries have a safer method to retrieve values that provides a default if the key is absent. List access can be guarded by checking length.",
                    hint3="Use `dict.get('{key_name}', default_value)` for dictionaries, or explicitly check `if '{key_name}' in dict_obj:` before access. For lists, validate the index against `len(list_obj)`.",
                    solution_code=f"value = my_dict.get('{key_name}', None)",
                    why_original_failed="Direct bracket access (`[]`) on dictionaries raises a `KeyError` if the key is not present, crashing the program. Similar issues occur with lists and `IndexError`.",
                    why_new_works="Using `dict.get()` provides a safe way to retrieve values, returning `None` or a specified default if the key is missing, thus preventing crashes. Explicit boundary checks protect list access."
                )
        self.generic_visit(node)

    def visit_While(self, node):
        # 5. Infinite loop detection: while True with no break/return/raise, or loop var never modified
        has_explicit_exit = False
        for sub in ast.walk(node):
            if isinstance(sub, (ast.Break, ast.Return, ast.Raise)):
                has_explicit_exit = True
                break

        if isinstance(node.test, ast.Constant) and node.test.value is True and not has_explicit_exit:
            self._add_issue(
                rule_id="BUG_INFINITE_LOOP_TRUE",
                severity="CRITICAL",
                category="Infinite Loop",
                line=node.lineno,
                problem="Definite infinite loop: `while True` without a clear exit condition",
                explanation="The `while True` loop condition is permanently true, and the loop body does not contain any `break`, `return`, or `raise` statements to terminate its execution. This will cause the program to run indefinitely or crash due to resource exhaustion.",
                hint1="Examine the loop's control condition and how it is intended to terminate. Does it have a way to exit?",
                hint2="A `while True` loop requires an explicit mechanism (like `break`, `return`, or `raise`) within its body to prevent endless execution.",
                hint3="Add a conditional check inside the loop that, when met, triggers a `break` statement to exit the loop, or ensure the function explicitly `return`s a value from within the loop.",
                solution_code="while True:\n    # loop logic\n    if exit_condition_met:\n        break",
                why_original_failed="Without an explicit exit, `while True` creates an endless loop, causing the program to hang indefinitely, consume 100% CPU, or exhaust memory.",
                why_new_works="Incorporating a clear termination condition and a `break` statement ensures the loop exits gracefully once its purpose is fulfilled, allowing the program to continue or finish."
            )

        # Heuristic for potential infinite loop if loop variable is not modified (Python specific)
        if isinstance(node.test, ast.Name):
            loop_var = node.test.id
            # Check if this variable is modified inside the loop body
            is_modified = False
            for sub_node in ast.walk(node):
                if isinstance(sub_node, ast.Assign):
                    for target in sub_node.targets:
                        if isinstance(target, ast.Name) and target.id == loop_var:
                            is_modified = True
                            break
                if is_modified:
                    break
            if not is_modified and not has_explicit_exit: # Only if no explicit exits like break/return
                self._add_issue(
                    rule_id="BUG_LOOP_VAR_NOT_MODIFIED",
                    severity="HIGH",
                    category="Infinite Loop",
                    line=node.lineno,
                    problem=f"Loop variable '{loop_var}' might not be modified, leading to infinite loop",
                    explanation=f"The `while` loop condition depends on variable '{loop_var}', but '{loop_var}' does not appear to be modified within the loop body. This could result in an infinite loop if '{loop_var}' remains truthy.",
                    hint1="Check if the variable controlling the loop's condition is ever updated within the loop's body.",
                    hint2="If '{loop_var}' never changes its value inside the loop, and it starts as true, the loop will never terminate.",
                    hint3="Ensure that '{loop_var}' (or a variable it depends on) is reassigned or altered in a way that will eventually make the `while` condition false.",
                    solution_code=f"while {loop_var}:\n    # logic\n    {loop_var} = new_value_or_condition",
                    why_original_failed="A loop variable that is never updated will cause the loop condition to remain constant, potentially leading to an infinite loop if the condition is initially true.",
                    why_new_works="Modifying the loop variable within the loop's body ensures that the condition can eventually become false, allowing the loop to terminate correctly."
                )

        self.generic_visit(node)

    def visit_ExceptHandler(self, node):
        # 6. Bare except or broad except Exception with pass
        if node.type is None: # Bare except
            self._add_issue(
                rule_id="BUG_BARE_EXCEPT",
                severity="HIGH",
                category="Security & Robustness",
                line=node.lineno,
                problem="Bare 'except:' clause catches all exceptions indiscriminately",
                explanation="A bare `except:` clause catches all exceptions, including `KeyboardInterrupt`, `SystemExit`, and critical internal errors. This can prevent proper program termination, mask underlying bugs, and make debugging extremely difficult.",
                hint1="Review your exception handling block. What specific types of errors are you intending to catch and handle here?",
                hint2="Catching all exceptions, even system-level ones, can hide serious problems and prevent your program from responding to control signals (like Ctrl+C).",
                hint3="Always specify the exact exception types you expect to handle (e.g., `except (ValueError, KeyError):`). If you need a broad catch, use `except Exception as e:` and ensure proper logging.",
                solution_code="except (ValueError, FileNotFoundError) as e:\n    logger.warning(f'Handled expected error: {e}')",
                why_original_failed="A bare `except` clause can mask critical errors, prevent graceful exits, and make it impossible to diagnose unexpected issues, leading to unstable software.",
                why_new_works="Catching specific exceptions ensures that only anticipated errors are handled, allowing unforeseen problems to surface for proper debugging and resolution."
            )
        elif isinstance(node.body[0], ast.Pass) if node.body else False: # Except with pass
            self._add_issue(
                rule_id="BUG_SILENT_EXCEPTION",
                severity="MEDIUM",
                category="Code Smell",
                line=node.lineno,
                problem="Silently suppressed exception with 'pass'",
                explanation="Catching an exception and executing `pass` silently suppresses any error that occurs. This makes failures invisible, preventing debugging, logging, or appropriate error recovery, which can lead to corrupted state or unexpected behavior downstream.",
                hint1="Consider the implications of an error occurring in this `try` block. Does anyone get notified, or is there any fallback action taken?",
                hint2="At line " + str(node.lineno) + ", an error is caught but completely ignored. This is like sweeping a problem under the rug.",
                hint3="Instead of `pass`, log the exception details, return a meaningful error status, raise a more specific exception, or implement a clear fallback mechanism. Never silently ignore errors in production code.",
                solution_code="except Exception as e:\n    logger.error(f'Error occurred during operation: {e}')\n    return False # Or re-raise, or handle gracefully",
                why_original_failed="Silently ignoring exceptions hides critical information, making it impossible to trace the root cause of issues, leading to difficult-to-diagnose bugs and unreliable program behavior.",
                why_new_works="Logging or explicitly handling exceptions ensures that errors are acknowledged, providing valuable insights for debugging or allowing the program to recover gracefully without entering an inconsistent state."
            )

        self.generic_visit(node)

    def visit_Assign(self, node):
        # 7. Dangerous variable initialization (e.g. max_val = 0 or min_val = 0 or shadowing built-in)
        builtins = {"list", "dict", "str", "int", "float", "set", "sum", "max", "min", "id", "type", "len", "print", "input", "range"}
        for target in node.targets:
            if isinstance(target, ast.Name):
                var_name = target.id
                if var_name in builtins:
                    self._add_issue(
                        rule_id="BUG_SHADOW_BUILTIN",
                        severity="LOW",
                        category="Best Practice",
                        line=node.lineno,
                        problem=f"Variable '{var_name}' shadows a Python built-in function or type",
                        explanation=f"Assigning a value to a variable named '{var_name}' (e.g., `len = 10`) overrides the standard Python built-in function or type of the same name. This can cause unexpected `TypeError`s or incorrect behavior if the built-in is called later in the code.",
                        hint1="Look closely at the name chosen for the variable being assigned on line " + str(node.lineno) + ".",
                        hint2="Is '{var_name}' already a recognized function or type that comes standard with Python?",
                        hint3=f"Rename '{var_name}' to something more descriptive and unique, such as '{var_name}_count', 'data_length', or 'items'. Avoid using names that conflict with common built-ins.",
                        solution_code=f"{var_name}_val = {self._unparse(node.value)} # Use a more descriptive name",
                        why_original_failed=f"Overwriting the built-in `{var_name}` with a variable prevents access to the original function or type, leading to unexpected `TypeError`s when the built-in is later invoked.",
                        why_new_works="Using a distinct identifier for your variable ensures that Python's built-in functions and types remain accessible and functional, preventing naming conflicts and preserving expected behavior."
                    )

                # Check max_val = 0 bug for negative arrays or collections
                if "max" in var_name.lower() and isinstance(node.value, ast.Constant) and node.value.value == 0:
                    self._add_issue(
                        rule_id="BUG_MAX_INIT_ZERO",
                        severity="HIGH",
                        category="Logic Bug",
                        line=node.lineno,
                        problem="Initializing maximum tracker to 0 fails for negative numbers",
                        explanation="If the input collection (e.g., an array) contains only negative numbers (e.g., `[-5, -2, -10]`), initializing a maximum tracking variable to 0 will incorrectly result in 0, because 0 is greater than all negative elements. The true maximum will be missed.",
                        hint1="Look carefully at how your maximum tracking variable is initialized on line " + str(node.lineno) + ".",
                        hint2="Consider what happens if the entire dataset you are processing consists only of negative values. Will your current initialization correctly find the maximum?",
                        hint3="For finding a maximum, initialize the tracker with `float('-inf')` (negative infinity) or the first element of the collection (after checking if the collection is non-empty).",
                        solution_code=f"{var_name} = float('-inf')  # Or: {var_name} = arr[0] if arr else float('-inf')",
                        why_original_failed="Initializing a maximum tracker to 0 works for non-negative numbers but fails for collections containing only negative values, as 0 will be incorrectly reported as the maximum.",
                        why_new_works="Initializing with negative infinity (`float('-inf')`) or the first element ensures that the first comparison correctly establishes a true maximum, regardless of the sign of the numbers in the collection."
                    )
                # Check min_val = MAX_INT bug for large numbers
                if "min" in var_name.lower() and isinstance(node.value, ast.Constant) and (isinstance(node.value.value, int) and node.value.value > 10**9 or isinstance(node.value.value, float) and node.value.value == float('inf')): # Heuristic for large int or float('inf')
                    self._add_issue(
                        rule_id="BUG_MIN_INIT_INF",
                        severity="HIGH",
                        category="Logic Bug",
                        line=node.lineno,
                        problem="Initializing minimum tracker to large number/infinity fails for collections with larger values",
                        explanation="If the input collection contains values larger than the initial minimum (e.g., `min_val = float('inf')` for a collection of huge numbers), this initialization will be correct. However, if using a large integer as initial min, and all collection values are even larger, the true minimum will be missed.",
                        hint1="Re-evaluate the initial value assigned to your minimum tracking variable.",
                        hint2="Consider a scenario where all elements in your collection are larger than the initial large integer you've set for the minimum.",
                        hint3="For finding a minimum, initialize the tracker with `float('inf')` (positive infinity) or the first element of the collection (after checking if the collection is non-empty).",
                        solution_code=f"{var_name} = float('inf') # Or: {var_name} = arr[0] if arr else float('inf')",
                        why_original_failed="Initializing a minimum tracker with a specific large integer might fail if all actual values in the collection are even larger, leading to an incorrect minimum.",
                        why_new_works="Initializing with positive infinity (`float('-inf')`) or the first element ensures that the first comparison correctly establishes a true minimum, accommodating for any range of values in the collection."
                    )


        self.generic_visit(node)

    def _unparse(self, node):
        try:
            return ast.unparse(node)
        except Exception:
            return "value"


def detect_bugs(code: str, language: str = "python") -> Dict[str, Any]:
    """
    Performs comprehensive static analysis, finding logical bugs, security risks,
    runtime errors, and code quality issues.
    """
    lang = language.lower()
    issues = []

    if not code or not code.strip():
        return {
            "issues": [],
            "score": 100,
            "score_breakdown": {
                "correctness": 100,
                "readability": 100,
                "maintainability": 100,
                "efficiency": 100,
                "security": 100,
                "best_practices": 100
            },
            "summary": "No code submitted."
        }

    # Python AST analysis
    if lang in ("python", "py"):
        try:
            tree = ast.parse(code)
            visitor = BugDetectorVisitor(code)
            visitor.visit(tree)
            issues.extend(visitor.issues)
        except SyntaxError as e:
            # Syntax errors become a CRITICAL issue
            issues.append({
                "id": "syntax_err",
                "severity": "CRITICAL",
                "category": "Syntax Error",
                "line": e.lineno or 1,
                "problem": f"SyntaxError: {e.msg}",
                "explanation": f"The Python interpreter failed to parse the code at line {e.lineno or 1}: {e.msg}. The code cannot be executed.",
                "hints": {
                    "hint1": "Review the syntax near line " + str(e.lineno or 1) + ".",
                    "hint2": "Check for missing colons (:), unclosed parentheses, quotes, or indentation mismatch.",
                    "hint3": "Make sure all open brackets/quotes have pairs and control statements end with a colon."
                },
                "solution": {
                    "code": "# Fix syntax error on line " + str(e.lineno or 1),
                    "explanation": "Correct the syntax formatting to allow Python AST parsing.",
                    "why_original_failed": f"Syntax error prevented Python compilation: {e.msg}",
                    "why_new_works": "Valid Python syntax executes seamlessly."
                }
            })

    # Additional Regex & Static Heuristics (Language Agnostic & Deep Python)
    lines = code.split("\n")
    for idx, line in enumerate(lines, start=1):
        stripped = line.strip()

        # Division by zero literal
        if re.search(r'/\s*0(?![0-9\.])', stripped):
            issues.append({
                "id": f"div_zero_{idx}",
                "rule_id": "BUG_DIVISION_BY_ZERO",
                "severity": "CRITICAL",
                "category": "Runtime Error",
                "line": idx,
                "problem": "Division by zero detected",
                "explanation": "Attempting to divide by an integer constant `0` will immediately raise a `ZeroDivisionError` at runtime, crashing the program.",
                "hints": {
                    "hint1": "Look closely at the mathematical operation on line " + str(idx) + ". What is the value of the denominator?",
                    "hint2": "Division by zero is an undefined mathematical operation that computers cannot perform.",
                    "hint3": "Before performing division, always check if the denominator is zero. If it is, handle this edge case by returning a default value, raising a specific error, or skipping the operation.",
                },
                "solution": {
                    "code": f"if denominator_variable != 0:\n    result = numerator / denominator_variable\nelse:\n    result = 0 # Or handle error",
                    "explanation": "Guard against zero denominators before performing division.",
                    "why_original_failed": "Division by zero is a fundamental mathematical impossibility in computing, causing a `ZeroDivisionError` and crashing the program.",
                    "why_new_works": "By explicitly checking if the denominator is zero, the code prevents a runtime crash and allows for graceful handling of this mathematical edge case."
                }
            })

        # Off-by-one / Index error in Python range
        if lang in ("python", "py"):
            if re.search(r'range\(\s*len\([a-zA-Z0-9_]+\)\s*\+\s*1\s*\)', stripped):
                variable_name_match = re.search(r'len\(([a-zA-Z0-9_]+)\)', stripped)
                variable_name = variable_name_match.group(1) if variable_name_match else "arr"
                issues.append({
                    "id": f"off_by_one_python_{idx}",
                    "rule_id": "BUG_PYTHON_OFF_BY_ONE_RANGE",
                    "severity": "HIGH",
                    "category": "Index Error",
                    "line": idx,
                    "problem": "Potential `IndexError` (off-by-one) with `range(len(...) + 1)`",
                    "explanation": f"Arrays and lists in Python are 0-indexed, meaning valid indices range from `0` to `len({variable_name}) - 1`. Iterating with `range(len({variable_name}) + 1)` will attempt to access an index one past the last valid element, leading to an `IndexError: list index out of range`.",
                    "hints": {
                        "hint1": "Inspect the upper bound of your `range` function call on line " + str(idx) + ".",
                        "hint2": f"Remember that Python collections are zero-indexed. If `{variable_name}` has `N` elements, what are the valid index numbers for those elements?",
                        "hint3": f"To iterate through all elements of `{variable_name}` using indices, use `range(len({variable_name}))` directly without adding `1`. Alternatively, a more Pythonic way is `for item in {variable_name}:`.",
                    },
                    "solution": {
                        "code": f"for i in range(len({variable_name})):\n    # Access {variable_name}[i] safely",
                        "explanation": "Use `range(len(collection))` or direct iteration to stay within bounds.",
                        "why_original_failed": f"Attempting to access `{variable_name}[len({variable_name})]` goes beyond the valid index range, causing an `IndexError`.",
                        "why_new_works": f"`range(len({variable_name}))` correctly generates indices from `0` up to `len({variable_name}) - 1`, ensuring all accesses are within valid bounds."
                    }
                })

        # Off-by-one in C / C++ / Java / JS: for (int i = 0; i <= arr.length; i++)
        if lang in ("c", "cpp", "java", "javascript", "js"):
            match = re.search(r'for\s*\(([^;]+);\s*([a-zA-Z0-9_]+)\s*<=\s*([a-zA-Z0-9_]+)(\.length|\.size\(\)|_len)?;\s*([^)]+)\)', stripped)
            if match:
                loop_var = match.group(2)
                size_var = match.group(3)
                issues.append({
                    "id": f"off_by_one_c_like_{idx}",
                    "rule_id": "BUG_C_OFF_BY_ONE_LOOP",
                    "severity": "HIGH",
                    "category": "Index Error",
                    "line": idx,
                    "problem": "Off-by-one loop condition `'<'='` allows out-of-bounds access",
                    "explanation": f"In zero-indexed languages like C, C++, Java, and JavaScript, collections (arrays, vectors) have elements from index `0` to `length - 1`. Using the loop condition `{loop_var} <= {size_var}` will attempt to access an element at `{size_var}` (which is `length`), resulting in an out-of-bounds access or segmentation fault.",
                    "hints": {
                        "hint1": "Examine the loop's boundary condition on line " + str(idx) + ". Specifically, focus on the comparison operator.",
                        "hint2": f"What happens on the very last iteration when `{loop_var}` becomes equal to `{size_var}` (the array's length)?",
                        "hint3": "Change the comparison operator from `<=` (less than or equal to) to `<` (strictly less than). This ensures the loop terminates before accessing an invalid index.",
                    },
                    "solution": {
                        "code": f"for (int {loop_var} = 0; {loop_var} < {size_var}; {loop_var}++)",
                        "explanation": "Use strict inequality (`<`) so the loop stops before reaching out-of-bounds indices.",
                        "why_original_failed": "Using `<=` in a zero-indexed loop causes an attempt to access an element at an index equal to the array's size, which is one beyond the valid range, leading to crashes or undefined behavior.",
                        "why_new_works": "Changing to `<` ensures the loop iterates from `0` up to `size - 1`, which precisely covers all valid elements of a zero-indexed collection."
                    }
                })

        # Two sum identical index comparison bug: if nums[i] + nums[j] == target without i != j
        if "nums[i]" in stripped and "nums[j]" in stripped:
            if not ("i != j" in stripped or "j = i + 1" in code or "range(i + 1" in code or "int j = i + 1" in code or "j > i" in stripped or "j != i" in stripped):
                issues.append({
                    "id": f"two_sum_dup_{idx}",
                    "rule_id": "BUG_TWO_SUM_SELF_PAIRING",
                    "severity": "HIGH",
                    "category": "Logic Bug",
                    "line": idx,
                    "problem": "Possible self-element pairing in two-sum check",
                    "explanation": "If the inner loop's logic allows `i == j`, an element might be incorrectly paired with itself (e.g., in `nums = [3, 2, 4], target = 6`, `3` could pair with `3` if indices are not distinct). This often violates the problem's 'distinct elements' constraint.",
                    "hints": {
                        "hint1": "Consider whether your nested loops (or single loop with a hash map) guarantee that the two indices `i` and `j` will always refer to *different* elements.",
                        "hint2": "What happens if the `target` value is exactly double an element's value, and that element is allowed to be paired with itself?",
                        "hint3": "Modify your inner loop to start at `i + 1` (e.g., `for (int j = i + 1; ...)` in C-like languages, or `for j in range(i + 1, len(nums)):` in Python) to ensure `j` is always greater than `i`, thus guaranteeing distinct elements.",
                    },
                    "solution": {
                        "code": "for (int i = 0; i < n; i++) {\n    for (int j = i + 1; j < n; j++) {\n        if (nums[i] + nums[j] == target) ...",
                        "explanation": "Ensure distinct indices by starting the inner loop at `i + 1`.",
                        "why_original_failed": "Permitting an element at index `i` to pair with itself (when `i == j`) can lead to incorrect results or violations of problem constraints requiring distinct elements.",
                        "why_new_works": "By setting the inner loop to start from `i + 1`, it is guaranteed that `j` will always be a different and greater index than `i`, ensuring distinct element pairings and avoiding redundant checks."
                    }
                })

        # C / C++ Preprocessor typos (e.g. #incluude, #defne)
        if lang in ("c", "cpp"):
            match_preproc_typo = re.match(r'#\s*(incluude|incldue|includ|defne|pragme)\b', stripped)
            if match_preproc_typo:
                bad_word = match_preproc_typo.group(1)
                issues.append({
                    "id": f"preproc_typo_{idx}",
                    "rule_id": "SYNTAX_PREPROCESSOR_TYPO",
                    "severity": "CRITICAL",
                    "category": "Syntax Error",
                    "line": idx,
                    "problem": f"Invalid preprocessor directive '#{bad_word}'",
                    "explanation": f"The C/C++ compiler does not recognize '#{bad_word}'. Preprocessor directives like `#include` or `#define` must be spelled precisely. A typo here will cause a compilation error.",
                    "hints": {
                        "hint1": "Look carefully at the spelling of the preprocessor command starting with '#' on line " + str(idx) + ".",
                        "hint2": f"Notice that '#{bad_word}' contains a common spelling mistake for a preprocessor directive.",
                        "hint3": "Correct the directive to its standard form, such as `#include <header>` to include a library, or `#define` to create a macro.",
                    },
                    "solution": {
                        "code": "#include <iostream> // Example fix",
                        "explanation": "Fix directive spelling to valid standard C/C++ keyword.",
                        "why_original_failed": f"The compiler failed to recognize '#{bad_word}' as a valid preprocessor instruction, leading to a fatal compilation error.",
                        "why_new_works": "Using the correctly spelled `#include` directive instructs the preprocessor to load the specified header file, allowing the compilation to proceed."
                    }
                })

            # Header typo (e.g. <iosrewa> instead of <iostream>)
            match_header_typo = re.search(r'<\s*(iosrewa|iostrem|iosteam|stido\.h|stdioo\.h|stringh|vectorh)\s*>', stripped)
            if match_header_typo:
                bad_header = match_header_typo.group(1)
                suggested_header = ""
                if "ios" in bad_header: suggested_header = "<iostream>"
                elif "stido" in bad_header or "stdioo" in bad_header: suggested_header = "<stdio.h>"
                elif "stringh" in bad_header: suggested_header = "<string>"
                elif "vectorh" in bad_header: suggested_header = "<vector>"

                issues.append({
                    "id": f"header_typo_{idx}",
                    "rule_id": "COMPILER_HEADER_TYPO",
                    "severity": "CRITICAL",
                    "category": "Compilation Error",
                    "line": idx,
                    "problem": f"Unrecognized standard library header file: <{bad_header}>",
                    "explanation": f"The specified header file `<{bad_header}>` does not match any standard C/C++ library header. This will result in a compilation error because essential declarations (like `cout` or `printf`) will be missing.",
                    "hints": {
                        "hint1": "Inspect the header name inside the angle brackets `<...>` on line " + str(idx) + ". Does it look exactly right?",
                        "hint2": f"Are you trying to include standard input/output streams, string manipulation, or dynamic arrays? For example, standard C++ I/O is in `iostream`.",
                        "hint3": f"Correct the header name to the proper standard library header, such as {suggested_header or '<iostream>'} for C++ streams or `<stdio.h>` for C standard I/O.",
                    },
                    "solution": {
                        "code": f"#include {suggested_header or '<iostream>'} // Example fix",
                        "explanation": "Use the correct standard library header.",
                        "why_original_failed": "An incorrectly named header prevents the compiler from finding the necessary function and class declarations, leading to unresolved symbol errors.",
                        "why_new_works": "Including the correct header file (e.g., `<iostream>`) makes all its declarations available to the compiler, resolving symbol errors and allowing the program to compile."
                    }
                })

            # Missing <iostream> when using cout / cin
            if ("cout" in stripped or "cin" in stripped) and not ("#include <iostream>" in code or "#include <bits/stdc++.h>" in code):
                issues.append({
                    "id": f"missing_iostream_{idx}",
                    "rule_id": "COMPILER_MISSING_IOSTREAM",
                    "severity": "HIGH",
                    "category": "Missing Header",
                    "line": idx,
                    "problem": "Using `cout` or `cin` without including `<iostream>`",
                    "explanation": "The standard C++ stream objects `std::cout` and `std::cin` are declared in the `<iostream>` header. Without including this header, the compiler will not recognize these symbols, leading to compilation errors.",
                    "hints": {
                        "hint1": "Where are `cout` and `cin` typically declared in standard C++?",
                        "hint2": "Check your `#include` statements at the top of the file. Is `iostream` present?",
                        "hint3": "Add `#include <iostream>` at the very beginning of your program file to make `cout` and `cin` available.",
                    },
                    "solution": {
                        "code": "#include <iostream>\n// using namespace std; // Optional, but common",
                        "explanation": "Include `<iostream>` to declare standard stream objects.",
                        "why_original_failed": "The compiler cannot find the definitions or declarations for `cout` or `cin` because their defining header `<iostream>` was not included, causing a compilation failure.",
                        "why_new_works": "Including `<iostream>` provides the necessary declarations for `std::cout`, `std::cin`, and other standard I/O facilities, allowing the program to compile and use them correctly."
                    }
                })

        # Missing semicolon in C, C++, Java
        if lang in ("c", "cpp", "java"):
            # A more robust check might involve parsing, but for regex, focus on common statements
            # Exclude lines that are comments, preprocessor directives, block starts/ends, or function/class definitions
            is_comment_or_preproc = stripped.startswith(("#", "//", "/*", "*"))
            is_block_structural = stripped.endswith(("{", "}", ":", ")")) or stripped.startswith(("public", "private", "protected", "class", "interface", "enum")) or (stripped.startswith("for") and not stripped.endswith(");"))
            is_assignment_or_call = re.match(r'^[a-zA-Z_]\w*\s*[=+\-*/%&|^<>!~]?=.*|^\w+\s*\([^)]*\)\s*;?$', stripped) # e.g. x = 5, myFunc()
            is_return_or_decl = re.match(r'^(return|int|float|double|char|long|short|void|bool|auto|std::string|String|const)\s+.*', stripped)

            if stripped and not is_comment_or_preproc and not is_block_structural:
                # This regex heuristic is still not perfect but catches many cases
                if any(stripped.startswith(k) for k in ("int ", "float ", "double ", "char ", "return ", "cout ", "cin ", "System.out", "auto ", "string ", "vector<", "if (", "while (", "for (")) and not stripped.endswith(";") and not stripped.endswith(")")):
                    if not re.match(r'^(if|while|for|switch|do)\s*\(.*', stripped): # Don't flag control flow headers
                        issues.append({
                            "id": f"missing_semicolon_{idx}",
                            "rule_id": "SYNTAX_MISSING_SEMICOLON",
                            "severity": "HIGH",
                            "category": "Syntax Error",
                            "line": idx,
                            "problem": f"Expected ';' at end of statement on line {idx}",
                            "explanation": f"Statements in {lang.upper()} must be terminated with a semicolon (`;`). Missing semicolons are a common cause of cascade syntax errors, making the compiler unable to correctly parse subsequent lines.",
                            "hints": {
                                "hint1": f"Check the punctuation at the very end of line {idx}. Is there a semicolon where one should be?",
                                "hint2": f"In {lang.upper()}, almost every instruction or declaration needs to end with a semicolon to tell the compiler where one statement finishes and the next begins.",
                                "hint3": "Append a semicolon (`;`) to the end of the statement on this line.",
                            },
                            "solution": {
                                "code": f"{stripped};",
                                "explanation": "Add the required semicolon terminating the statement.",
                                "why_original_failed": "A missing semicolon causes the compiler to misinterpret the code, often leading to a cascade of errors on subsequent lines, preventing successful compilation.",
                                "why_new_works": "Adding the semicolon correctly delineates the end of one statement and the beginning of the next, allowing the compiler to parse the code accurately."
                            }
                        })

        # Java String == Comparison
        if lang in ("java",):
            # Matches `str_var == "literal"` or `str_var == another_str_var`
            if re.search(r'\bString\s+\w+\s*=\s*.*?;', line) or re.search(r'\bString\s+\w+[^;]*;', line): # Simple heuristic to detect string declarations
                match = re.search(r'\b([a-zA-Z_]\w*)\s*==\s*("[^"]*"|\b[a-zA-Z_]\w*\b)', stripped)
                if match and "null" not in stripped and not re.search(r'\b(int|char|boolean|double|float|long|short)\s+[^=]*==', stripped):
                    var1 = match.group(1)
                    var2 = match.group(2)
                    issues.append({
                        "id": f"java_str_equals_{idx}",
                        "rule_id": "BUG_JAVA_STRING_EQUALS",
                        "severity": "HIGH",
                        "category": "Logic Bug",
                        "line": idx,
                        "problem": "Comparing Strings with `==` instead of `.equals()`",
                        "explanation": "In Java, the `==` operator compares object *references* (memory addresses), not their actual character *content*. Two distinct `String` objects with identical content will evaluate to `false` when compared with `==`, leading to incorrect logic.",
                        "hints": {
                            "hint1": "How does Java differentiate between comparing primitive values (like `int`s) and comparing objects (like `String`s)?",
                            "hint2": "The `==` operator checks if two variables point to the *exact same object* in memory. Is that what you intend when comparing string values?",
                            "hint3": "To compare the actual character sequence of `String` objects, you must use the `.equals()` method (e.g., `str1.equals(str2)`). Consider `Objects.equals(str1, str2)` for null-safe comparison.",
                        },
                        "solution": {
                            "code": f"if ({var1}.equals({var2})) // For content comparison",
                            "explanation": "Use `.equals()` to check actual character value equality.",
                            "why_original_failed": "The `==` operator on `String` objects tests for reference identity, which means it returns `true` only if both variables point to the exact same object in memory. This often fails for strings that have the same content but were created independently.",
                            "why_new_works": "The `.equals()` method is designed to compare the character sequences of `String` objects. It returns `true` if and only if the strings have the same sequence of characters, ensuring accurate content comparison."
                        }
                    })

    # Remove duplicates by line and rule_id (rule_id is more stable than problem string)
    unique_issues = []
    seen = set()
    for iss in issues:
        key = (iss["line"], iss["rule_id"])
        if key not in seen:
            seen.add(key)
            unique_issues.append(iss)

    # Calculate score and deductions using the new consolidated function
    score_analysis_results = _calculate_score_and_deductions(unique_issues)
    
    return {
        "issues": unique_issues,
        **score_analysis_results # Unpack score, score_breakdown, deductions, summary, basis
    }
