import re
from typing import Dict, Any, List, Optional
from ai.base import ReviewProvider
from ai.models import ExplanationModel


class OfflineProvider(ReviewProvider):
    """
    Deterministic, rule-based static analysis mentor provider.
    Runs entirely locally without external network dependencies or API keys.
    Accurately identifies its engine so users know it is rule-based.
    """

    @property
    def name(self) -> str:
        return "CodeComprehension Rule Engine (Offline)"

    def generate_explanation(
        self,
        code: str,
        language: str = "python",
        context_issues: Optional[List[Dict[str, Any]]] = None
    ) -> ExplanationModel:
        lang = language.lower().strip()
        code_lower = code.lower()

        # 1. Detect Functions & Signatures across languages
        key_funcs = []
        if lang in ("python", "py"):
            funcs = re.findall(r'def\s+([a-zA-Z0-9_]+)\s*\((.*?)\)', code)
            for f_name, f_params in funcs:
                key_funcs.append(f"def {f_name}({f_params})")
        elif lang in ("cpp", "c++", "c"):
            cpp_funcs = re.findall(r'(\b[a-zA-Z0-9_<>\s*&]+?\b)\s+([a-zA-Z0-9_]+)\s*\(([^)]*)\)\s*\{', code)
            for ret_type, f_name, f_params in cpp_funcs:
                ret_clean = ret_type.strip().split()[-1] if ret_type.strip() else ""
                if f_name not in ("if", "for", "while", "switch", "catch"):
                    key_funcs.append(f"{ret_clean} {f_name}({f_params.strip()})")
        elif lang == "java":
            java_funcs = re.findall(r'(?:public|private|protected)?\s*(?:static)?\s*([a-zA-Z0-9_<>[\]]+)\s+([a-zA-Z0-9_]+)\s*\(([^)]*)\)\s*\{', code)
            for ret_type, f_name, f_params in java_funcs:
                if f_name not in ("if", "for", "while", "switch", "catch"):
                    key_funcs.append(f"{ret_type} {f_name}({f_params.strip()})")
        elif lang in ("javascript", "js"):
            js_funcs = re.findall(r'function\s+([a-zA-Z0-9_]+)\s*\((.*?)\)', code)
            for f_name, f_params in js_funcs:
                key_funcs.append(f"function {f_name}({f_params})")
            js_arrows = re.findall(r'(?:const|let|var)\s+([a-zA-Z0-9_]+)\s*=\s*(?:\([^)]*\)|[a-zA-Z0-9_]+)\s*=>', code)
            for f_name in js_arrows:
                key_funcs.append(f"const {f_name} = (...) =>")

        if not key_funcs:
            key_funcs = [f"Top-level {language.upper()} sequence"]

        # 2. Extract Data Structures Used
        data_structures = []
        if "vector<" in code or "std::vector" in code:
            data_structures.append("std::vector (Dynamic contiguous memory)")
        if "unordered_map" in code:
            data_structures.append("std::unordered_map (O(1) Hash Table)")
        elif "map<" in code or "std::map" in code:
            data_structures.append("std::map (Red-Black self-balancing tree)")
        if "[" in code and "]" in code and "std::vector" not in str(data_structures):
            data_structures.append("Fixed / Indexed Array")
        if "dict" in code_lower or ("{" in code and ":" in code):
            data_structures.append("Hash Map / Dictionary (O(1) amortized lookup)")
        if "set(" in code or "new Set" in code:
            data_structures.append("Hash Set (Unique value collection)")
        if "*" in code and any(k in code for k in ("int*", "char*", "void*", "->", "malloc", "free")):
            data_structures.append("Raw Pointers & Heap Memory")

        if not data_structures:
            data_structures = ["Primitive Variables & Scalars"]

        # 3. Extract Variables
        key_vars = []
        if lang in ("python", "py"):
            vars_found = re.findall(r'\b([a-zA-Z_][a-zA-Z0-9_]*)\s*=', code)
            for v in vars_found:
                if v not in ("self", "cls", "def", "class", "for", "if", "while") and v not in key_vars:
                    key_vars.append(v)
        elif lang in ("cpp", "c++", "c", "java"):
            typed_vars = re.findall(r'\b(?:int|float|double|char|bool|auto|string|vector<[^>]+>)\s+([a-zA-Z_][a-zA-Z0-9_]*)', code)
            for v in typed_vars:
                if v not in key_vars:
                    key_vars.append(v)
        elif lang in ("javascript", "js"):
            js_vars = re.findall(r'\b(?:let|const|var)\s+([a-zA-Z_][a-zA-Z0-9_]*)', code)
            for v in js_vars:
                if v not in key_vars:
                    key_vars.append(v)

        if not key_vars:
            key_vars = ["Input parameters & local variables"]

        # 4. Classify Algorithm
        algo_name = "Sequential Procedural Routine"
        purpose = "Executes sequential statements to process inputs."

        if ("for " in code and code.count("for ") >= 2) or ("for(" in code and code.count("for(") >= 2):
            algo_name = "Nested Iteration / Double-Loop Scan"
            purpose = "Compares or combines elements pairwise across a dataset."
        elif "sort(" in code or "sorted(" in code or ("swap(" in code and "for" in code):
            algo_name = "Comparative Sorting Algorithm"
            purpose = "Orders input elements in ascending or descending sequence."
        elif "mid =" in code or "mid=" in code or "low <=" in code:
            algo_name = "Binary Search (Divide & Conquer)"
            purpose = "Searches for a target item in a sorted collection in logarithmic time."
        elif any(f_name in code and f"def {f_name}" in code for f_name in ["fib", "factorial", "solve", "recur"]):
            algo_name = "Recursive Tree Traversal"
            purpose = "Breaks down a computational problem into smaller subproblems recursively."

        # 5. Build Step-by-Step Flow
        step_flow = [
            f"1. Entry: Accepts parameters and allocates local stack frames ({', '.join(key_vars[:3])}).",
            "2. Processing: Evaluates iterative loops and conditional branch decisions.",
            "3. Termination: Completes execution and yields return value to caller."
        ]

        mentor_note = "Mentor Tip: Ensure boundary test cases (empty inputs, zero, negatives) are verified."

        return ExplanationModel(
            provider=self.name,
            purpose=purpose,
            algorithm=algo_name,
            data_structures=data_structures,
            key_functions=key_funcs[:5],
            key_variables=key_vars[:6],
            step_by_step=step_flow,
            mentor_note=mentor_note,
            token_usage={"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
            estimated_cost_usd=0.0
        )
