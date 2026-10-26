import uuid
from flask import Blueprint, request, jsonify, g
from config import Config
from extensions import limiter
import logging
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

logger = logging.getLogger("codecomprehension.routes.review")
review_bp = Blueprint("review_bp", __name__)


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
    language_input = str(data.get("language", "python")).strip().lower()

    request_id = getattr(g, "request_id", str(uuid.uuid4()))

    # Normalize language input using aliases
    language = Config.LANGUAGE_ALIASES.get(language_input, language_input)

    if not code or not code.strip():
        return make_error_response("EMPTY_CODE", "Empty code payload. Please write or paste code to analyze.", 400)

    if len(code) > Config.MAX_CODE_LENGTH:
        return make_error_response(
            "CODE_TOO_LONG",
            f"Submitted code length ({len(code)} chars) exceeds maximum limit of {Config.MAX_CODE_LENGTH} chars.",
            413
        )

    if language not in Config.SUPPORTED_LANGUAGES:
        supported_langs = ", ".join(sorted([k for k in Config.SUPPORTED_LANGUAGES.keys()]))
        return make_error_response(
            "UNSUPPORTED_LANGUAGE",
            f"Language '{language_input}' is not supported. Supported languages are: {supported_langs}.",
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
            cached_payload["request_id"] = request_id
            if secret_warnings:
                cached_payload["security_warnings"] = secret_warnings
            return jsonify(cached_payload)

    # Initialize all results with a default "not analyzed" state
    syntax_res = {"status": "not_analyzed", "reason": "Syntax analysis not run."}
    ast_res = {"status": "not_analyzed", "reason": "AST analysis not run."}
    bugs_res = {"status": "not_analyzed", "reason": "Bug detection not run.", "issues": [], "score": 100, "summary": "No critical defects detected."}
    complexity_res = {"status": "not_analyzed", "reason": "Complexity analysis not run."}
    test_cases_res = {"status": "not_analyzed", "reason": "Test case generation not run."}
    optimization_res = {"status": "not_analyzed", "reason": "Optimization analysis not run."}
    explanation_res = {"status": "not_analyzed", "reason": "AI explanation not run."}
    visualization_res = {"status": "not_analyzed", "reason": "Visualization pre-computation not run."}
    topology_3d_res = {"status": "not_analyzed", "reason": "3D topology pre-computation not run."}

    # Coordinated Analysis Pipeline
    try:
        syntax_res = analyze_syntax(safe_code, language)
    except Exception as e:
        logger.error(f"Syntax analysis failed for request {request_id}: {e}")
        syntax_res = {"status": "failed", "reason": f"Syntax analysis encountered an error: {str(e)}"}

    try:
        ast_res = analyze_ast(safe_code, language)
    except Exception as e:
        logger.error(f"AST analysis failed for request {request_id}: {e}")
        ast_res = {"status": "failed", "reason": f"AST analysis encountered an error: {str(e)}"}

    try:
        bugs_res = detect_bugs(safe_code, language)
    except Exception as e:
        logger.error(f"Bug detection failed for request {request_id}: {e}")
        bugs_res = {"status": "failed", "reason": f"Bug detection encountered an error: {str(e)}", "issues": [], "score": 100, "summary": "Bug detection failed due to an internal error."}

    try:
        complexity_res = analyze_complexity(safe_code, language)
    except Exception as e:
        logger.error(f"Complexity analysis failed for request {request_id}: {e}")
        complexity_res = {"status": "failed", "reason": f"Complexity analysis encountered an error: {str(e)}"}

    try:
        test_cases_res = generate_test_cases(safe_code, language)
    except Exception as e:
        logger.error(f"Test case generation failed for request {request_id}: {e}")
        test_cases_res = {"status": "failed", "reason": f"Test case generation encountered an error: {str(e)}"}

    try:
        optimization_res = analyze_optimization(safe_code, language)
    except Exception as e:
        logger.error(f"Optimization analysis failed for request {request_id}: {e}")
        optimization_res = {"status": "failed", "reason": f"Optimization analysis encountered an error: {str(e)}"}

    try:
        explanation_res = get_ai_explanation(
            safe_code,
            language,
            bugs_res.get("issues", []),
            provider_name=canonical_provider
        )
    except Exception as e:
        logger.error(f"AI explanation failed for request {request_id}: {e}")
        explanation_res = {"status": "failed", "reason": f"AI explanation encountered an error: {str(e)}"}

    try:
        visualization_res = generate_visualization_frames(safe_code, language)
    except Exception as e:
        logger.error(f"Visualization generation failed for request {request_id}: {e}")
        visualization_res = {"status": "failed", "reason": f"Visualization generation encountered an error: {str(e)}"}

    try:
        topology_3d_res = generate_3d_topology(safe_code, language, ast_res, complexity_res)
    except Exception as e:
        logger.error(f"3D topology generation failed for request {request_id}: {e}")
        topology_3d_res = {"status": "failed", "reason": f"3D topology generation encountered an error: {str(e)}"}

    review_payload = {
        "success": True, # Overall API call success, not necessarily all analysis steps
        "request_id": request_id,
        "language": language,
        "syntax": syntax_res,
        "ast": ast_res,
        "bugs": bugs_res,
        "score": bugs_res.get("score", 100), # Default to 100 if bug detection failed or no score
        "score_breakdown": bugs_res.get("score_breakdown", {}),
        "summary": bugs_res.get("summary", "Analysis completed with partial results due to internal errors in some modules."),
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
        # Extract complexity metrics carefully if analysis failed
        time_complexity = complexity_res.get("time_complexity") if isinstance(complexity_res, dict) and "time_complexity" in complexity_res else "N/A"
        space_complexity = complexity_res.get("space_complexity") if isinstance(complexity_res, dict) and "space_complexity" in complexity_res else "N/A"

        review_id = database.save_review(
            language=language,
            code=safe_code,
            score=review_payload["score"],
            issue_count=len(bugs_res.get("issues", [])),
            time_complexity=time_complexity,
            space_complexity=space_complexity,
            review_data=review_payload,
            ai_provider=canonical_provider,
            prompt_version=database.ANALYZER_VERSION
        )
        review_payload["review_id"] = review_id
    except Exception as e:
        logger.error(f"Database persistence failed for review request {request_id}: {e}")
        review_payload["review_id"] = None
        review_payload["db_warning"] = f"Review completed but database persistence failed: {str(e)}"

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
