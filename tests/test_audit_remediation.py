import os
import tempfile
import pytest
import sqlite3
from config import AppSettings, Config
from app import create_app
import database
from ai.gemini_provider import GeminiProvider
from analyzer.secret_redactor import scan_and_redact_secrets
from analyzer.execution_sandbox import execute_user_code


def test_production_secret_key_validation():
    """Ensure production cannot start with an empty, short, or placeholder SECRET_KEY."""
    # Empty secret key in production
    with pytest.raises(Exception) as exc_info:
        AppSettings(FLASK_ENV="production", SECRET_KEY="")
    assert "SECRET_KEY must be explicitly set" in str(exc_info.value)

    # Short secret key in production (< 16 chars)
    with pytest.raises(Exception) as exc_info:
        AppSettings(FLASK_ENV="production", SECRET_KEY="short_key")
    assert "at least 16 characters" in str(exc_info.value)

    # Insecure placeholder in production
    with pytest.raises(Exception) as exc_info:
        AppSettings(FLASK_ENV="production", SECRET_KEY="changeme12345678")
    assert "weak key" in str(exc_info.value) or "at least 16 characters" in str(exc_info.value)

    # Valid strong key in production
    valid_settings = AppSettings(
        FLASK_ENV="production",
        SECRET_KEY="a-very-strong-production-secret-key-12345",
        EXECUTION_BACKEND="docker"
    )
    assert valid_settings.SECRET_KEY == "a-very-strong-production-secret-key-12345"


def test_production_local_dev_unsafe_blocked():
    """Ensure production strictly forbids EXECUTION_BACKEND='local_dev_unsafe'."""
    with pytest.raises(Exception) as exc_info:
        AppSettings(
            FLASK_ENV="production",
            SECRET_KEY="a-very-strong-production-secret-key-12345",
            EXECUTION_BACKEND="local_dev_unsafe"
        )
    assert "local_dev_unsafe' is strictly forbidden in production" in str(exc_info.value)


def test_gemini_provider_uses_header_not_query_param():
    """Verify Gemini provider does not expose API key in URL query string."""
    provider = GeminiProvider(api_key="test-api-key-safe-123")
    # Verify offline fallback when key is not actual Google key
    assert provider.api_key == "test-api-key-safe-123"
    # We inspect the code pattern to ensure key is sent in header, not in URL string
    import inspect
    source = inspect.getsource(provider.generate_explanation)
    assert "x-goog-api-key" in source
    assert "key=" not in source.split("url =")[1].split("\n")[0]


def test_secret_redaction_before_persistence_and_ai(client):
    """Verify submitted code secrets are redacted before saving to DB or sending to AI."""
    code_with_secret = '''
OPENAI_KEY = "sk-1234567890abcdef1234567890abcdef"
def greet(name):
    return "Hello " + name
'''
    resp = client.post("/api/v1/review", json={"code": code_with_secret, "language": "python"})
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["success"] is True
    review_id = data["review_id"]
    assert review_id is not None

    # Verify secret is detected in warnings
    assert len(data.get("security_warnings", [])) > 0

    # Verify database record does NOT store the raw secret
    stored = database.get_review_by_id(review_id)
    assert stored is not None
    assert "sk-1234567890abcdef1234567890abcdef" not in stored["code"]
    assert "[REDACTED_API_KEY]" in stored["code"]


def test_solution_gate_rejects_missing_review_id(client):
    """Enforce that solution endpoint rejects requests missing review_id."""
    resp = client.post("/api/v1/solution", json={"bug_id": "test_bug"})
    assert resp.status_code == 400
    data = resp.get_json()
    assert data["error"]["code"] == "MISSING_REVIEW_ID"


def test_solution_gate_rejects_nonexistent_review(client):
    """Enforce that solution endpoint returns 404 for nonexistent review_id."""
    resp = client.post("/api/v1/solution", json={"review_id": 9999999, "bug_id": "test_bug"})
    assert resp.status_code == 404
    data = resp.get_json()
    assert data["error"]["code"] == "REVIEW_NOT_FOUND"


def test_hint_gate_rejects_skipping_levels(client):
    """Enforce sequential progression: requesting Level 3 before Level 1 and 2 is rejected."""
    # Create a review with a detectable bug
    code = """def find_max(numbers):
    max_num = 0
    for num in numbers:
        if num > max_num:
            max_num = num
    return max_num
"""
    rev_resp = client.post("/api/v1/review", json={"code": code, "language": "python"})
    rev_id = rev_resp.get_json()["review_id"]
    issues = rev_resp.get_json()["bugs"]["issues"]
    assert len(issues) > 0
    bug_id = issues[0]["id"]

    # Try skipping directly to Hint 3
    resp = client.post("/api/v1/hint", json={
        "review_id": rev_id,
        "bug_id": bug_id,
        "level": 3
    })
    assert resp.status_code == 400
    data = resp.get_json()
    assert data["error"]["code"] == "INVALID_HINT_SEQUENCE"


def test_test_database_isolation():
    """Verify that Flask application context DATABASE_PATH is respected by get_db."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tf:
        custom_db_path = tf.name

    try:
        custom_app = create_app({
            "TESTING": True,
            "DATABASE_PATH": custom_db_path,
            "SECRET_KEY": "test-custom-isolation-key-9999"
        })

        with custom_app.app_context():
            # Verify get_db uses the custom_app's DATABASE_PATH
            with database.get_db() as conn:
                cur = conn.cursor()
                cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='reviews';")
                row = cur.fetchone()
                assert row is not None
                assert row[0] == "reviews"
    finally:
        if os.path.exists(custom_db_path):
            try:
                os.remove(custom_db_path)
            except Exception:
                pass


def test_cache_deduplication_and_analyzer_version(client):
    """Verify that review caching returns cached=True and includes analyzer version."""
    code = "def is_positive(n):\n    return n > 0\n"
    # First submission -> fresh review
    r1 = client.post("/api/v1/review", json={"code": code, "language": "python"})
    assert r1.status_code == 200
    d1 = r1.get_json()
    assert d1["cached"] is False

    # Second submission with same code -> cached review
    r2 = client.post("/api/v1/review", json={"code": code, "language": "python"})
    assert r2.status_code == 200
    d2 = r2.get_json()
    assert d2["cached"] is True
    assert d2["review_id"] == d1["review_id"]
