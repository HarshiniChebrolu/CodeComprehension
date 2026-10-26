import uuid
from flask import Blueprint, request, jsonify, g
from analyzer.visualizer import generate_visualization_frames

visualization_bp = Blueprint("visualization_bp", __name__)


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


@visualization_bp.route("/api/v1/visualize", methods=["POST"])
@visualization_bp.route("/api/visualize", methods=["POST"])
def get_visualization():
    data = request.get_json(force=True, silent=True) or {}
    code = data.get("code", "")
    language = str(data.get("language", "python")).strip().lower()

    if not code:
        return make_error_response("EMPTY_CODE", "No code provided for visualization.", 400)

    frames_data = generate_visualization_frames(code, language)
    return jsonify({
        "success": True,
        "visualization": frames_data
    })
