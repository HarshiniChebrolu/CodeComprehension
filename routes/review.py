import uuid
from flask import Blueprint, request, jsonify, g
from config import Config
from extensions import limiter
import database
from analyzer.syntax_analyzer import analyze_syntax
from analyzer.ast_analyzer import analyze_ast
from analyzer.bug_detector import detect_bugs
from analyzer.complexity_analyzer import analyze_complexity
from analyzer.test_generator import generate_test_cases
from analyzer.optimizer import analyze_optimization
from analyzer.visualizer import generate_visualization_frames
from analyzer.topology_3d import generate_3d_topology
from analyzer.secret_redactor import scan_and_redact_secrets
from ai.reviewer import get_ai_explanation

review_bp = Blueprint("review_bp", __name__)
ALLOWED_LANGUAGES = {"python", "py", "cpp", "c++", "c", "java", "javascript", "js"}


def make_error_response(code: str, message: str, status_code: int = 400):
    req_id = getattr(g, "request_id", str(uuid.uuid4()))
    return jsonify({
        "success": False,
        "error": {
            "code": code,
            "message": message,
            "request_id": req_id
        }
    }), status_code


@review_bp.route("/api/v1/review", methods=["POST"])
@review_bp.route("/api/review", methods=["POST"])
@limiter.limit(Config.RATELIMIT_REVIEW)
def review_code():
    data = request.get_json(force=True, silent=True) or {}
    code = data.get("code", "")
    language = str(data.get("language", "python")).strip().lower()

    if not code or not code.strip():
        return make_error_response("EMPTY_CODE", "Empty code payload. Please write or paste code to analyze.", 400)

    if len(code) > Config.MAX_CODE_LENGTH:
        return make_error_response(
            "CODE_TOO_LONG",
            f"Submitted code length ({len(code)} chars) exceeds maximum limit of {Config.MAX_CODE_LENGTH} chars.",
            413
        )

    if language not in ALLOWED_LANGUAGES:
        return make_error_response(
            "UNSUPPORTED_LANGUAGE",
            f"Language '{language}' is not supported. Supported: Python, C++, C, Java, JavaScript.",
            400
        )

    # Secret scanning & redaction before analysis, caching, and persistence
    safe_code, secret_warnings = scan_and_redact_secrets(code)

    # Canonical AI provider identifier (e.g. 'offline', 'gemini', 'openai')
    canonical_provider = str(data.get("ai_provider") or Config.DEFAULT_AI_PROVIDER or "offline").lower().strip()

    # Cache lookup (unless client explicitly requests fresh review)
    no_cache = data.get("no_cache", False)
    if not no_cache:
        cached = database.get_cached_review(
            code=safe_code,
            language=language,
            ai_provider=canonical_provider,
            prompt_version=database.ANALYZER_VERSION
        )
        if cached and cached.get("review_data"):
            cached_payload = dict(cached["review_data"])
            cached_payload["review_id"] = cached["id"]
            cached_payload["cached"] = True
            cached_payload["request_id"] = getattr(g, "request_id", str(uuid.uuid4()))
            if secret_warnings:
                cached_payload["security_warnings"] = secret_warnings
            return jsonify(cached_payload)

    # 1. Syntax Analysis
    syntax_res = analyze_syntax(safe_code, language)

    # 2. AST Analysis
    ast_res = analyze_ast(safe_code, language)

    # 3. Bug Detection & Scoring
    bugs_res = detect_bugs(safe_code, language)

    # 4. Complexity Analysis
    complexity_res = analyze_complexity(safe_code, language)

    # 5. Test Case Generation
    test_cases_res = generate_test_cases(safe_code, language)

    # 6. Optimization Opportunities
    optimization_res = analyze_optimization(safe_code, language)

    # 7. AI / Mentor Explanation (using redacted safe code and configured provider)
    explanation_res = get_ai_explanation(
        safe_code,
        language,
        bugs_res.get("issues", []),
        provider_name=canonical_provider
    )

    # 8. Visualization Frames Pre-computation
    visualization_res = generate_visualization_frames(safe_code, language)

    # 9. Clean 2D Program Control Flow Graph Pre-computation
    topology_3d_res = generate_3d_topology(safe_code, language, ast_res, complexity_res)

    review_payload = {
        "success": True,
        "request_id": getattr(g, "request_id", str(uuid.uuid4())),
        "language": language,
        "syntax": syntax_res,
        "ast": ast_res,
        "bugs": bugs_res,
        "score": bugs_res.get("score", 100),
        "score_breakdown": bugs_res.get("score_breakdown", {}),
        "summary": bugs_res.get("summary", ""),
        "complexity": complexity_res,
        "test_cases": test_cases_res,
        "optimization": optimization_res,
        "explanation": explanation_res,
        "visualization": visualization_res,
        "topology_3d": topology_3d_res,
        "security_warnings": secret_warnings,
        "ai_provider": canonical_provider,
        "cached": False
    }

    # Save redacted safe copy to SQLite Review History
    try:
        review_id = database.save_review(
            language=language,
            code=safe_code,
            score=bugs_res.get("score", 100),
            issue_count=len(bugs_res.get("issues", [])),
            time_complexity=complexity_res.get("time_complexity", "O(1)"),
            space_complexity=complexity_res.get("space_complexity", "O(1)"),
            review_data=review_payload,
            ai_provider=canonical_provider,
            prompt_version=database.ANALYZER_VERSION
        )
        review_payload["review_id"] = review_id
    except Exception as e:
        review_payload["review_id"] = None
        review_payload["db_warning"] = "Review completed but database persistence failed."

    return jsonify(review_payload)


