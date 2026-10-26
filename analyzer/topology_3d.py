import re
import math
from typing import Dict, Any, List


def generate_3d_topology(code: str, language: str = "python", ast_data: dict = None, complexity_data: dict = None) -> Dict[str, Any]:
    """
    Generates dynamic 3D spatial Control Flow Architecture & Topology data.
    Builds an authentic 3D Control Flow Graph (CFG) including:
      - Program / Function Entry Nodes
      - Variable & State Initializations
      - Loop Headers with Loopback Cycle Conduits
      - Conditional Branch Nodes with TRUE / FALSE branch pathways
      - Operations & Code Statements
      - Terminal Return / Exit Portals
      - Dynamic chronological Execution Sequence for 3D Moving Flow Playback
    """
    lang = language.lower().strip()
    raw_lines = code.split("\n")
    
    # 1. Parse structured statements with line numbers & indentation depth
    parsed_statements = []
    for idx, line in enumerate(raw_lines, start=1):
        stripped = line.strip()
        if not stripped:
            continue
        # Skip pure comment lines
        if stripped.startswith(("//", "/*", "*", "#")) and not (stripped.startswith("#include") or stripped.startswith("#define")):
            continue
            
        indent = len(line) - len(line.lstrip())
        parsed_statements.append({
            "line": idx,
            "raw": line,
            "text": stripped,
            "indent": indent
        })

    nodes = []
    edges = []
    execution_steps = []
    node_id_counter = 1

    def create_node(label, category, tier, x, y, z, shape, color, line_num, desc, snippet="", complexity="O(1)", branch_type=""):
        nonlocal node_id_counter
        nid = node_id_counter
        node_id_counter += 1
        node_obj = {
            "id": nid,
            "label": label,
            "snippet": snippet or label,
            "category": category, # entry, function, variable, loop, condition, operation, return
            "tier": tier,
            "x": round(float(x), 2),
            "y": round(float(y), 2),
            "z": round(float(z), 2),
            "shape": shape, # octahedron, icosahedron, torus, diamond, cube, cylinder, sphere
            "color": color,
            "line": line_num,
            "description": desc,
            "complexity": complexity,
            "branch_type": branch_type
        }
        nodes.append(node_obj)
        return node_obj

    def add_edge(from_id, to_id, flow_type="normal", label="", color=None, flow_rate=1.0):
        # Prevent self-loop on same ID
        if from_id == to_id:
            return
        edge_obj = {
            "from": from_id,
            "to": to_id,
            "flowType": flow_type, # normal, true_branch, false_branch, loopback, return
            "label": label,
            "color": color or ("#38bdf8" if flow_type == "normal" else "#10b981" if flow_type == "true_branch" else "#f43f5e" if flow_type == "false_branch" else "#fb923c"),
            "flowRate": flow_rate
        }
        edges.append(edge_obj)
        return edge_obj

    # Identify Key Structural Components
    # 1. Entry / Environment node
    entry_label = f"{language.upper()} Runtime Entry"
    entry_line = 1
    for st in parsed_statements:
        if st["text"].startswith("#include") or st["text"].startswith("import ") or st["text"].startswith("from "):
            entry_label = st["text"][:38]
            entry_line = st["line"]
            break

    entry_node = create_node(
        label=entry_label,
        category="entry",
        tier=1,
        x=0.0,
        y=7.5,
        z=0.0,
        shape="octahedron",
        color="#38bdf8",
        line_num=entry_line,
        desc="Program entry point and runtime environment initialization.",
        snippet=entry_label,
        complexity="O(1)"
    )

    # 2. Find Functions
    func_nodes = []
    var_nodes = []
    loop_nodes = []
    cond_nodes = []
    op_nodes = []
    ret_nodes = []

    for st in parsed_statements:
        text = st["text"]
        line = st["line"]

        # Function definition
        if "def " in text or (any(text.startswith(k) for k in ("int ", "void ", "function ", "public ", "bool ", "double ", "vector<", "std::vector", "string ", "auto ", "char ")) and "(" in text and ")" in text):
            clean_hdr = text.split("{")[0].strip().rstrip(":")
            f_name = clean_hdr.split("(")[0].strip().split()[-1].replace("*", "").replace("&", "")
            if f_name not in ("if", "for", "while", "switch", "catch"):
                func_nodes.append({
                    "name": f_name,
                    "label": f"def {f_name}()" if lang in ("python", "py") else f"{f_name}()",
                    "snippet": clean_hdr,
                    "line": line,
                    "indent": st["indent"]
                })
        # Loops
        elif text.startswith("for ") or text.startswith("for(") or text.startswith("while ") or text.startswith("while("):
            loop_label = text.split("{")[0].rstrip(":").strip()
            loop_nodes.append({
                "label": loop_label[:34] + ("..." if len(loop_label) > 34 else ""),
                "snippet": text,
                "line": line,
                "indent": st["indent"],
                "type": "for" if "for" in text else "while"
            })
        # Conditions
        elif text.startswith("if ") or text.startswith("if(") or text.startswith("elif ") or text.startswith("else if") or text.startswith("switch"):
            cond_label = text.split("{")[0].rstrip(":").strip()
            cond_nodes.append({
                "label": cond_label[:32] + ("..." if len(cond_label) > 32 else ""),
                "snippet": text,
                "line": line,
                "indent": st["indent"]
            })
        # Returns
        elif text.startswith("return") or "return " in text:
            ret_nodes.append({
                "label": text.rstrip(";"),
                "snippet": text,
                "line": line,
                "indent": st["indent"]
            })
        # Variable initializations
        elif "=" in text and not any(k in text for k in ("==", "<=", ">=", "!=", "+=", "-=", "*=", "/=", "for ", "while ")):
            parts = text.split("=")
            var_name = parts[0].strip().split()[-1]
            if len(var_name) <= 20 and var_name not in ("return", "if", "else", "elif"):
                var_nodes.append({
                    "label": f"{var_name} = {parts[1].strip()[:14]}",
                    "snippet": text,
                    "name": var_name,
                    "line": line,
                    "indent": st["indent"]
                })
        # Important in-loop operations (swaps, updates)
        elif any(k in text for k in ("+=", "-=", "*=", "swap", ".append", ".push", "printf", "cout", "print")):
            op_nodes.append({
                "label": text[:30] + ("..." if len(text) > 30 else ""),
                "snippet": text,
                "line": line,
                "indent": st["indent"]
            })

    # Default fallback function if none matched
    if not func_nodes:
        func_nodes.append({
            "name": "main",
            "label": f"main() Execution Scope",
            "snippet": "Program entry scope",
            "line": 1,
            "indent": 0
        })

    # Default fallback return if none
    if not ret_nodes:
        ret_nodes.append({
            "label": "return 0 / Exit",
            "snippet": "End of execution",
            "line": max(1, len(raw_lines)),
            "indent": 0
        })

    # Build 3D Control Flow Graph with true spatial pathways
    # Current active flow tip in the graph
    flow_tips = [entry_node["id"]]
    time_comp = complexity_data.get("time_complexity", "O(1)") if complexity_data else "O(n)"

    # 1. Tier 2: Function Node
    created_func_nodes = []
    for i, fn in enumerate(func_nodes[:2]):
        angle = (i - (len(func_nodes[:2]) - 1) / 2) * 1.2
        fx = round(math.sin(angle) * 3.0, 2)
        fy = 5.2
        fz = round(math.cos(angle) * 1.2, 2)
        f_node = create_node(
            label=fn["label"],
            category="function",
            tier=2,
            x=fx,
            y=fy,
            z=fz,
            shape="icosahedron",
            color="#ec4899",
            line_num=fn["line"],
            desc=f"Function frame: {fn['name']}(). Allocates stack frame and arguments.",
            snippet=fn["snippet"],
            complexity=time_comp
        )
        created_func_nodes.append(f_node)
        add_edge(entry_node["id"], f_node["id"], flow_type="normal", label="Invoke Call", color="#ec4899", flow_rate=1.2)
        execution_steps.append({
            "step": len(execution_steps) + 1,
            "node_id": f_node["id"],
            "line": fn["line"],
            "title": f"Function Call: {fn['name']}()",
            "description": f"Pushes activation frame onto stack and initiates execution."
        })

    if created_func_nodes:
        flow_tips = [f["id"] for f in created_func_nodes]

    # 2. Tier 3: Variable Initializations / Setup
    created_var_nodes = []
    for i, vn in enumerate(var_nodes[:3]):
        angle = (i - (len(var_nodes[:3]) - 1) / 2) * 1.4
        vx = round(math.sin(angle) * 4.2, 2)
        vy = 3.0
        vz = round(math.cos(angle) * 1.5, 2)
        v_node = create_node(
            label=vn["label"],
            category="variable",
            tier=3,
            x=vx,
            y=vy,
            z=vz,
            shape="cube",
            color="#10b981",
            line_num=vn["line"],
            desc=f"Variable allocation: `{vn['snippet']}` in local memory frame.",
            snippet=vn["snippet"],
            complexity="O(1)"
        )
        created_var_nodes.append(v_node)
        for tip in flow_tips:
            add_edge(tip, v_node["id"], flow_type="normal", label="Initialize", color="#10b981", flow_rate=1.0)
        execution_steps.append({
            "step": len(execution_steps) + 1,
            "node_id": v_node["id"],
            "line": vn["line"],
            "title": f"Memory Allocation: {vn['label']}",
            "description": f"Allocates memory register and assigns initial value."
        })

    if created_var_nodes:
        flow_tips = [v["id"] for v in created_var_nodes]

    # 3. Tier 4: Control Flow — Loops & Conditions
    created_loop_nodes = []
    for i, ln in enumerate(loop_nodes[:2]):
        lx = (i - (len(loop_nodes[:2]) - 1) / 2) * 2.8
        ly = 0.5 - (i * 2.5)
        lz = 0.0
        is_inner = i > 0
        l_node = create_node(
            label=f"Loop: {ln['label']}",
            category="loop",
            tier=4,
            x=lx,
            y=ly,
            z=lz,
            shape="torus",
            color="#f97316",
            line_num=ln["line"],
            desc=f"Iteration cycle: `{ln['snippet']}`. Controls iteration counter and termination check.",
            snippet=ln["snippet"],
            complexity="O(n)" if not is_inner else "O(n²)"
        )
        created_loop_nodes.append(l_node)
        for tip in flow_tips:
            add_edge(tip, l_node["id"], flow_type="normal", label="Enter Loop", color="#f97316", flow_rate=1.4)
        flow_tips = [l_node["id"]]
        execution_steps.append({
            "step": len(execution_steps) + 1,
            "node_id": l_node["id"],
            "line": ln["line"],
            "title": f"Loop Check: {ln['label']}",
            "description": "Evaluates loop boundary condition. If valid, iterates through loop body."
        })

    # 4. Conditional Branch Nodes (With TRUE and FALSE pathways!)
    created_cond_nodes = []
    for i, cn in enumerate(cond_nodes[:2]):
        cy = -2.2 - (i * 2.2)
        c_node = create_node(
            label=f"Branch: {cn['label']}",
            category="condition",
            tier=4,
            x=0.0,
            y=cy,
            z=0.0,
            shape="diamond",
            color="#a855f7",
            line_num=cn["line"],
            desc=f"Conditional Decision Branch: `{cn['snippet']}`. Tests truth predicate.",
            snippet=cn["snippet"],
            complexity="O(1)"
        )
        created_cond_nodes.append(c_node)
        for tip in flow_tips:
            add_edge(tip, c_node["id"], flow_type="normal", label="Evaluate Condition", color="#a855f7", flow_rate=1.2)
            
        execution_steps.append({
            "step": len(execution_steps) + 1,
            "node_id": c_node["id"],
            "line": cn["line"],
            "title": f"Decision Predicate: {cn['label']}",
            "description": "Evaluates boolean expression to determine branch fork."
        })

        # TRUE PATH: Branch Action / Statement (curves to +X)
        true_action_label = "True: Execute Block"
        true_action_line = cn["line"] + 1
        true_action_snippet = "Branch condition met (True)"
        if op_nodes:
            true_action_label = op_nodes[0]["label"]
            true_action_line = op_nodes[0]["line"]
            true_action_snippet = op_nodes[0]["snippet"]

        true_node = create_node(
            label=true_action_label,
            category="operation",
            tier=5,
            x=3.8,
            y=cy - 1.6,
            z=1.8,
            shape="sphere",
            color="#10b981",
            line_num=true_action_line,
            desc=f"Executed when `{cn['label']}` evaluates to TRUE.",
            snippet=true_action_snippet,
            complexity="O(1)",
            branch_type="true"
        )
        add_edge(c_node["id"], true_node["id"], flow_type="true_branch", label="TRUE Branch", color="#10b981", flow_rate=1.5)

        # FALSE / FALLTHROUGH PATH: (curves to -X)
        false_node = create_node(
            label="False: Continue Iteration",
            category="operation",
            tier=5,
            x=-3.8,
            y=cy - 1.6,
            z=-1.8,
            shape="sphere",
            color="#ef4444",
            line_num=cn["line"],
            desc=f"Executed when `{cn['label']}` evaluates to FALSE. Skips block.",
            snippet="Condition false -> continue",
            complexity="O(1)",
            branch_type="false"
        )
        add_edge(c_node["id"], false_node["id"], flow_type="false_branch", label="FALSE Branch", color="#ef4444", flow_rate=1.0)

        execution_steps.append({
            "step": len(execution_steps) + 1,
            "node_id": true_node["id"],
            "line": true_action_line,
            "title": f"Branch TRUE: {true_action_label}",
            "description": "Expression resolved to TRUE: executes target block."
        })

        # Add LOOPBACK conduit if a loop exists!
        if created_loop_nodes:
            target_loop = created_loop_nodes[-1]
            # Arc back from true and false nodes up to loop header
            add_edge(true_node["id"], target_loop["id"], flow_type="loopback", label="Loopback Cycle", color="#fb923c", flow_rate=1.6)
            add_edge(false_node["id"], target_loop["id"], flow_type="loopback", label="Loopback Cycle", color="#fb923c", flow_rate=1.4)
            execution_steps.append({
                "step": len(execution_steps) + 1,
                "node_id": target_loop["id"],
                "line": target_loop["line"],
                "title": f"Loopback Cycle: Re-evaluating Loop",
                "description": "Control flows back up to loop header for the next iteration cycle."
            })

        flow_tips = [true_node["id"], false_node["id"]]

    # 5. Operations fallback if no condition
    if not created_cond_nodes and op_nodes:
        for i, op in enumerate(op_nodes[:2]):
            oy = -2.0 - (i * 2.0)
            op_node = create_node(
                label=op["label"],
                category="operation",
                tier=5,
                x=0.0,
                y=oy,
                z=0.0,
                shape="sphere",
                color="#06b6d4",
                line_num=op["line"],
                desc=f"Operational mutation: `{op['snippet']}`.",
                snippet=op["snippet"],
                complexity="O(1)"
            )
            for tip in flow_tips:
                add_edge(tip, op_node["id"], flow_type="normal", label="Execute", color="#06b6d4", flow_rate=1.0)
            flow_tips = [op_node["id"]]
            execution_steps.append({
                "step": len(execution_steps) + 1,
                "node_id": op_node["id"],
                "line": op["line"],
                "title": f"Operation: {op['label']}",
                "description": "Mutates program state or registers."
            })

    # 6. Tier 6: Terminal Return / Exit Portals (Bottom)
    for i, rn in enumerate(ret_nodes[:2]):
        rx = (i - (len(ret_nodes[:2]) - 1) / 2) * 3.5
        ry = -7.5
        rz = 0.0
        ret_node = create_node(
            label=rn["label"],
            category="return",
            tier=6,
            x=rx,
            y=ry,
            z=rz,
            shape="cylinder",
            color="#eab308",
            line_num=rn["line"],
            desc=f"Terminal Return Statement: `{rn['snippet']}`. Pops frame and yields result to caller.",
            snippet=rn["snippet"],
            complexity="Exit"
        )
        for tip in flow_tips:
            add_edge(tip, ret_node["id"], flow_type="return", label="Return Result", color="#eab308", flow_rate=1.2)
        execution_steps.append({
            "step": len(execution_steps) + 1,
            "node_id": ret_node["id"],
            "line": rn["line"],
            "title": f"Exit / Return: {rn['label']}",
            "description": "Pops activation record and returns result to runtime host."
        })

    return {
        "title": "3D Code Control Flow Architecture",
        "language": language,
        "total_nodes": len(nodes),
        "total_conduits": len(edges),
        "nodes": nodes,
        "edges": edges,
        "execution_steps": execution_steps,
        "tiers": {
            "tier_1": {"name": "Program Entry & Runtime", "y": 7.5, "color": "#38bdf8"},
            "tier_2": {"name": "Function Frame & Signature", "y": 5.2, "color": "#ec4899"},
            "tier_3": {"name": "Memory & Variable Allocation", "y": 3.0, "color": "#10b981"},
            "tier_4": {"name": "Iteration Loops & Control Flow", "y": 0.0, "color": "#f97316"},
            "tier_5": {"name": "Conditional Branches & Actions", "y": -3.5, "color": "#a855f7"},
            "tier_6": {"name": "Termination & Returns", "y": -7.5, "color": "#eab308"}
        }
    }
