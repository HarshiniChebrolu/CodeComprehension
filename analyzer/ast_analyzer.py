import ast
from typing import Dict, Any, List


class ASTInspector(ast.NodeVisitor):
    def __init__(self):
        self.functions = []
        self.classes = []
        self.imports = []
        self.flow_nodes = []
        self.flow_edges = []
        self._node_id = 0
        self.max_nesting_depth = 0
        self._current_depth = 0
        self.total_loops = 0
        self.total_branches = 0
        self.total_calls = 0

    def _get_id(self):
        self._node_id += 1
        return self._node_id

    def _get_expr_str(self, node):
        try:
            return ast.unparse(node)
        except Exception:
            return str(type(node).__name__)

    def visit_FunctionDef(self, node):
        parent_depth = self._current_depth
        self._current_depth += 1
        self.max_nesting_depth = max(self.max_nesting_depth, self._current_depth)

        node_id = self._get_id()
        args = [a.arg for a in node.args.args]
        func_info = {
            "id": node_id,
            "name": node.name,
            "args": args,
            "line": node.lineno,
            "end_line": getattr(node, "end_lineno", node.lineno),
            "docstring": ast.get_docstring(node),
            "type": "FunctionDef"
        }
        self.functions.append(func_info)

        flow_item = {
            "id": node_id,
            "category": "function",
            "type": "Function",
            "label": f"def {node.name}({', '.join(args)})",
            "line": node.lineno,
            "description": f"Function entry point with {len(args)} parameters"
        }
        self.flow_nodes.append(flow_item)

        prev_id = node_id
        for child in node.body:
            child_id = self._process_statement(child, prev_id)
            if child_id:
                prev_id = child_id

        self._current_depth = parent_depth

    def _process_statement(self, node, parent_id=None):
        node_id = self._get_id()
        item = None

        if isinstance(node, ast.For):
            self.total_loops += 1
            target = self._get_expr_str(node.target)
            iter_src = self._get_expr_str(node.iter)
            item = {
                "id": node_id,
                "category": "loop",
                "type": "For Loop",
                "label": f"for {target} in {iter_src}",
                "line": node.lineno,
                "description": f"Iterates over {iter_src}"
            }
        elif isinstance(node, ast.While):
            self.total_loops += 1
            test_str = self._get_expr_str(node.test)
            item = {
                "id": node_id,
                "category": "loop",
                "type": "While Loop",
                "label": f"while {test_str}",
                "line": node.lineno,
                "description": f"Repeats while ({test_str}) is true"
            }
        elif isinstance(node, ast.If):
            self.total_branches += 1
            test_str = self._get_expr_str(node.test)
            item = {
                "id": node_id,
                "category": "condition",
                "type": "Condition",
                "label": f"if {test_str}",
                "line": node.lineno,
                "description": f"Conditional check: {test_str}"
            }
        elif isinstance(node, ast.Return):
            val_str = self._get_expr_str(node.value) if node.value else "None"
            item = {
                "id": node_id,
                "category": "return",
                "type": "Return",
                "label": f"return {val_str}",
                "line": node.lineno,
                "description": f"Terminates function returning {val_str}"
            }
        elif isinstance(node, ast.Expr) and isinstance(node.value, ast.Call):
            self.total_calls += 1
            func_name = self._get_expr_str(node.value.func)
            item = {
                "id": node_id,
                "category": "call",
                "type": "Function Call",
                "label": f"{func_name}(...)",
                "line": node.lineno,
                "description": f"Invokes function {func_name}"
            }
        elif isinstance(node, ast.Assign):
            targets = ", ".join(self._get_expr_str(t) for t in node.targets)
            val = self._get_expr_str(node.value)
            item = {
                "id": node_id,
                "category": "assign",
                "type": "Assignment",
                "label": f"{targets} = {val}",
                "line": node.lineno,
                "description": f"Sets {targets}"
            }

        if item:
            self.flow_nodes.append(item)
            if parent_id is not None:
                self.flow_edges.append({"from": parent_id, "to": node_id})

            # Recurse into nested blocks
            last_inner_id = node_id
            if hasattr(node, "body") and isinstance(node.body, list):
                for sub in node.body:
                    res = self._process_statement(sub, last_inner_id)
                    if res:
                        last_inner_id = res

            if hasattr(node, "orelse") and isinstance(node.orelse, list) and node.orelse:
                else_id = self._get_id()
                self.flow_nodes.append({
                    "id": else_id,
                    "category": "condition",
                    "type": "Else Branch",
                    "label": "else:",
                    "line": node.orelse[0].lineno if hasattr(node.orelse[0], "lineno") else node.lineno,
                    "description": "Alternative execution branch"
                })
                self.flow_edges.append({"from": node_id, "to": else_id})
                last_else_id = else_id
                for sub in node.orelse:
                    res = self._process_statement(sub, last_else_id)
                    if res:
                        last_else_id = res

            return node_id
        return None

    def visit_ClassDef(self, node):
        self.classes.append({
            "name": node.name,
            "line": node.lineno,
            "bases": [self._get_expr_str(b) for b in node.bases]
        })
        self.generic_visit(node)

    def visit_Import(self, node):
        for alias in node.names:
            self.imports.append(alias.name)

    def visit_ImportFrom(self, node):
        module = node.module or ""
        for alias in node.names:
            self.imports.append(f"{module}.{alias.name}")