@review_bp.route("/api/v1/hint", methods=["POST"])
@review_bp.route("/api/hint", methods=["POST"])
def get_hint():
    """
    Returns progressive hints (Level 1 -> 2 -> 3).
    Tracks server-side unlocked level to enforce educational deduction.
    Validates review_id and issue ownership on the server.
    """
    data = request.get_json(force=True, silent=True) or {}
    review_id = data.get("review_id")
    bug_id = data.get("bug_id")
    raw_level = data.get("level", 1)

    if not review_id:
        return make_error_response("MISSING_REVIEW_ID", "Field 'review_id' is required to access hints.", 400)

    try:
        review_id_int = int(review_id)
    except (ValueError, TypeError):
        return make_error_response("INVALID_REVIEW_ID", "Field 'review_id' must be a valid integer.", 400)

    if not bug_id:
        return make_error_response("MISSING_BUG_ID", "Field 'bug_id' is required.", 400)

    try:
        level = int(raw_level)
        if not (1 <= level <= 3):
            return make_error_response("INVALID_HINT_LEVEL", "Hint level must be between 1 and 3.", 400)
    except (ValueError, TypeError):
        return make_error_response("INVALID_HINT_LEVEL", "Hint level must be an integer.", 400)

    review = database.get_review_by_id(review_id_int)
    if not review:
        return make_error_response("REVIEW_NOT_FOUND", f"Review record #{review_id} not found.", 404)

    review_data = review.get("review_data") or {}
    stored_issues = review_data.get("bugs", {}).get("issues", [])
    matched = None
    for iss in stored_issues:
        if iss.get("id") == bug_id:
            matched = iss
            break

    # Fallback to client-supplied issues if stored review has empty issues list
    if not matched and "issues" in data:
        for iss in data.get("issues", []):
            if iss.get("id") == bug_id:
                matched = iss
                break

    if not matched:
        return make_error_response("ISSUE_NOT_FOUND", f"Issue '{bug_id}' not found in review #{review_id}.", 404)

    # Server-side progressive unlock check
    current_unlocked = database.record_hint_unlock(review_id_int, bug_id, level)
    if level > current_unlocked:
        return make_error_response(
            "INVALID_HINT_SEQUENCE",
            f"Cannot skip hints. Current unlocked level is {current_unlocked}. Please unlock level {current_unlocked + 1} first.",
            400
        )

    hints = matched.get("hints", {})
    hint_text = ""
    hint_title = f"Hint {level}"

    if level == 1:
        hint_text = hints.get("hint1", "Look carefully at the control flow and conditions.")
        hint_title = "Hint 1: Gentle Clue"
    elif level == 2:
        hint_text = hints.get("hint2", "Check boundary scenarios and state persistence.")
        hint_title = "Hint 2: Directional Guidance"
    elif level == 3:
        hint_text = hints.get("hint3", "Consider edge cases such as empty or negative input.")
        hint_title = "Hint 3: Strong Hint"

    return jsonify({
        "success": True,
        "review_id": review_id_int,
        "bug_id": bug_id,
        "level": level,
        "title": hint_title,
        "hint": hint_text,
        "has_next_hint": level < 3
    })


