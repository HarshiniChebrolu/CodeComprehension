import uuid
from flask import Blueprint, request, jsonify, g
import database

history_bp = Blueprint("history_bp", __name__)


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


@history_bp.route("/api/v1/history", methods=["GET"])
@history_bp.route("/api/history", methods=["GET"])
def list_history():
    """
    Returns paginated review history and the total record count.
    """
    try:
        limit = max(1, min(int(request.args.get("limit", 20)), 100))
        offset = max(0, int(request.args.get("offset", 0)))
    except ValueError:
        return make_error_response("INVALID_PAGINATION", "Parameters 'limit' and 'offset' must be valid integers.", 400)

    reviews, total_count = database.get_recent_reviews(limit=limit, offset=offset)
    return jsonify({
        "success": True,
        "history": reviews,
        "pagination": {
            "limit": limit,
            "offset": offset,
            "total_count": total_count,
            "has_more": (offset + len(reviews)) < total_count
        }
    })


@history_bp.route("/api/v1/history/<int:review_id>", methods=["GET"])
@history_bp.route("/api/history/<int:review_id>", methods=["GET"])
def get_history_item(review_id):
    review = database.get_review_by_id(review_id)
    if not review:
        return make_error_response("NOT_FOUND", f"Review record #{review_id} not found.", 404)
    return jsonify({
        "success": True,
        "review": review
    })


@history_bp.route("/api/v1/history/<int:review_id>", methods=["DELETE"])
@history_bp.route("/api/history/<int:review_id>", methods=["DELETE"])
def delete_history_item(review_id):
    """
    Deletes a single review record.
    Returns HTTP 404 if record did not exist.
    """
    deleted = database.delete_review(review_id)
    if not deleted:
        return make_error_response("NOT_FOUND", f"Review record #{review_id} does not exist.", 404)
    return jsonify({
        "success": True,
        "message": f"Review #{review_id} was successfully deleted."
    })


@history_bp.route("/api/v1/history", methods=["DELETE"])
@history_bp.route("/api/history", methods=["DELETE"])
def delete_all_history():
    """
    Permanently deletes all stored review records and associated progress.
    """
    deleted_count = database.delete_all_reviews()
    return jsonify({
        "success": True,
        "message": f"All review history records ({deleted_count} total) have been permanently deleted.",
        "deleted_count": deleted_count
    })
