import pytest


def test_hint_progression_server_gate(client):
    code = """def find_max(numbers):
    max_num = 0
    for num in numbers:
        if num > max_num:
            max_num = num
    return max_num
"""
    # 1. Submit review
    r_rev = client.post("/api/v1/review", json={"code": code, "language": "python"})
    assert r_rev.status_code == 200
    rev_data = r_rev.get_json()
    review_id = rev_data["review_id"]
    issues = rev_data["bugs"]["issues"]
    assert len(issues) > 0
    bug_id = issues[0]["id"]

    # 2. Attempting to bypass hints and reveal solution immediately MUST be rejected with 403 Forbidden
    r_bypass = client.post("/api/v1/solution", json={
        "review_id": review_id,
        "bug_id": bug_id,
        "issues": issues
    })
    assert r_bypass.status_code == 403
    bypass_data = r_bypass.get_json()
    assert bypass_data["success"] is False
    assert bypass_data["error"]["code"] == "HINTS_INCOMPLETE"

    # 3. Request Hint 1
    r_h1 = client.post("/api/v1/hint", json={
        "review_id": review_id,
        "bug_id": bug_id,
        "level": 1,
        "issues": issues
    })
    assert r_h1.status_code == 200
    assert r_h1.get_json()["level"] == 1

    # 4. Attempt solution after only 1 hint -> Still 403
    r_bypass_2 = client.post("/api/v1/solution", json={
        "review_id": review_id,
        "bug_id": bug_id,
        "issues": issues
    })
    assert r_bypass_2.status_code == 403

    # 5. Unlock Hint 2 & Hint 3
    client.post("/api/v1/hint", json={"review_id": review_id, "bug_id": bug_id, "level": 2, "issues": issues})
    client.post("/api/v1/hint", json={"review_id": review_id, "bug_id": bug_id, "level": 3, "issues": issues})

    # 6. Now solution request is authorized and returns 200 OK
    r_sol = client.post("/api/v1/solution", json={
        "review_id": review_id,
        "bug_id": bug_id,
        "issues": issues
    })
    assert r_sol.status_code == 200
    sol_data = r_sol.get_json()
    assert sol_data["success"] is True
    assert "solution" in sol_data
    assert "code" in sol_data["solution"] or "corrected_code" in str(sol_data["solution"])
