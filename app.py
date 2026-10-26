import uuid
import logging
from flask import Flask, render_template, jsonify, request, g
from config import Config
from extensions import limiter
import database
from analyzer.docker_sandbox import is_docker_available

from routes.review import review_bp
from routes.execution import execution_bp
from routes.visualization import visualization_bp
from routes.history import history_bp

logger = logging.getLogger("codecomprehension.app")


def create_app(config_override=None):
    """
    Application factory for CodeComprehension.
    Supports clean dependency injection and testing configurations.
    """
    app = Flask(__name__, static_folder="static", template_folder="templates")

    # Apply configuration
    app.config.from_object(Config)
    if config_override:
        app.config.update(config_override)

    # Enforce request payload size threshold (prevents payload DoS)
    app.config["MAX_CONTENT_LENGTH"] = Config.MAX_CONTENT_LENGTH

    # Session Cookie Security
    app.config["SESSION_COOKIE_HTTPONLY"] = True
    app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
    if app.config.get("FLASK_ENV") == "production":
        app.config["SESSION_COOKIE_SECURE"] = True

    # Configure ProxyFix for reverse proxy deployments (e.g. Nginx, Gunicorn)
    trusted_proxies = app.config.get("TRUSTED_PROXIES", 0)
    if trusted_proxies > 0:
        try:
            from werkzeug.middleware.proxy_fix import ProxyFix
            app.wsgi_app = ProxyFix(
                app.wsgi_app,
                x_for=trusted_proxies,
                x_proto=trusted_proxies,
                x_host=trusted_proxies,
                x_port=trusted_proxies
            )
            logger.info("Configured Werkzeug ProxyFix with %d trusted proxies.", trusted_proxies)
        except Exception as e:
            logger.warning("Failed to initialize ProxyFix: %s", e)

    # Initialize extensions
    limiter.init_app(app)

    # Initialize SQLite schema and versioned migrations for configured database
    db_path = app.config.get("DATABASE_PATH")
    try:
        database.init_db(db_path=db_path)
    except Exception as e:
        logger.error("Failed to initialize database during startup: %s", e)

    # Register API blueprints
    app.register_blueprint(review_bp)
    app.register_blueprint(execution_bp)
    app.register_blueprint(visualization_bp)
    app.register_blueprint(history_bp)

    # Request ID and Security Header Middleware
    @app.before_request
    def before_request_hook():
        g.request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())

    @app.after_request
    def set_security_headers(response):
        response.headers["X-Request-ID"] = getattr(g, "request_id", "")
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "SAMEORIGIN"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        # Content Security Policy: strictly bounded, permits local styles & Google fonts
        csp_policy = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline'; "
            "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
            "font-src 'self' https://fonts.gstatic.com; "
            "img-src 'self' data:; "
            "connect-src 'self';"
        )
        response.headers["Content-Security-Policy"] = csp_policy
        return response

    @app.route("/")
    def index():
        return render_template("index.html")

    @app.route("/healthz", methods=["GET"])
    def health_check():
        """
        Production health probe endpoint.
        Verifies database and execution sandbox readiness without leaking secrets.
        """
        db_healthy = False
        db_path = app.config.get("DATABASE_PATH")
        try:
            with database.get_db(db_path=db_path) as conn:
                cur = conn.cursor()
                cur.execute("SELECT 1;")
                db_healthy = (cur.fetchone()[0] == 1)
        except Exception:
            db_healthy = False

        docker_ready = is_docker_available()

        status_code = 200 if db_healthy else 503
        return jsonify({
            "status": "healthy" if db_healthy else "degraded",
            "database": "connected" if db_healthy else "disconnected",
            "execution_sandbox": "docker_ready" if docker_ready else "fallback_active",
            "ai_provider": app.config.get("DEFAULT_AI_PROVIDER", Config.DEFAULT_AI_PROVIDER),
            "version": database.ANALYZER_VERSION
        }), status_code

    # Standardized error handlers with request_id
    @app.errorhandler(404)
    def handle_404(e):
        req_id = getattr(g, "request_id", str(uuid.uuid4()))
        return jsonify({
            "success": False,
            "error": {
                "code": "NOT_FOUND",
                "message": "The requested endpoint or resource was not found.",
                "request_id": req_id
            }
        }), 404

    @app.errorhandler(413)
    def handle_413(e):
        req_id = getattr(g, "request_id", str(uuid.uuid4()))
        return jsonify({
            "success": False,
            "error": {
                "code": "PAYLOAD_TOO_LARGE",
                "message": f"Submitted payload exceeds the {Config.MAX_CONTENT_LENGTH} byte limit.",
                "request_id": req_id
            }
        }), 413

    @app.errorhandler(429)
    def handle_429(e):
        req_id = getattr(g, "request_id", str(uuid.uuid4()))
        return jsonify({
            "success": False,
            "error": {
                "code": "RATE_LIMIT_EXCEEDED",
                "message": "Too many requests. Please slow down and try again shortly.",
                "request_id": req_id
            }
        }), 429

    @app.errorhandler(500)
    def handle_500(e):
        req_id = getattr(g, "request_id", str(uuid.uuid4()))
        logger.exception("Internal server error [request_id=%s]: %s", req_id, e)
        return jsonify({
            "success": False,
            "error": {
                "code": "INTERNAL_SERVER_ERROR",
                "message": "An internal error occurred in the analysis engine.",
                "request_id": req_id
            }
        }), 500

    return app


# Lazy application singleton: ensures importing `create_app` in test suites
# does not trigger side-effects or touch the production database during imports!
_app_instance = None


def __getattr__(name):
    if name == "app":
        global _app_instance
        if _app_instance is None:
            _app_instance = create_app()
        return _app_instance
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")


if __name__ == "__main__":
    host = Config.HOST
    port = Config.PORT
    debug = Config.DEBUG

    print("=" * 65)
    print("  CodeComprehension — AI Code Reviewer & Coding Mentor")
    print("  'Understand your code. Don't just fix it.'")
    print(f"  Server starting at: http://{host}:{port}")
    print(f"  Environment: {Config.FLASK_ENV} | Debug: {debug}")
    print("=" * 65)
    live_app = create_app()
    live_app.run(host=host, port=port, debug=debug)