@review_bp.route("/api/v1/solution", methods=["POST"])
@review_bp.route("/api/solution", methods=["POST"])
def get_solution():
    """
    Reveals the solution ONLY after progressive hints have been completed.
    Enforces strict server-side validation against bypassing hint progression.
    """
    data = request.get_json(force=True, silent=True) or {}
    review_id = data.get("review_id")
    bug_id = data.get("bug_id")

    if not review_id:
        return make_error_response("MISSING_REVIEW_ID", "Field 'review_id' is required to reveal solution.", 400)

    try:
        review_id_int = int(review_id)
    except (ValueError, TypeError):
        return make_error_response("INVALID_REVIEW_ID", "Field 'review_id' must be a valid integer.", 400)

    if not bug_id:
        return make_error_response("MISSING_BUG_ID", "Field 'bug_id' is required.", 400)

    review = database.get_review_by_id(review_id_int)
    if not review:
        return make_error_response("REVIEW_NOT_FOUND", f"Review record #{review_id} not found.", 404)

    review_data = review.get("review_data") or {}
    stored_issues = review_data.get("bugs", {}).get("issues", [])
    matched = None
    for iss in stored_issues:
        if iss.get("id") == bug_id:
            matched = iss
            break

    # Fallback to client-supplied issues if stored review issues was empty
    if not matched and "issues" in data:
        for iss in data.get("issues", []):
            if iss.get("id") == bug_id:
                matched = iss
                break

    if not matched:
        return make_error_response("ISSUE_NOT_FOUND", f"Issue '{bug_id}' not found in review #{review_id}.", 404)

    # Strict server-side progressive hint gate
    is_authorized = database.check_solution_authorized(review_id_int, bug_id)
    if not is_authorized:
        return make_error_response(
            "HINTS_INCOMPLETE",
            "Access Denied: You must unlock all 3 progressive hints before revealing the solution. "
            "CodeComprehension emphasizes deduction over instant answers!",
            403
        )

    database.record_solution_unlocked(review_id_int, bug_id)

    solution = matched.get("solution", {})
    return jsonify({
        "success": True,
        "review_id": review_id_int,
        "bug_id": bug_id,
        "problem": matched.get("problem"),
        "line": matched.get("line"),
        "solution": solution
    })


@review_bp.route("/api/v1/explain", methods=["POST"])
@review_bp.route("/api/explain", methods=["POST"])
def explain_code():
    data = request.get_json(force=True, silent=True) or {}
    code = data.get("code", "")
    language = str(data.get("language", "python")).strip().lower()

    if not code:
        return make_error_response("EMPTY_CODE", "No code provided to explain.", 400)

    safe_code, _ = scan_and_redact_secrets(code)
    explanation = get_ai_explanation(safe_code, language)
    return jsonify({
        "success": True,
        "explanation": explanation
    })
