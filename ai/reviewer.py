import os
import re
import json
import requests
from config import Config
from typing import Dict, Any, List


from ai.factory import get_ai_provider


def get_ai_explanation(
    code: str,
    language: str = "python",
    context_issues: list = None,
    provider_name: str = None
) -> Dict[str, Any]:
    """
    Generates structured code explanation and mentor guidance using the configured ReviewProvider.
    """
    provider = get_ai_provider(provider_name)
    explanation = provider.generate_explanation(code, language, context_issues)
    return explanation.model_dump()



def _generate_dynamic_offline_explanation(code: str, language: str, context_issues: list = None) -> Dict[str, Any]:
    """
    Offline dynamic analysis and explanation engine tailored to Python, C++, C, Java, and JavaScript.
    Analyzes exact functions, variables, data structures, and algorithmic patterns.
    """
    lang = language.lower().strip()
    lines = [line.strip() for line in code.split("\n") if line.strip()]
    code_lower = code.lower()

    # 1. Detect Functions & Signatures across languages
    key_funcs = []
    if lang in ("python", "py"):
        funcs = re.findall(r'def\s+([a-zA-Z0-9_]+)\s*\((.*?)\)', code)
        for f_name, f_params in funcs:
            key_funcs.append(f"def {f_name}({f_params})")
    elif lang in ("cpp", "c++", "c"):
        # Match e.g. vector<int> twoSum(vector<int>& nums, int target) or void bubbleSort(int arr[], int n) or int main()
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
        # Arrow functions or const fn = (...)
        js_arrows = re.findall(r'(?:const|let|var)\s+([a-zA-Z0-9_]+)\s*=\s*(?:\([^)]*\)|[a-zA-Z0-9_]+)\s*=>', code)
        for f_name in js_arrows:
            key_funcs.append(f"const {f_name} = (...) =>")

    # 2. Extract Data Structures Used
    data_structures = []
    if "vector<" in code or "std::vector" in code:
        data_structures.append("std::vector (Dynamic contiguous memory)")
    if "unordered_map" in code:
        data_structures.append("std::unordered_map (O(1) Hash Table)")
    elif "map<" in code or "std::map" in code:
        data_structures.append("std::map (Red-Black self-balancing tree)")
    if "unordered_set" in code:
        data_structures.append("std::unordered_set (Hash Set)")
    elif "set<" in code or "std::set" in code:
        data_structures.append("std::set (Ordered unique collection)")
    if "string" in code and lang in ("cpp", "c++"):
        data_structures.append("std::string (Dynamic character buffer)")

    if "[" in code and "]" in code and "std::vector" not in str(data_structures):
        data_structures.append("Fixed / Indexed Array")
    if "HashMap" in code or "Map<" in code or "new Map" in code:
        data_structures.append("Hash Map / Key-Value Lookup")
    if "ArrayList" in code or "List<" in code:
        data_structures.append("Dynamic List (ArrayList)")
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
    # Match assignment statements
    assigns = re.findall(r'(?:int|double|float|auto|const|let|var)?\s*([a-zA-Z0-9_]+)\s*=', code)
    reserved = {"for", "if", "def", "class", "while", "return", "int", "void", "public", "private", "auto", "const", "new", "else", "switch"}
    for v in assigns:
        v_clean = v.strip()
        if v_clean and v_clean not in reserved and len(v_clean) < 25:
            key_vars.append(v_clean)
    key_vars = list(dict.fromkeys(key_vars))[:6]

    # 4. Infer Algorithm, Purpose & Mechanics dynamically
    func_names_lower = [f.lower() for f in key_funcs]
    has_nested_loops = False
    if lang in ("python", "py"):
        has_nested_loops = code.count("for ") >= 2 or (code.count("for ") >= 1 and code.count("while ") >= 1)
    else:
        has_nested_loops = len(re.findall(r'\bfor\s*\(', code)) >= 2 or len(re.findall(r'\bwhile\s*\(', code)) >= 2

    purpose = ""
    algo_name = ""
    step_flow = []

    # Check Two Sum / Pair Finding
    if ("sum" in code_lower and ("target" in code_lower or "pair" in code_lower or "complement" in code_lower)) or any("twosum" in fn for fn in func_names_lower):
        algo_name = "Two-Sum Target Pair Matching"
        if has_nested_loops:
            purpose = f"Finds two distinct elements whose sum equals a given target using nested O(n²) exhaustive search in {language.upper()}."
            algo_name += " (Brute-Force O(n²))"
        else:
            purpose = f"Efficiently identifies two numbers that sum up to a target value using linear lookup in {language.upper()}."
            algo_name += " (Linear O(n))"

        step_flow.append(f"1. Function Entry: Accepts input collection and target sum ({', '.join(key_vars[:2]) if key_vars else 'parameters'}).")
        if has_nested_loops:
            step_flow.append("2. Outer Loop: Selects index `i` representing the first candidate number.")
            step_flow.append("3. Inner Loop: Iterates index `j` to pair with `i`, checking if `nums[i] + nums[j] == target`.")
            step_flow.append("4. Result / Exit: Returns matching index pair upon discovery or an empty collection if no pair satisfies the condition.")
        else:
            step_flow.append("2. Hash Lookup: Traverses elements, calculating `complement = target - current` and inspecting the hash map.")
            step_flow.append("3. Match or Memoize: If complement is seen, returns current and complement indices; otherwise records current item in map.")

    # Check Sorting (Bubble / Selection / General Sort)
    elif any(k in code_lower for k in ("sort", "bubble", "swap", "selection")):
        algo_name = "Comparison-Based Sorting Algorithm"
        purpose = f"Sorts an array or vector of items into ascending or descending sequence using pairwise comparisons in {language.upper()}."
        step_flow.append(f"1. Sequence Intake: Evaluates size `n` of the input collection.")
        step_flow.append("2. Pass Cycle: Outer loop executes passes through the array to settle extreme values at boundary.")
        step_flow.append("3. Element Swap: Inner loop inspects adjacent elements and performs in-place swaps when out of order.")
        step_flow.append("4. Finalization: Returns or displays the sorted collection.")

    # Check Binary Search / Halving
    elif any(k in code_lower for k in ("binary", "search", "mid", "low", "high")):
        algo_name = "Binary Search (Divide & Conquer)"
        purpose = f"Searches for a target value in a sorted collection in logarithmic O(log n) time by continuously halving the search interval."
        step_flow.append("1. Boundary Pointers: Initializes `low = 0` and `high` at the bounds of the array.")
        step_flow.append("2. Interval Halving: Calculates midpoint index `mid = (low + high) / 2` each iteration.")
        step_flow.append("3. Condition Branch: If `arr[mid] == target`, returns index; else narrows search to either the left or right partition.")
        step_flow.append("4. Not Found: Terminates and yields `-1` if boundaries cross without finding target.")

    # Check Recursion / Recurrence
    elif any(k in code_lower for k in ("fib", "factorial", "recur")):
        algo_name = "Recursive Tree Evaluation"
        purpose = f"Computes mathematical sequence values using self-referencing recurrence functions in {language.upper()}."
        step_flow.append("1. Base Case Guard: Evaluates termination conditions (e.g. `n <= 1`) to halt recursive descent.")
        step_flow.append("2. Recursive Branching: Spawns sub-calls for overlapping sub-problems on the call stack.")
        step_flow.append("3. Unwinding & Sum: Combines returned values as the call stack frames resolve back up to root.")

    # Check Array Max / Min / Scanning
    elif any(k in code_lower for k in ("max", "min", "largest", "smallest", "reverse")):
        algo_name = "Linear Collection Scan / In-Place Manipulation"
        purpose = f"Traverses collection elements to find boundary extremes or modify item positions sequentially."
        step_flow.append(f"1. Tracking Variable: Allocates state tracker ({key_vars[0] if key_vars else 'tracker'}) to store current maximum/result.")
        step_flow.append("2. Item Iteration: Iterates sequentially through each element in the collection.")
        step_flow.append("3. Evaluation: Tests whether current item exceeds tracked threshold or satisfies swap conditions.")
        step_flow.append("4. Return: Yields accumulated final value.")

    else:
        # Dynamic procedural walkthrough
        algo_name = f"Procedural {language.upper()} Logic Flow"
        purpose = f"Executes structured data transformations and control operations on input arguments using {language.upper()} idioms."
        step_flow.append(f"1. Initialization: Program initializes {len(key_vars)} key variable(s) ({', '.join(key_vars) if key_vars else 'local variables'}) and configures runtime environment.")
        if any(k in code_lower for k in ("for ", "while ", "for(", "while(")):
            step_flow.append("2. Iteration Loop: Drives iterative traversal over input data or loop counters.")
        if any(k in code_lower for k in ("if ", "if(", "switch")):
            step_flow.append("3. Conditional Branch: Validates decision logic and state transitions.")
        step_flow.append("4. Termination: Produces output via return statement or standard I/O streams.")

    # 5. Tailored Mentor Note
    mentor_note = ""
    if lang in ("cpp", "c++"):
        if "&" not in code and "vector" in code:
            mentor_note = "Mentor Tip: In C++, pass large containers like `vector<int>` by const reference (`const vector<int>& nums`) to prevent costly full memory copies on function calls."
        elif has_nested_loops:
            mentor_note = "Mentor Tip: The nested loops here incur O(n²) time complexity. Consider using `std::unordered_map` for O(n) average time complexity."
        else:
            mentor_note = "Mentor Tip: Use modern C++ RAII and STL container algorithms (`std::sort`, `std::find`) for both safer memory management and optimal performance."
    elif lang == "c":
        mentor_note = "Mentor Tip: In C, always verify array bounds explicitly and ensure memory allocated with `malloc` has matching `free` calls to avoid leaks."
    elif lang == "java":
        if "==" in code and "String" in code:
            mentor_note = "Mentor Tip: In Java, always compare String content using `.equals()` instead of `==`. The `==` operator compares reference memory addresses."
        else:
            mentor_note = "Mentor Tip: Leverage Java Collection Framework abstractions (`List`, `Map`) and watch out for NullPointerExceptions when accessing objects."
    elif lang in ("javascript", "js"):
        if "==" in code and "===" not in code:
            mentor_note = "Mentor Tip: In JavaScript, always use strict equality (`===`) instead of loose equality (`==`) to avoid unexpected type coercion."
        else:
            mentor_note = "Mentor Tip: Modern JS supports `Map` and `Set` for high-performance key lookups and clean functional array methods (`.map()`, `.filter()`)."
    else:
        # Python
        mentor_note = "Mentor Tip: Focus on edge case resilience (e.g. empty inputs, negative numbers, missing dictionary keys) to build production-grade habits."

    return {
        "provider": f"CodeComprehension {language.upper()} Intelligence",
        "purpose": purpose,
        "algorithm": algo_name,
        "data_structures": data_structures,
        "key_functions": key_funcs if key_funcs else [f"Top-level {language.upper()} routine"],
        "key_variables": key_vars if key_vars else ["Input parameters"],
        "step_by_step": step_flow,
        "mentor_note": mentor_note
    }


