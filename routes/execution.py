import uuid
import logging
from flask import Blueprint, request, jsonify, g
from config import Config
from extensions import limiter
from analyzer.execution_sandbox import execute_user_code, run_test_cases_safely, get_runnable_languages_status

logger = logging.getLogger("codecomprehension.routes.execution")
execution_bp = Blueprint("execution_bp", __name__)


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


@execution_bp.route("/api/v1/execute", methods=["POST"])
@execution_bp.route("/api/execute", methods=["POST"])
@limiter.limit(Config.RATELIMIT_EXECUTE)
def run_code():
    data = request.get_json(force=True, silent=True) or {}
    code = data.get("code", "")
    language_input = str(data.get("language", "python")).strip().lower()
    custom_stdin = data.get("stdin", "")
    request_id = getattr(g, "request_id", str(uuid.uuid4()))
    
    language = Config.LANGUAGE_ALIASES.get(language_input, language_input)

    if not code or not code.strip():
        return make_error_response("EMPTY_CODE", "No code provided to execute.", 400)

    if len(code) > Config.MAX_CODE_LENGTH:
        return make_error_response(
            "CODE_TOO_LONG",
            f"Code exceeds maximum allowed limit of {Config.MAX_CODE_LENGTH} characters. Submitted: {len(code)}",
            413
        )
    
    if len(custom_stdin) > Config.MAX_STDIN_LENGTH:
        return make_error_response(
            "STDIN_TOO_LONG",
            f"Provided stdin exceeds maximum allowed limit of {Config.MAX_STDIN_LENGTH} characters. Submitted: {len(custom_stdin)}",
            413
        )

    if language not in Config.SUPPORTED_LANGUAGES:
        supported_langs = ", ".join(sorted([k for k in Config.SUPPORTED_LANGUAGES.keys()]))
        return make_error_response(
            "UNSUPPORTED_LANGUAGE",
            f"Language '{language_input}' is not supported for execution. Supported languages are: {supported_langs}.",
            400
        )

    logger.info(f"[{request_id}] Executing code in {language}...")
    result = execute_user_code(code, language, custom_stdin)
    
    # Ensure success is always present in the top-level response for client consumption
    result["success"] = result["status"] == "OK"
    result["request_id"] = request_id

    status_code = 200
    if result["status"] == "SECURITY_VIOLATION":
        status_code = 403
    elif result["status"] in ["UNAVAILABLE", "DISABLED", "CONFIG_ERROR", "UNSUPPORTED_LANGUAGE", "SECURITY_ERROR"]:
        status_code = 503 if result["status"] == "UNAVAILABLE" else 500
    elif result["status"] == "COMPILE_ERROR":
        status_code = 400
    elif result["status"] in ["RUNTIME_ERROR", "TIMEOUT", "MEMORY_LIMIT_EXCEEDED"]:
        status_code = 400
        
    logger.info(f"[{request_id}] Code execution finished with status: {result['status']}")
    return jsonify(result), status_code


@execution_bp.route("/api/v1/run-tests", methods=["POST"])
@execution_bp.route("/api/run-tests", methods=["POST"])
@limiter.limit(Config.RATELIMIT_EXECUTE)
def run_tests():
    data = request.get_json(force=True, silent=True) or {}
    code = data.get("code", "")
    test_cases = data.get("test_cases", [])
    func_name = data.get("function_name", "solution")
    language_input = str(data.get("language", "python")).strip().lower()
    request_id = getattr(g, "request_id", str(uuid.uuid4()))

    language = Config.LANGUAGE_ALIASES.get(language_input, language_input)

    if not code or not code.strip():
        return make_error_response("EMPTY_CODE", "No code provided for test suite.", 400)
    
    if len(code) > Config.MAX_CODE_LENGTH:
        return make_error_response(
            "CODE_TOO_LONG",
            f"Code exceeds maximum allowed limit of {Config.MAX_CODE_LENGTH} characters. Submitted: {len(code)}",
            413
        )

    if language not in Config.SUPPORTED_LANGUAGES:
        supported_langs = ", ".join(sorted([k for k in Config.SUPPORTED_LANGUAGES.keys()]))
        return make_error_response(
            "UNSUPPORTED_LANGUAGE",
            f"Language '{language_input}' is not supported for testing. Supported languages are: {supported_langs}.",
            400
        )
    
    logger.info(f"[{request_id}] Running tests for {language} with {len(test_cases)} cases...")
    results = run_test_cases_safely(code, test_cases, func_name, language)

    passed_count = sum(1 for r in results if r.get("passed", False))
    total_count = len(results)

    pass_rate_str = f"{(passed_count / total_count * 100):.1f}%" if total_count > 0 else "0%"
    logger.info(f"[{request_id}] Test run finished. Passed: {passed_count}/{total_count} ({pass_rate_str})")

    return jsonify({
        "success": True,
        "request_id": request_id,
        "results": results,
        "passed_count": passed_count,
        "total_count": total_count,
        "pass_rate": pass_rate_str
    })


@execution_bp.route("/api/v1/languages", methods=["GET"])
def get_languages():
    """
    Returns a list of all supported languages and their execution readiness status.
    """
    request_id = getattr(g, "request_id", str(uuid.uuid4()))
    logger.info(f"[{request_id}] Fetching language execution statuses.")
    language_statuses = get_runnable_languages_status()
    
    return jsonify({
        "success": True,
        "request_id": request_id,
        "languages": language_statuses
    })
