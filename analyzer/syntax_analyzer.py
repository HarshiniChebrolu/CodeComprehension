import ast
import traceback
import re


def analyze_syntax(code: str, language: str = "python") -> dict:
    """
    Performs thorough syntax and formatting validation on the submitted code.
    Returns:
        {
            "valid": bool,
            "error": str or None,
            "line": int or None,
            "column": int or None,
            "snippet": str or None,
            "details": str or None,
            "ast_obj": AST object or None (Python only)
        }
    """
    lang = language.lower()

    if not code or not code.strip():
        return {
            "valid": False,
            "error": "Empty code submission",
            "line": 1,
            "column": 0,
            "snippet": "",
            "details": "Please provide code before running review.",
            "ast_obj": None
        }

    if lang in ("python", "py"):
        try:
            tree = ast.parse(code)
            return {
                "valid": True,
                "error": None,
                "line": None,
                "column": None,
                "snippet": None,
                "details": "Python syntax verified successfully via AST parser.",
                "has_ast": True
            }
        except SyntaxError as e:
            lines = code.split("\n")
            line_idx = (e.lineno - 1) if e.lineno and e.lineno <= len(lines) else 0
            snippet = lines[line_idx] if 0 <= line_idx < len(lines) else ""
            return {
                "valid": False,
                "error": f"SyntaxError: {e.msg}",
                "line": e.lineno or 1,
                "column": e.offset or 0,
                "snippet": snippet,
                "details": f"Python syntax error at line {e.lineno or 1}: {e.msg}. Please check colons, indentation, and matching parentheses/quotes.",
                "has_ast": False
            }
        except Exception as e:
            return {
                "valid": False,
                "error": str(e),
                "line": 1,
                "column": 0,
                "snippet": "",
                "details": f"Failed to parse Python code: {str(e)}",
                "has_ast": False
            }
    else:
        # Static bracket and quote validation for C, C++, Java, JavaScript
        bracket_pairs = {'(': ')', '[': ']', '{': '}'}
        stack = []
        lines = code.split("\n")

        for line_num, line in enumerate(lines, start=1):
            # Strip string literals and single line comments for bracket check
            cleaned_line = re.sub(r'//.*$', '', line)
            cleaned_line = re.sub(r'".*?"|\'.*?\'', '', cleaned_line)

            for col, ch in enumerate(cleaned_line, start=1):
                if ch in bracket_pairs.keys():
                    stack.append((ch, line_num, col))
                elif ch in bracket_pairs.values():
                    if not stack:
                        return {
                            "valid": False,
                            "error": f"Unmatched closing bracket '{ch}'",
                            "line": line_num,
                            "column": col,
                            "snippet": line,
                            "details": f"Encountered unexpected closing bracket '{ch}' without matching opening bracket.",
                            "has_ast": False
                        }
                    open_ch, open_line, open_col = stack.pop()
                    if bracket_pairs[open_ch] != ch:
                        return {
                            "valid": False,
                            "error": f"Mismatched bracket: expected '{bracket_pairs[open_ch]}', found '{ch}'",
                            "line": line_num,
                            "column": col,
                            "snippet": line,
                            "details": f"Opening bracket '{open_ch}' at line {open_line} does not match '{ch}' at line {line_num}.",
                            "has_ast": False
                        }

        if stack:
            open_ch, open_line, open_col = stack[-1]
            return {
                "valid": False,
                "error": f"Unclosed bracket '{open_ch}'",
                "line": open_line,
                "column": open_col,
                "snippet": lines[open_line - 1] if open_line <= len(lines) else "",
                "details": f"Bracket '{open_ch}' opened at line {open_line} was never closed.",
                "has_ast": False
            }

        return {
            "valid": True,
            "error": None,
            "line": None,
            "column": None,
            "snippet": None,
            "details": f"{language.upper()} syntax structure verified (bracket pairs and nesting intact).",
            "ast_obj": None
        }