def _call_gemini_explanation(code: str, language: str, api_key: str) -> Dict[str, Any]:
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={api_key}"
    headers = {"Content-Type": "application/json"}
    prompt = f"""You are an expert programming mentor in CodeComprehension.
Explain the following {language} code clearly for a developer.
Return ONLY a valid JSON object with these exact keys:
{{
  "purpose": "A concise 1-2 sentence description of what the code achieves.",
  "algorithm": "Name or classification of algorithm used.",
  "data_structures": ["list of data structures used"],
  "key_functions": ["function names with params"],
  "key_variables": ["notable variable names and their roles"],
  "step_by_step": ["step 1 description", "step 2 description", "step 3 description"],
  "mentor_note": "A thoughtful 1 sentence mentoring tip for the author."
}}

Code:
```{language}
{code[:3000]}
```
Do not include markdown backticks around the JSON. Return raw JSON string only."""

    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.2, "maxOutputTokens": 1000}
    }

    resp = requests.post(url, headers=headers, json=payload, timeout=6.0)
    if resp.status_code == 200:
        data = resp.json()
        text = data["candidates"][0]["content"]["parts"][0]["text"].strip()
        text = re.sub(r'^```json\s*', '', text)
        text = re.sub(r'```$', '', text).strip()
        parsed = json.loads(text)
        parsed["provider"] = "Google Gemini Live AI"
        return parsed

    raise Exception(f"Gemini API returned status {resp.status_code}")


def _call_openai_explanation(code: str, language: str, api_key: str) -> Dict[str, Any]:
    url = "https://api.openai.com/v1/chat/completions"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}"
    }
    prompt = f"""Explain this {language} code as a programming mentor. Return ONLY a JSON object with:
{{
  "purpose": "1-2 sentence overview",
  "algorithm": "Algorithm name/style",
  "data_structures": ["structures used"],
  "key_functions": ["function signatures"],
  "key_variables": ["variables"],
  "step_by_step": ["step 1", "step 2", "step 3"],
  "mentor_note": "Mentoring insight"
}}

Code:
```{language}
{code[:3000]}
```"""

    payload = {
        "model": "gpt-4o-mini",
        "messages": [{"role": "user", "content": prompt}],
        "response_format": {"type": "json_object"},
        "temperature": 0.2
    }

    resp = requests.post(url, headers=headers, json=payload, timeout=6.0)
    if resp.status_code == 200:
        data = resp.json()
        content = data["choices"][0]["message"]["content"]
        parsed = json.loads(content)
        parsed["provider"] = "OpenAI GPT Live AI"
        return parsed

    raise Exception(f"OpenAI API returned status {resp.status_code}")
