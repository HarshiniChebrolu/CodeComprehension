import uuid
from flask import Blueprint, request, jsonify, g
from config import Config
from extensions import limiter
from analyzer.execution_sandbox import execute_user_code, run_test_cases_safely

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
    language = str(data.get("language", "python")).strip().lower()
    custom_stdin = data.get("stdin", "")

    if not code or not code.strip():
        return make_error_response("EMPTY_CODE", "No code provided to execute.", 400)

    if len(code) > Config.MAX_CODE_LENGTH:
        return make_error_response(
            "CODE_TOO_LONG",
            f"Code exceeds maximum allowed limit of {Config.MAX_CODE_LENGTH} characters.",
            413
        )

    result = execute_user_code(code, language, custom_stdin)
    result["request_id"] = getattr(g, "request_id", str(uuid.uuid4()))
    return jsonify(result)


@execution_bp.route("/api/v1/run-tests", methods=["POST"])
@execution_bp.route("/api/run-tests", methods=["POST"])
@limiter.limit(Config.RATELIMIT_EXECUTE)
def run_tests():
    data = request.get_json(force=True, silent=True) or {}
    code = data.get("code", "")
    test_cases = data.get("test_cases", [])
    func_name = data.get("function_name", "solution")
    language = str(data.get("language", "python")).strip().lower()

    if not code:
        return make_error_response("EMPTY_CODE", "No code provided for test suite.", 400)

    results = run_test_cases_safely(code, test_cases, func_name, language)

    passed_count = sum(1 for r in results if r.get("passed", False))
    total_count = len(results)

    return jsonify({
        "success": True,
        "request_id": getattr(g, "request_id", str(uuid.uuid4())),
        "results": results,
        "passed_count": passed_count,
        "total_count": total_count,
        "pass_rate": f"{(passed_count / total_count * 100):.1f}%" if total_count > 0 else "0%"
    })
