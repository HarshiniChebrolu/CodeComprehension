import pytest


def test_healthz_endpoint(client):
    resp = client.get("/healthz")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["status"] == "healthy"
    assert data["database"] == "connected"
    assert "version" in data
    # Ensure no secrets or API keys are leaked in health check
    assert "SECRET_KEY" not in str(data)
    assert "GEMINI_API_KEY" not in str(data)


def test_security_headers_present(client):
    resp = client.get("/healthz")
    headers = resp.headers
    assert "X-Request-ID" in headers
    assert headers["X-Content-Type-Options"] == "nosniff"
    assert headers["X-Frame-Options"] == "SAMEORIGIN"
    assert "Content-Security-Policy" in headers


def test_review_empty_code_rejected(client):
    resp = client.post("/api/v1/review", json={"code": "", "language": "python"})
    assert resp.status_code == 400
    data = resp.get_json()
    assert data["success"] is False
    assert data["error"]["code"] == "EMPTY_CODE"


def test_review_excessive_code_length_rejected(client):
    huge_code = "x = 1\n" * 20000  # > 50,000 characters
    resp = client.post("/api/v1/review", json={"code": huge_code, "language": "python"})
    assert resp.status_code == 413
    data = resp.get_json()
    assert data["success"] is False
    assert data["error"]["code"] == "CODE_TOO_LONG"


def test_review_unsupported_language_rejected(client):
    resp = client.post("/api/v1/review", json={"code": "print('hi')", "language": "ruby"})
    assert resp.status_code == 400
    data = resp.get_json()
    assert data["success"] is False
    assert data["error"]["code"] == "UNSUPPORTED_LANGUAGE"


def test_review_valid_python_success(client):
    code = """def add_numbers(a, b):
    return a + b
"""
    resp = client.post("/api/v1/review", json={"code": code, "language": "python"})
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["success"] is True
    assert data["score"] >= 80
    assert "bugs" in data
    assert "complexity" in data
    assert "explanation" in data
    assert "test_cases" in data
    assert "topology_3d" in data
    assert data["review_id"] is not None
