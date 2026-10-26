import pytest
from analyzer.secret_redactor import scan_and_redact_secrets
from analyzer.docker_sandbox import is_docker_available, execute_in_docker_container
from analyzer.execution_sandbox import execute_user_code


def test_secret_redaction_openai_key():
    code = 'openai_api_key = "sk-1234567890abcdef1234567890abcdef"'
    redacted, findings = scan_and_redact_secrets(code)
    assert "sk-1234567890abcdef" not in redacted
    assert "[REDACTED_API_KEY]" in redacted or "[REDACTED_PASSWORD]" in redacted
    assert len(findings) > 0


def test_secret_redaction_aws_key():
    code = 'aws_access_key = "AKIAIOSFODNN7EXAMPLE"'
    redacted, findings = scan_and_redact_secrets(code)
    assert "AKIAIOSFODNN7EXAMPLE" not in redacted
    assert len(findings) > 0


def test_docker_sandbox_normal_execution():
    if not is_docker_available():
        pytest.skip("Docker daemon not available in current test environment")

    res = execute_in_docker_container("print('hello ' + str(40 + 2))", timeout=15.0)
    assert res["success"] is True
    assert "hello 42" in res["stdout"]


def test_docker_sandbox_infinite_loop_timeout():
    if not is_docker_available():
        pytest.skip("Docker daemon not available in current test environment")

    res = execute_in_docker_container("while True: pass", timeout=1.0)
    assert res["success"] is False
    assert res["status"] == "TIMEOUT"


def test_docker_sandbox_network_isolation():
    if not is_docker_available():
        pytest.skip("Docker daemon not available in current test environment")

    # Attempting outbound network request must fail or timeout because --network none is enforced
    script = """import urllib.request
try:
    urllib.request.urlopen("https://example.com", timeout=1.0)
    print("NETWORK_ACCESSIBLE")
except Exception as e:
    print("NETWORK_BLOCKED:" + str(e))
"""
    res = execute_in_docker_container(script, timeout=2.5)
    # The container has no network interface, so socket open fails
    assert "NETWORK_ACCESSIBLE" not in res.get("stdout", "")
