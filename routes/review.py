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
    # These defaults ensure the response structure is consistent even if an analysis step fails entirely.
    syntax_res = {"status": "not_analyzed", "reason": "Syntax analysis not run."}
    ast_res = {"status": "not_analyzed", "reason": "AST analysis not run."}
    bugs_res = {
        "status": "not_analyzed",
        "reason": "Bug detection not run.",
        "issues": [],
        "score": 100,
        "score_breakdown": {m: 100 for m in ["correctness", "readability", "maintainability", "efficiency", "security", "best_practices"]},
        "deductions": [],
        "summary": "No defects detected during bug scan.",
        "basis": "static analysis only; correctness not verified by execution"
    }
    complexity_res = {"status": "not_analyzed", "reason": "Complexity analysis not run."}
    test_cases_res = {"status": "not_analyzed", "reason": "Test case generation not run."}
    optimization_res = {"status": "not_analyzed", "reason": "Optimization analysis not run."}
    explanation_res = {"status": "not_analyzed", "reason": "AI explanation not run."}
    visualization_res = {"status": "not_analyzed", "reason": "Visualization pre-computation not run."}
    topology_3d_res = {"status": "not_analyzed", "reason": "3D topology pre-computation not run."}

    # Coordinated Analysis Pipeline - Each step is independent and handles its own errors
    logger.info(f"[{request_id}] Starting code review pipeline for language: {language}")

    # 1. Static Analysis / Bug Detection (Most comprehensive, includes scoring)
    try:
        bugs_res = detect_bugs(safe_code, language)
        logger.info(f"[{request_id}] Bug detection completed. Score: {bugs_res.get('score')}, Issues: {len(bugs_res.get('issues', []))}")
    except Exception as e:
        logger.error(f"[{request_id}] Bug detection failed: {e}", exc_info=True)
        bugs_res = {
            "status": "failed",
            "reason": f"Bug detection encountered an error: {str(e)}",
            "issues": [],
            "score": 50, # Default low score on failure
            "score_breakdown": {m: 50 for m in ["correctness", "readability", "maintainability", "efficiency", "security", "best_practices"]},
            "deductions": [],
            "summary": "Bug detection failed due to an internal error. Partial results may be available.",
            "basis": "bug detection module failed"
        }

    # 2. Syntax Analysis (can be redundant with bug_detector's SyntaxError, but ensures a dedicated check)
    try:
        syntax_res = analyze_syntax(safe_code, language)
        logger.debug(f"[{request_id}] Syntax analysis completed.")
    except Exception as e:
        logger.error(f"[{request_id}] Syntax analysis failed: {e}", exc_info=True)
        syntax_res = {"status": "failed", "reason": f"Syntax analysis encountered an error: {str(e)}"}

    # 3. Structural / AST Analysis
    try:
        ast_res = analyze_ast(safe_code, language)
        logger.debug(f"[{request_id}] AST analysis completed.")
    except Exception as e:
        logger.error(f"[{request_id}] AST analysis failed: {e}", exc_info=True)
        ast_res = {"status": "failed", "reason": f"AST analysis encountered an error: {str(e)}"}

    # 4. Complexity Analysis
    try:
        complexity_res = analyze_complexity(safe_code, language)
        logger.debug(f"[{request_id}] Complexity analysis completed.")
    except Exception as e:
        logger.error(f"[{request_id}] Complexity analysis failed: {e}", exc_info=True)
        complexity_res = {"status": "failed", "reason": f"Complexity analysis encountered an error: {str(e)}"}

    # 5. Test Case Generation
    try:
        test_cases_res = generate_test_cases(safe_code, language)
        logger.debug(f"[{request_id}] Test case generation completed.")
    except Exception as e:
        logger.error(f"[{request_id}] Test case generation failed: {e}", exc_info=True)
        test_cases_res = {"status": "failed", "reason": f"Test case generation encountered an error: {str(e)}"}

    # 6. Optimization Opportunities
    try:
        optimization_res = analyze_optimization(safe_code, language)
        logger.debug(f"[{request_id}] Optimization analysis completed.")
    except Exception as e:
        logger.error(f"[{request_id}] Optimization analysis failed: {e}", exc_info=True)
        optimization_res = {"status": "failed", "reason": f"Optimization analysis encountered an error: {str(e)}"}

    # 7. AI / Mentor Explanation (using redacted safe code and configured provider)
    try:
        explanation_res = get_ai_explanation(
            safe_code,
            language,
            bugs_res.get("issues", []), # Pass issues for context
            provider_name=canonical_provider
        )
        logger.debug(f"[{request_id}] AI explanation completed by {canonical_provider}.")
    except Exception as e:
        logger.error(f"[{request_id}] AI explanation failed: {e}", exc_info=True)
        explanation_res = {"status": "failed", "reason": f"AI explanation encountered an error: {str(e)}"}

    # 8. Visualization Frames Pre-computation
    try:
        visualization_res = generate_visualization_frames(safe_code, language)
        logger.debug(f"[{request_id}] Visualization generation completed.")
    except Exception as e:
        logger.error(f"[{request_id}] Visualization generation failed: {e}", exc_info=True)
        visualization_res = {"status": "failed", "reason": f"Visualization generation encountered an error: {str(e)}"}

    # 9. Clean 2D Program Control Flow Graph Pre-computation
    try:
        topology_3d_res = generate_3d_topology(safe_code, language, ast_res, complexity_res)
        logger.debug(f"[{request_id}] 3D topology generation completed.")
    except Exception as e:
        logger.error(f"[{request_id}] 3D topology generation failed: {e}", exc_info=True)
        topology_3d_res = {"status": "failed", "reason": f"3D topology generation encountered an error: {str(e)}"}

    review_payload = {
        "success": True, # Overall API call success, not necessarily all analysis steps
        "request_id": request_id,
        "language": language,
        "syntax": syntax_res,
        "ast": ast_res,
        "bugs": bugs_res,
        "issues": bugs_res.get("issues", []),
        "score": bugs_res.get("score", 0),
        "score_breakdown": bugs_res.get("score_breakdown", {}),
        "deductions": bugs_res.get("deductions", []),
        "summary": bugs_res.get("summary", "Analysis completed with partial results due to internal errors in some modules."),
        "basis": bugs_res.get("basis", "Static analysis only. Correctness findings are based on static pattern analysis and are not verified by execution."),
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
            review_data=review_payload, # Save the full payload for consistency
            ai_provider=canonical_provider,
            prompt_version=database.ANALYZER_VERSION
        )
        review_payload["review_id"] = review_id
        logger.info(f"[{request_id}] Review saved to DB with ID: {review_id}")
    except Exception as e:
        logger.error(f"[{request_id}] Database persistence failed for review: {e}", exc_info=True)
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
    review_id_raw = data.get("review_id")
    bug_id = data.get("bug_id")
    level_raw = data.get("level")

    request_id = getattr(g, "request_id", str(uuid.uuid4()))
    logger.info(f"[{request_id}] Hint request for review_id: {review_id_raw}, bug_id: {bug_id}, level: {level_raw}")

    if not review_id_raw:
        return make_error_response("MISSING_REVIEW_ID", "Field 'review_id' is required to access hints.", 400)
    if not bug_id:
        return make_error_response("MISSING_BUG_ID", "Field 'bug_id' is required.", 400)
    if level_raw is None:
        return make_error_response("MISSING_HINT_LEVEL", "Field 'level' is required.", 400)

    try:
        review_id_int = int(review_id_raw)
    except (ValueError, TypeError):
        return make_error_response("INVALID_REVIEW_ID", "Field 'review_id' must be a valid integer.", 400)

    try:
        level = int(level_raw)
        if not (1 <= level <= 3):
            return make_error_response("INVALID_HINT_LEVEL", "Hint level must be between 1 and 3.", 400)
    except (ValueError, TypeError):
        return make_error_response("INVALID_HINT_LEVEL", "Hint level must be an integer.", 400)

    review = database.get_review_by_id(review_id_int)
    if not review:
        return make_error_response("REVIEW_NOT_FOUND", f"Review record #{review_id_int} not found.", 404)

    review_data = review.get("review_data") or {}
    stored_bugs = review_data.get("bugs", {})
    if isinstance(stored_bugs, dict):
        stored_issues = stored_bugs.get("issues", [])
    elif isinstance(stored_bugs, list):
        stored_issues = stored_bugs
    else:
        stored_issues = []
    matched_issue = None
    for iss in stored_issues:
        if iss.get("id") == bug_id:
            matched_issue = iss
            break

    if not matched_issue:
        logger.warning(f"[{request_id}] Issue '{bug_id}' not found in review #{review_id_int}. Stored issues: {[i.get('id') for i in stored_issues]}")
        return make_error_response("ISSUE_NOT_FOUND", f"Issue '{bug_id}' not found in review #{review_id_int}.", 404)

    # Server-side progressive unlock check
    current_unlocked_level = database.record_hint_unlock(review_id_int, bug_id, level)
    if level > current_unlocked_level:
        logger.warning(f"[{request_id}] Invalid hint sequence: requested level {level}, current unlocked {current_unlocked_level}")
        return make_error_response(
            "INVALID_HINT_SEQUENCE",
            f"Cannot skip hints. Current unlocked level is {current_unlocked_level}. Please unlock level {current_unlocked_level + 1} first.",
            400
        )

    hints = matched_issue.get("hints", {})
    hint_text = ""
    hint_title = f"Hint {level}"

    if level == 1:
        hint_text = hints.get("hint1", "A gentle clue for the problem area.")
        hint_title = "Hint 1: Gentle Clue"
    elif level == 2:
        hint_text = hints.get("hint2", "Directional guidance on conditions or scenarios.")
        hint_title = "Hint 2: Directional Guidance"
    elif level == 3:
        hint_text = hints.get("hint3", "A strong hint explaining the core logic adjustment.")
        hint_title = "Hint 3: Strong Hint"
    
    # Ensure a fallback if hint text is unexpectedly empty
    if not hint_text:
        hint_text = "No specific hint available for this level. Please contact support if this persists."
        logger.warning(f"[{request_id}] No hint text found for bug_id {bug_id}, level {level} in review {review_id_int}. Matched hints: {hints}")

    return jsonify({
        "success": True,
        "review_id": review_id_int,
        "bug_id": bug_id,
        "level": level,
        "title": hint_title,
        "hint": hint_text,
        "has_next_hint": level < 3,
        "request_id": request_id
    })