def analyze_ast(code: str, language: str = "python") -> Dict[str, Any]:
    """
    Produces clean, structured AST data for diagrams and structural insight.
    """
    lang = language.lower()
    if lang not in ("python", "py"):
        # Heuristic AST breakdown for non-python code
        return _non_python_ast_summary(code, language)

    try:
        tree = ast.parse(code)
        inspector = ASTInspector()
        inspector.visit(tree)

        # Build clean flow chain pipeline text
        flow_chain = []
        for n in inspector.flow_nodes[:8]:  # Top representative steps
            flow_chain.append({
                "type": n["type"],
                "label": n["label"],
                "category": n["category"],
                "line": n["line"]
            })

        return {
            "success": True,
            "language": "python",
            "functions": inspector.functions,
            "classes": inspector.classes,
            "imports": inspector.imports,
            "flow_nodes": inspector.flow_nodes[:20],  # Guard against massive trees
            "flow_edges": inspector.flow_edges[:30],
            "flow_chain": flow_chain,
            "metrics": {
                "functions_count": len(inspector.functions),
                "loops_count": inspector.total_loops,
                "branches_count": inspector.total_branches,
                "calls_count": inspector.total_calls,
                "max_nesting_depth": inspector.max_nesting_depth
            }
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "flow_nodes": [],
            "flow_edges": [],
            "flow_chain": [],
            "metrics": {
                "functions_count": 0,
                "loops_count": 0,
                "branches_count": 0,
                "calls_count": 0,
                "max_nesting_depth": 0
            }
        }


def _non_python_ast_summary(code: str, language: str) -> Dict[str, Any]:
    # Language mismatch detection
    if language in ("java", "c", "cpp"):
        for line in code.split("\n"):
            stripped = line.strip()
            if re.match(r'^def\s+[a-zA-Z_]\w*\s*\(', stripped) or stripped == "pass":
                return {
                    "success": False,
                    "error": f"Language mismatch: Python syntax detected in {language.upper()} submission.",
                    "language": language,
                    "is_heuristic": True,
                    "structure_type": "heuristic_structural_outline",
                    "functions": [],
                    "classes": [],
                    "imports": [],
                    "flow_nodes": [],
                    "flow_edges": [],
                    "flow_chain": [],
                    "metrics": {
                        "functions_count": 0,
                        "loops_count": 0,
                        "branches_count": 0,
                        "calls_count": 0,
                        "max_nesting_depth": 0
                    }
                }

    lines = code.split("\n")
    flow_nodes = []
    edges = []
    functions = []
    imports = []
    classes = []
    node_id = 1

    for idx, line in enumerate(lines, start=1):
        stripped = line.strip()
        if stripped.startswith("//") or stripped.startswith("/*") or not stripped:
            continue

        category = None
        node_type = None

        if stripped.startswith("#include") or stripped.startswith("import ") or stripped.startswith("using namespace"):
            category = "import"
            node_type = "Include / Import"
            imports.append(stripped)
        elif "class " in stripped and "{" in stripped:
            category = "class"
            node_type = "Class Def"
            cls_name = stripped.split("class ")[1].split("{")[0].split(":")[0].strip()
            classes.append({"name": cls_name, "line": idx})
        elif "for (" in stripped or "for(" in stripped:
            category = "loop"
            node_type = "For Loop"
        elif "while (" in stripped or "while(" in stripped:
            category = "loop"
            node_type = "While Loop"
        elif "if (" in stripped or "if(" in stripped:
            category = "condition"
            node_type = "Condition"
        elif "return " in stripped or stripped.startswith("return;"):
            category = "return"
            node_type = "Return"
        elif any(stripped.startswith(k) for k in ("int ", "void ", "function ", "public ", "double ", "char ", "bool ", "auto ", "string ", "vector<")):
            if "(" in stripped and ")" in stripped:
                category = "function"
                node_type = "Function"
                func_name = stripped.split("(")[0].split()[-1].replace("*", "").replace("&", "")
                functions.append({"name": func_name, "line": idx, "args": [], "type": "Function"})

        if category and len(flow_nodes) < 20:
            node_item = {
                "id": node_id,
                "category": category,
                "type": node_type,
                "label": stripped[:45] + ("..." if len(stripped) > 45 else ""),
                "line": idx,
                "description": f"{node_type} at line {idx}"
            }
            flow_nodes.append(node_item)
            if node_id > 1:
                edges.append({"from": node_id - 1, "to": node_id})
            node_id += 1

    return {
        "success": True,
        "language": language,
        "is_heuristic": True,
        "structure_type": "heuristic_structural_outline",
        "functions": functions,
        "classes": classes,
        "imports": imports,
        "flow_nodes": flow_nodes,
        "flow_edges": edges,
        "flow_chain": flow_nodes[:7],
        "metrics": {
            "functions_count": len(functions),
            "loops_count": sum(1 for n in flow_nodes if n["category"] == "loop"),
            "branches_count": sum(1 for n in flow_nodes if n["category"] == "condition"),
            "calls_count": len(imports),
            "max_nesting_depth": max(1, sum(1 for n in flow_nodes if n["category"] == "loop") + 1)
        }
    }
