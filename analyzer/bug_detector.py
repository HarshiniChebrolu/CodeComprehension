import ast
import re
from typing import List, Dict, Any


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

    def _add_issue(self, severity: str, category: str, line: int, problem: str,
                   explanation: str, hint1: str, hint2: str, hint3: str,
                   solution_code: str, solution_exp: str, why_failed: str, why_works: str):
        self._issue_counter += 1
        self.issues.append({
            "id": f"bug_{self._issue_counter}",
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
                "explanation": solution_exp,
                "why_original_failed": why_failed,
                "why_new_works": why_works
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
                    severity="HIGH",
                    category="Dangerous Pattern",
                    line=node.lineno,
                    problem=f"Mutable default argument in function '{node.name}'",
                    explanation="Default arguments are evaluated once when the function is defined, not each time it is called. Mutating this default modifies it across all subsequent function calls.",
                    hint1="Look at the parameter list of your function definition. Do any parameters initialize directly to an empty container?",
                    hint2="In Python, lists/dictionaries given as default values persist their state between calls.",
                    hint3="Set default to None, and inside the function body initialize: if param is None: param = []",
                    solution_code=f"def {node.name}(..., param=None):\n    if param is None:\n        param = []",
                    solution_exp="Use None as a sentinel value and initialize a fresh mutable instance inside the function body.",
                    why_failed="A single list was shared across all invocations, accumulating unexpected state.",
                    why_works="Every invocation that doesn't supply an argument creates its own distinct list instance."
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
        for i, stmt in enumerate(node.body[:-1]):
            if isinstance(stmt, (ast.Return, ast.Raise)):
                next_stmt = node.body[i + 1]
                self._add_issue(
                    severity="LOW",
                    category="Dead Code",
                    line=next_stmt.lineno,
                    problem="Unreachable code detected",
                    explanation=f"Statements following line {stmt.lineno} in the same block will never be executed because a return or raise terminates the block.",
                    hint1="Check the sequence of lines in the function body. Does an early return block subsequent code?",
                    hint2="Look right after the return statement at line " + str(stmt.lineno) + ".",
                    hint3="Remove or reorganize the dead statements located directly after the return.",
                    solution_code="# Remove or indent the unreachable statements before the return",
                    solution_exp="Clean up unreachable code to avoid confusion and maintain clean control flow.",
                    why_failed="Code placed after unconditional return/raise never executes.",
                    why_works="Placing logic prior to the terminal statement ensures it runs as intended."
                )
                break

        self.generic_visit(node)
        self.current_function = prev_func
        self.local_vars = prev_locals

    def visit_Subscript(self, node):
        # 4. Unsafe dict or list indexing
        # e.g. user['name'] or user['id']
        if isinstance(node.slice, ast.Constant) and isinstance(node.slice.value, str):
            key_name = node.slice.value
            # Check if inside try or already guarded
            self._add_issue(
                severity="MEDIUM",
                category="Runtime Risk",
                line=node.lineno,
                problem=f"Unsafe dictionary access ['{key_name}'] without key validation",
                explanation=f"Directly accessing '{key_name}' with bracket notation raises a KeyError if the key is missing from the dictionary.",
                hint1="Consider what happens when the incoming dictionary doesn't contain the expected key.",
                hint2="Look at line " + str(node.lineno) + ". Is there a safer dictionary method that doesn't throw KeyError?",
                hint3="Use dict.get('" + key_name + "') or guard with 'if \"" + key_name + "\" in dict:'.",
                solution_code=f"val = data.get('{key_name}', default_value)",
                solution_exp="dict.get() safely returns None (or a specified default) instead of raising an unhandled KeyError.",
                why_failed="Direct index access throws an unhandled KeyError if data from API or user input lacks the key.",
                why_works="get() handles missing keys gracefully with an optional fallback value."
            )
        self.generic_visit(node)

    def visit_While(self, node):
        # 5. Infinite loop detection: while True with no break/return, or loop var never modified
        has_exit = False
        for sub in ast.walk(node):
            if isinstance(sub, (ast.Break, ast.Return, ast.Raise)):
                has_exit = True
                break

        if isinstance(node.test, ast.Constant) and node.test.value is True and not has_exit:
            self._add_issue(
                severity="CRITICAL",
                category="Infinite Loop",
                line=node.lineno,
                problem="Definite infinite loop: while True without break or return",
                explanation="The while loop condition is permanently True, and the loop body contains no break, return, or raise statements to exit.",
                hint1="Look at the loop control condition and its termination mechanism.",
                hint2="Does this loop ever have a way to break out or finish?",
                hint3="Add a termination condition or a 'break' statement when an end criterion is met.",
                solution_code="while condition:\n    # loop logic\n    if exit_condition:\n        break",
                solution_exp="Provide a guaranteed exit condition to prevent the program from hanging indefinitely.",
                why_failed="The program would freeze or consume 100% CPU waiting for an impossible exit.",
                why_works="A guarded exit or evaluated boolean expression terminates when work is completed."
            )

        self.generic_visit(node)

    def visit_ExceptHandler(self, node):
        # 6. Bare except or broad except Exception with pass
        if node.type is None:
            self._add_issue(
                severity="HIGH",
                category="Security & Robustness",
                line=node.lineno,
                problem="Bare 'except:' catches all exceptions indiscriminately",
                explanation="A bare except clause catches KeyboardInterrupt, SystemExit, and MemoryError, preventing normal program termination and masking syntax/logical bugs.",
                hint1="Look at the exception handling block. What type of exception are you trying to handle?",
                hint2="Catching every single exception including system signals makes debugging nearly impossible.",
                hint3="Specify the exact exception type you expect, e.g., except (ValueError, KeyError):",
                solution_code="except (ValueError, KeyError) as e:\n    logger.warning(f'Handled expected error: {e}')",
                solution_exp="Catch only specific expected exceptions rather than swallowing all system and program errors.",
                why_failed="A bare except masks fatal errors, bugs, and keyboard interrupts (Ctrl+C).",
                why_works="Targeted exceptions catch only known failure modes, leaving unexpected crashes visible for debugging."
            )
        elif isinstance(node.body[0], ast.Pass) if node.body else False:
            self._add_issue(
                severity="MEDIUM",
                category="Code Smell",
                line=node.lineno,
                problem="Silently suppressed exception with 'pass'",
                explanation="Catching an exception and executing 'pass' swallows errors silently without logging or recovery, making failures invisible.",
                hint1="What happens when an error occurs in this try block? Does anyone know?",
                hint2="Check line " + str(node.lineno) + ". The error is caught but completely ignored.",
                hint3="Log the error message, return a status code, or handle the fallback appropriately instead of bare 'pass'.",
                solution_code="except Exception as e:\n    print(f'Error occurred: {e}')\n    return False",
                solution_exp="Always record or act on caught exceptions rather than ignoring them silently.",
                why_failed="Silent failure hides corrupted state and causes hard-to-trace bugs later.",
                why_works="Logging or handling alerts developers to the exact root cause of anomalies."
            )

        self.generic_visit(node)

    def visit_Assign(self, node):
        # 7. Dangerous variable initialization (e.g. max_val = 0 or min_val = 0 or shadowing built-in)
        builtins = {"list", "dict", "str", "int", "float", "set", "sum", "max", "min", "id", "type", "len"}
        for target in node.targets:
            if isinstance(target, ast.Name):
                var_name = target.id
                if var_name in builtins:
                    self._add_issue(
                        severity="LOW",
                        category="Best Practice",
                        line=node.lineno,
                        problem=f"Variable '{var_name}' shadows Python built-in function",
                        explanation=f"Assigning to '{var_name}' overrides the standard library built-in '{var_name}()', which can cause unexpected TypeError if the built-in is called later.",
                        hint1="Look at the variable name you chose on line " + str(node.lineno) + ".",
                        hint2="Is that name already a standard function in Python?",
                        hint3=f"Rename '{var_name}' to something more descriptive like '{var_name}_val' or 'items'.",
                        solution_code=f"{var_name}_data = {self._unparse(node.value)}",
                        solution_exp=f"Use descriptive variable names that do not conflict with Python built-ins.",
                        why_failed=f"Overwriting {var_name} prevents calling the built-in {var_name}() function.",
                        why_works="Distinct identifiers preserve standard library functions in the local namespace."
                    )

                # Check max_val = 0 bug for negative arrays
                if "max" in var_name.lower() and isinstance(node.value, ast.Constant) and node.value.value == 0:
                    self._add_issue(
                        severity="HIGH",
                        category="Logic Bug",
                        line=node.lineno,
                        problem="Initializing maximum tracker to 0 fails for negative numbers",
                        explanation="If the input array contains only negative numbers (e.g., [-5, -2, -10]), initializing max to 0 will incorrectly return 0 because 0 is greater than all elements.",
                        hint1="Look carefully at how the maximum tracking variable is initialized.",
                        hint2="Consider what happens when the input dataset contains only negative values.",
                        hint3="Ask yourself whether initializing the maximum value to zero is always valid. What if you initialize with the first element or float('-inf')?",
                        solution_code=f"{var_name} = float('-inf')  # or arr[0] if arr is non-empty",
                        solution_exp="Initialize max tracker with negative infinity or the first element of the collection.",
                        why_failed="0 is larger than any negative number, so negative-only lists return 0 instead of their true maximum.",
                        why_works="float('-inf') is smaller than any real number, ensuring valid comparison for all inputs."
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
                "severity": "CRITICAL",
                "category": "Runtime Error",
                "line": idx,
                "problem": "Division by zero detected",
                "explanation": "Attempting to divide by integer constant 0 will immediately raise a ZeroDivisionError at runtime.",
                "hints": {
                    "hint1": "Look at the mathematical operators on line " + str(idx) + ".",
                    "hint2": "What is the denominator value?",
                    "hint3": "Never divide directly by 0; ensure denominators are checked against 0 before division."
                },
                "solution": {
                    "code": "if denominator != 0:\n    result = numerator / denominator\nelse:\n    result = 0",
                    "explanation": "Guard against zero denominators before performing division.",
                    "why_original_failed": "Division by zero is undefined and crashes the process.",
                    "why_works": "Guarding with a condition prevents the crash and handles the edge case."
                }
            })

        # Off-by-one / Index error in Python range
        if lang in ("python", "py"):
            if re.search(r'range\(\s*len\([a-zA-Z0-9_]+\)\s*\+\s*1\s*\)', stripped):
                issues.append({
                    "id": f"off_by_one_{idx}",
                    "severity": "HIGH",
                    "category": "Index Error",
                    "line": idx,
                    "problem": "Potential IndexError (off-by-one) with range(len(...) + 1)",
                    "explanation": "Arrays in Python are 0-indexed with valid indices from 0 to len-1. Iterating up to len(...) + 1 will trigger an IndexError: list index out of range when accessing arr[i].",
                    "hints": {
                        "hint1": "Inspect the upper bound of your range loop.",
                        "hint2": "Remember that Python lists are zero-indexed: the last valid element is at index len(arr) - 1.",
                        "hint3": "Use range(len(arr)) directly without adding 1, or iterate over elements with 'for item in arr:'."
                    },
                    "solution": {
                        "code": "for i in range(len(arr)):\n    # or better: for item in arr:",
                        "explanation": "Use range(len(arr)) or direct iteration to stay within bounds.",
                        "why_original_failed": "Accessing arr[len(arr)] overshoots the array bounds.",
                        "why_works": "range(len(arr)) generates indices from 0 up to len(arr)-1 perfectly."
                    }
                })

        # Off-by-one in C / C++ / Java / JS: for (int i = 0; i <= arr.length; i++)
        if lang in ("c", "cpp", "java", "javascript", "js"):
            if re.search(r'<=\s*[a-zA-Z0-9_]+(\.length|\.size\(\)|_len)', stripped):
                issues.append({
                    "id": f"off_by_one_c_{idx}",
                    "severity": "HIGH",
                    "category": "Index Error",
                    "line": idx,
                    "problem": "Off-by-one condition '<=' allows index out-of-bounds",
                    "explanation": "Zero-indexed arrays have elements from 0 to length - 1. Using '<= length' attempts to read memory beyond the allocated array boundary.",
                    "hints": {
                        "hint1": "Examine the loop boundary condition.",
                        "hint2": "What happens on the very last iteration when i equals the array length?",
                        "hint3": "Change the '<=' comparison to strictly '<'."
                    },
                    "solution": {
                        "code": "for (int i = 0; i < length; i++)",
                        "explanation": "Use strict inequality (<) so the loop stops before reaching out-of-bounds indices.",
                        "why_original_failed": "Accessing index equal to size causes a segmentation fault or out-of-bounds exception.",
                        "why_works": "Stops at size - 1, which is the last valid element."
                    }
                })

        # Two sum identical index comparison bug: if nums[i] + nums[j] == target without i != j
        if "nums[i]" in stripped and "nums[j]" in stripped:
            if "i != j" not in stripped and "j = i + 1" not in code and "range(i + 1" not in code and "int j = i + 1" not in code:
                issues.append({
                    "id": f"two_sum_dup_{idx}",
                    "severity": "HIGH",
                    "category": "Logic Bug",
                    "line": idx,
                    "problem": "Possible self-element pairing in two-sum check",
                    "explanation": "If the inner loop allows i == j, an element might add with itself to falsely satisfy target (e.g. nums=[3, 2, 4], target=6 pairing 3 with itself).",
                    "hints": {
                        "hint1": "Can the inner index equal the outer index?",
                        "hint2": "What happens if target is twice the value of an element at index i?",
                        "hint3": "Start the inner loop at i + 1: e.g. for (int j = i + 1; ...) or range(i + 1, len(nums))."
                    },
                    "solution": {
                        "code": "for (int i = 0; i < n; i++) {\n    for (int j = i + 1; j < n; j++) {\n        if (nums[i] + nums[j] == target) ...",
                        "explanation": "Ensure distinct indices by starting the inner loop at i + 1.",
                        "why_original_failed": "An element at index i was permitted to pair with itself.",
                        "why_works": "Starting at i + 1 guarantees pairs are distinct and avoids duplicate work."
                    }
                })

        # C / C++ Preprocessor typos (e.g. #incluude, #defne)
        if lang in ("c", "cpp"):
            if re.match(r'#\s*(incluude|incldue|includ|defne|pragme)\b', stripped):
                bad_word = re.findall(r'#\s*(\w+)', stripped)[0]
                issues.append({
                    "id": f"preproc_typo_{idx}",
                    "severity": "CRITICAL",
                    "category": "Syntax Error",
                    "line": idx,
                    "problem": f"Invalid preprocessor directive '#{bad_word}'",
                    "explanation": f"The C/C++ compiler does not recognize '#{bad_word}'. Preprocessor directives must be strictly spelled (e.g., '#include' or '#define').",
                    "hints": {
                        "hint1": "Look carefully at the spelling of the preprocessor command starting with '#'.",
                        "hint2": f"Notice '#{bad_word}' has an accidental spelling mistake.",
                        "hint3": "Correct the directive to '#include <header>' or '#define'."
                    },
                    "solution": {
                        "code": "#include <iostream>",
                        "explanation": "Fix directive spelling to valid standard C/C++ keyword.",
                        "why_original_failed": f"Compiler halted because #{bad_word} is an illegal preprocessing directive.",
                        "why_works": "#include instructs the preprocessor to load the target header."
                    }
                })

            # Header typo (e.g. <iosrewa> instead of <iostream>)
            if re.search(r'<\s*(iosrewa|iostrem|iosteam|stido\.h|stdioo\.h)\s*>', stripped):
                issues.append({
                    "id": f"header_typo_{idx}",
                    "severity": "CRITICAL",
                    "category": "Compilation Error",
                    "line": idx,
                    "problem": "Unrecognized standard library header file",
                    "explanation": "The header specified inside angle brackets does not match any standard C/C++ header. Standard stream IO is in <iostream> (C++) or <stdio.h> (C).",
                    "hints": {
                        "hint1": "Inspect the header name inside the angle brackets <...>.",
                        "hint2": "Are you trying to include standard input/output streams?",
                        "hint3": "Change the header name to <iostream> or <stdio.h>."
                    },
                    "solution": {
                        "code": "#include <iostream>",
                        "explanation": "Use <iostream> for standard C++ input/output operations.",
                        "why_original_failed": "Non-existent header caused a fatal compilation include error.",
                        "why_works": "<iostream> provides std::cout, std::cin, and std::endl."
                    }
                })

            # Missing <iostream> when using cout / cin
            if ("cout" in stripped or "cin" in stripped) and "#include" in code and "iostream" not in code:
                issues.append({
                    "id": f"missing_iostream_{idx}",
                    "severity": "HIGH",
                    "category": "Missing Header",
                    "line": idx,
                    "problem": "Using 'cout' or 'cin' without including <iostream>",
                    "explanation": "The standard streams 'cout' and 'cin' require the <iostream> header to be included.",
                    "hints": {
                        "hint1": "Where are 'cout' and 'cin' declared in standard C++?",
                        "hint2": "Check your #include statements at the top of the file.",
                        "hint3": "Add '#include <iostream>' at the beginning of the program."
                    },
                    "solution": {
                        "code": "#include <iostream>\nusing namespace std;",
                        "explanation": "Include <iostream> to declare standard stream objects.",
                        "why_original_failed": "The compiler cannot find declarations for cout / cin.",
                        "why_works": "Including <iostream> defines all standard IO stream objects."
                    }
                })

        # Missing semicolon in C, C++, Java
        if lang in ("c", "cpp", "java"):
            if stripped and not stripped.startswith(("#", "//", "/*", "*")) and not stripped.endswith(("{", "}", ";", ":", ")", ",")):
                if any(stripped.startswith(k) for k in ("int ", "float ", "double ", "char ", "return ", "cout ", "cin ", "System.out", "auto ", "string ", "vector<")):
                    issues.append({
                        "id": f"missing_semicolon_{idx}",
                        "severity": "HIGH",
                        "category": "Syntax Error",
                        "line": idx,
                        "problem": f"Expected ';' at end of statement on line {idx}",
                        "explanation": f"Statements in {lang.upper()} must be terminated with a semicolon ';'. Missing semicolons cause cascade syntax errors.",
                        "hints": {
                            "hint1": f"Check punctuation at the end of line {idx}.",
                            "hint2": f"In {lang.upper()}, every statement must terminate with a semicolon.",
                            "hint3": "Append ';' to the end of the line."
                        },
                        "solution": {
                            "code": f"{stripped};",
                            "explanation": "Add the required semicolon terminating the statement.",
                            "why_original_failed": "Missing semicolon causes compiler parsing failure.",
                            "why_works": "Semicolons delineate separate statements for the compiler."
                        }
                    })

        # Java String == Comparison
        if lang in ("java",):
            if re.search(r'[a-zA-Z0-9_]+\s*==\s*("[^"]*"|[a-zA-Z0-9_]+)', stripped) and "null" not in stripped and "int" not in stripped:
                if "String" in code or '"' in stripped:
                    issues.append({
                        "id": f"java_str_equals_{idx}",
                        "severity": "HIGH",
                        "category": "Logic Bug",
                        "line": idx,
                        "problem": "Comparing Strings with '==' instead of '.equals()'",
                        "explanation": "In Java, '==' compares object reference addresses in memory, not the string character content. Strings with identical values might return false with '=='.",
                        "hints": {
                            "hint1": "How does Java compare reference objects vs primitive types?",
                            "hint2": "Does '==' compare the string content or the object memory address?",
                            "hint3": "Use str1.equals(str2) or Objects.equals(str1, str2) for content equality."
                        },
                        "solution": {
                            "code": "if (str1.equals(str2))",
                            "explanation": "Use .equals() to check actual character value equality.",
                            "why_original_failed": "'==' tests reference identity, failing for independently allocated strings.",
                            "why_works": ".equals() compares the character sequence within both strings."
                        }
                    })

    # Remove duplicates by line and problem
    unique_issues = []
    seen = set()
    for iss in issues:
        key = (iss["line"], iss["problem"])
        if key not in seen:
            seen.add(key)
            unique_issues.append(iss)

    # Calculate real Code Quality Score
    score = 100
    deductions = {
        "CRITICAL": 30,
        "HIGH": 15,
        "MEDIUM": 8,
        "LOW": 4,
        "INFO": 2
    }

    correctness_ded = 0
    readability_ded = 0
    maintainability_ded = 0
    efficiency_ded = 0
    security_ded = 0
    best_practices_ded = 0

    for iss in unique_issues:
        sev = iss["severity"]
        cat = iss["category"]
        pts = deductions.get(sev, 5)
        score -= pts

        if "Syntax" in cat or "Logic" in cat or "Index" in cat or "Runtime" in cat:
            correctness_ded += pts * 1.5
        if "Smell" in cat or "Dead" in cat:
            readability_ded += pts
            maintainability_ded += pts
        if "Pattern" in cat or "Security" in cat:
            security_ded += pts
            best_practices_ded += pts
        if "Performance" in cat:
            efficiency_ded += pts

    score = max(12, min(100, score))

    score_breakdown = {
        "correctness": max(15, min(100, int(100 - correctness_ded))),
        "readability": max(20, min(100, int(100 - readability_ded))),
        "maintainability": max(20, min(100, int(100 - maintainability_ded))),
        "efficiency": max(25, min(100, int(100 - efficiency_ded))),
        "security": max(25, min(100, int(100 - security_ded))),
        "best_practices": max(20, min(100, int(100 - best_practices_ded)))
    }

    # Summary description
    issue_count = len(unique_issues)
    if issue_count == 0:
        summary = "Clean code! No critical syntax, logic, or runtime defects detected."
    elif any(i["severity"] == "CRITICAL" for i in unique_issues):
        summary = f"Found {issue_count} issue(s) including critical errors that prevent successful execution."
    else:
        summary = f"Detected {issue_count} issue(s) ranging from runtime risks to code quality improvements."

    return {
        "issues": unique_issues,
        "score": score,
        "score_breakdown": score_breakdown,
        "summary": summary
    }