@review_bp.route("/api/v1/solution", methods=["POST"])
@review_bp.route("/api/solution", methods=["POST"])
def get_solution():
    """
    Reveals the solution ONLY after progressive hints have been completed.
    Enforces strict server-side validation against bypassing hint progression.
    """
    data = request.get_json(force=True, silent=True) or {}
    review_id_raw = data.get("review_id")
    bug_id = data.get("bug_id")

    request_id = getattr(g, "request_id", str(uuid.uuid4()))
    logger.info(f"[{request_id}] Solution request for review_id: {review_id_raw}, bug_id: {bug_id}")

    if not review_id_raw:
        return make_error_response("MISSING_REVIEW_ID", "Field 'review_id' is required to reveal solution.", 400)
    if not bug_id:
        return make_error_response("MISSING_BUG_ID", "Field 'bug_id' is required.", 400)

    try:
        review_id_int = int(review_id_raw)
    except (ValueError, TypeError):
        return make_error_response("INVALID_REVIEW_ID", "Field 'review_id' must be a valid integer.", 400)

    review = database.get_review_by_id(review_id_int)
    if not review:
        return make_error_response("REVIEW_NOT_FOUND", f"Review record #{review_id_int} not found.", 404)

    review_data = review.get("review_data") or {}
    stored_bugs = review_data.get("bugs", {})
    if isinstance(stored_bugs, dict):
        stored_issues = stored_bugs.get("issues", [])
    elif isinstance(stored_bugs, list):
        stored_issues = stored_bugs
    else:
        stored_issues = []
    matched_issue = None
    for iss in stored_issues:
        if iss.get("id") == bug_id:
            matched_issue = iss
            break

    if not matched_issue:
        logger.warning(f"[{request_id}] Issue '{bug_id}' not found in review #{review_id_int}.")
        return make_error_response("ISSUE_NOT_FOUND", f"Issue '{bug_id}' not found in review #{review_id_int}.", 404)

    # Strict server-side progressive hint gate
    is_authorized = database.check_solution_authorized(review_id_int, bug_id)
    if not is_authorized:
        logger.warning(f"[{request_id}] Solution access denied for bug_id {bug_id} in review {review_id_int}: hints incomplete.")
        return make_error_response(
            "HINTS_INCOMPLETE",
            "Access Denied: You must unlock all 3 progressive hints before revealing the solution. "
            "CodeComprehension emphasizes deduction over instant answers!",
            403
        )

    database.record_solution_unlocked(review_id_int, bug_id)
    logger.info(f"[{request_id}] Solution unlocked and recorded for bug_id {bug_id} in review {review_id_int}.")

    solution_data = matched_issue.get("solution", {})
    return jsonify({
        "success": True,
        "review_id": review_id_int,
        "bug_id": bug_id,
        "problem": matched_issue.get("problem"),
        "line": matched_issue.get("line"),
        "solution": solution_data,
        "solution_code": solution_data.get("code", "Solution code not available."),
        "why_original_failed": solution_data.get("why_original_failed", "Reason for original failure not available."),
        "why_new_works": solution_data.get("why_new_works", "Explanation for solution effectiveness not available."),
        "request_id": request_id
    })


@review_bp.route("/api/v1/explain", methods=["POST"])
@review_bp.route("/api/explain", methods=["POST"])
def explain_code():
    data = request.get_json(force=True, silent=True) or {}
    code = data.get("code", "")
    language_input = str(data.get("language", "python")).strip().lower()
    request_id = getattr(g, "request_id", str(uuid.uuid4()))

    language = Config.LANGUAGE_ALIASES.get(language_input, language_input)

    if not code:
        return make_error_response("EMPTY_CODE", "No code provided to explain.", 400)

    if language not in Config.SUPPORTED_LANGUAGES:
        supported_langs = ", ".join(sorted([k for k in Config.SUPPORTED_LANGUAGES.keys()]))
        return make_error_response(
            "UNSUPPORTED_LANGUAGE",
            f"Language '{language_input}' is not supported for explanation. Supported languages are: {supported_langs}.",
            400
        )

    safe_code, _ = scan_and_redact_secrets(code)
    try:
        explanation = get_ai_explanation(safe_code, language)
        return jsonify({
            "success": True,
            "explanation": explanation,
            "request_id": request_id,
            "language": language
        })
    except Exception as e:
        logger.error(f"[{request_id}] AI explanation failed in /explain route: {e}", exc_info=True)
        return make_error_response("AI_EXPLANATION_FAILED", f"Failed to generate explanation: {str(e)}", 500)

